"""The AI step, tested against a stand-in for the API. No key needed and nothing is sent."""

import json

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

from roleful import pipeline  # noqa: E402
from roleful.enrich import enrich, waiting  # noqa: E402
from tests.test_pipeline import DAY1, run, web  # noqa: E402, F401

ANSWER = {
    "summary": "Plans stock for kitchen tools.",
    "required_skills": ["Excel", "SQL"],
    "preferred_skills": ["Tableau"],
    "years_min": 1,
    "pay_min": 70000,
    "pay_max": 80000,
}


class FakeAPI:
    def __init__(self, status=200, stop_reason="end_turn"):
        self.requests, self.status, self.stop_reason = [], status, stop_reason
        transport = httpx2.MockTransport(self.answer)
        http_client = anthropic.DefaultHttpxClient(transport=transport)
        self.client = anthropic.Anthropic(api_key="test", http_client=http_client, max_retries=0)

    def answer(self, request):
        self.requests.append(json.loads(request.content))
        if self.status != 200:
            return httpx2.Response(self.status, json={"type": "error", "error": {"type": "x", "message": "no"}})
        body = {
            "id": "msg", "type": "message", "role": "assistant", "model": "test", "stop_sequence": None,
            "stop_reason": self.stop_reason, "usage": {"input_tokens": 900, "output_tokens": 60},
            "content": [{"type": "text", "text": json.dumps(ANSWER)}],
        }  # fmt: skip
        return httpx2.Response(200, json=body)


def test_each_text_is_sent_once(store, web):  # noqa: F811
    run(store, DAY1)
    api = FakeAPI()
    first = enrich(store, client=api.client)
    sent = len(api.requests)
    assert sent == len({r["messages"][0]["content"] for r in api.requests})
    assert "0 still waiting" in first
    enrich(store, client=api.client)
    assert len(api.requests) == sent


def test_the_request_asks_for_the_schema_and_marks_the_posting_as_data(store, web):  # noqa: F811
    run(store, DAY1)
    api = FakeAPI()
    enrich(store, limit=1, client=api.client)
    request = api.requests[0]
    assert set(request["output_config"]["format"]["schema"]["properties"]) == set(ANSWER)
    assert request["messages"][0]["content"].startswith("<posting>")
    assert "ignore them" in request["system"]


def test_the_limit_caps_spending(store, web):  # noqa: F811
    run(store, DAY1)
    api = FakeAPI()
    enrich(store, limit=1, client=api.client)
    assert len(api.requests) == 1
    assert len(waiting(store)) >= 1


def test_answers_fill_gaps_but_never_replace_what_the_company_listed(store, web, profile, rules):  # noqa: F811
    run(store, DAY1)
    store.db.execute("UPDATE postings SET feed_pay_min = NULL, feed_pay_max = NULL WHERE source_id = '102'")
    enrich(store, client=FakeAPI().client)
    pipeline.refresh(store, profile, rules, DAY1)
    pay = dict(store.rows("SELECT source_id, pay_min FROM postings WHERE source_id IN ('101', '102')"))
    assert pay == {"101": 64480, "102": 70000}


def test_a_declined_or_cut_off_answer_is_skipped(store, web):  # noqa: F811
    run(store, DAY1)
    message = enrich(store, limit=1, client=FakeAPI(stop_reason="max_tokens").client)
    assert message.startswith("0 postings read")
    assert store.ai_facts() == {}


@pytest.mark.parametrize("status", [429, 500])
def test_errors_stop_the_step_without_losing_anything(store, web, status):  # noqa: F811
    run(store, DAY1)
    api = FakeAPI(status=status)
    assert "Stopped early" in enrich(store, client=api.client)
    assert len(api.requests) == 1
