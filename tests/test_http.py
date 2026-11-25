import pytest
import requests

from roleful import http
from roleful.http import Client, FeedError


class Reply:
    def __init__(self, status, data=None, headers=None):
        self.status_code, self._data, self.headers = status, data, headers or {}

    def json(self):
        if self._data is None:
            raise ValueError
        return self._data


@pytest.fixture
def client(monkeypatch):
    waits = []
    monkeypatch.setattr(http.time, "sleep", waits.append)
    client = Client(pause=0)
    client.waits = waits
    client.sent = []

    def answer_with(*replies):
        queue = list(replies)

        def get(url, headers, timeout):
            client.sent.append(headers)
            reply = queue.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        client.session.get = get

    client.answer_with = answer_with
    return client


def test_returns_json_and_etag(client):
    client.answer_with(Reply(200, {"jobs": []}, {"ETag": "abc"}))
    reply = client.get_json("https://x.test")
    assert (reply.data, reply.etag) == ({"jobs": []}, "abc")


def test_sends_the_etag_and_understands_not_modified(client):
    client.answer_with(Reply(304))
    reply = client.get_json("https://x.test", etag="abc")
    assert client.sent == [{"If-None-Match": "abc"}]
    assert (reply.status, reply.data, reply.etag) == (304, None, "abc")


def test_retries_when_busy_and_respects_retry_after(client):
    client.answer_with(Reply(429, headers={"Retry-After": "30"}), Reply(503), Reply(200, []))
    assert client.get_json("https://x.test").data == []
    assert 30 in client.waits


def test_retries_after_a_dropped_connection(client):
    client.answer_with(requests.ConnectionError(), Reply(200, []))
    assert client.get_json("https://x.test").data == []


def test_gives_up_after_the_last_retry(client):
    client.answer_with(*[Reply(500)] * 4)
    with pytest.raises(FeedError, match="HTTP 500"):
        client.get_json("https://x.test")


def test_does_not_retry_a_missing_board(client):
    client.answer_with(Reply(404))
    with pytest.raises(FeedError, match="HTTP 404"):
        client.get_json("https://x.test")
    assert len(client.sent) == 1


def test_a_page_that_is_not_json_is_a_failed_read(client):
    client.answer_with(Reply(200))
    with pytest.raises(FeedError, match="not JSON"):
        client.get_json("https://x.test")
