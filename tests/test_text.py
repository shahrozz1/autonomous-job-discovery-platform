from roleful.text import html_to_text


def test_headings_and_lists_keep_their_shape():
    markup = "<h3>Requirements</h3><ul><li>SQL</li><li><p>Excel</p></li></ul><p>Thanks!</p>"
    assert html_to_text(markup) == "# Requirements\n- SQL\n- Excel\nThanks!"


def test_a_bold_line_is_a_heading_but_a_bold_word_is_not():
    assert html_to_text("<p><strong>About you</strong></p><p>You <b>love</b> data.</p>") == (
        "# About you\nYou love data."
    )


def test_escaped_html_is_unescaped_first():
    assert html_to_text("&lt;p&gt;Fish &amp;amp; chips&lt;/p&gt;") == "Fish & chips"


def test_scripts_and_odd_spaces_are_dropped():
    assert html_to_text("<p>One  two</p><script>alert(1)</script>") == "One two"


def test_empty():
    assert html_to_text(None) == ""
