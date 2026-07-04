from dataclasses import replace

from articlebots.convert import article_slug, render_article, to_markdown
from articlebots.scraper import Article

SAMPLE = Article(
    id=42,
    title="How do I add a YouTube video?",
    url="https://example.zendesk.com/hc/en-us/articles/42",
    body_html="",
    updated_at="2026-01-01T00:00:00Z",
    section_id=1,
)


def test_headings_become_atx():
    md = to_markdown("<h2>Setup</h2><p>words</p>")
    assert "## Setup" in md


def test_editor_junk_is_stripped():
    html = '<p style="color:red" class="wysiwyg-indent" data-x="1">hi <span>there</span></p>'
    md = to_markdown(html)
    assert md.strip() == "hi there"


def test_links_survive():
    md = to_markdown('<p><a href="/hc/en-us/articles/99">see docs</a></p>')
    assert "[see docs](/hc/en-us/articles/99)" in md


def test_code_blocks_get_fenced_with_language():
    html = '<pre><code class="language-python">print("hi")</code></pre>'
    md = to_markdown(html)
    assert '```python\nprint("hi")\n```' in md


def test_empty_paragraphs_removed():
    md = to_markdown("<p>real</p><p>  </p><div></div><p>content</p>")
    assert "real" in md and "content" in md
    assert "\n\n\n" not in md


def test_front_matter_carries_citation_url():
    text = render_article(replace(SAMPLE, body_html="<p>x</p>"))
    assert text.startswith("---\n")
    assert "url: https://example.zendesk.com/hc/en-us/articles/42" in text
    assert "article_id: 42" in text


def test_slug_is_filesystem_safe():
    assert article_slug(SAMPLE) == "how-do-i-add-a-youtube-video"


def test_upload_variant_repeats_url_in_every_section():
    from articlebots.convert import render_upload

    art = Article(**{**SAMPLE.__dict__, "body_html": "<p>intro</p><h2>Setup</h2><p>a</p><h2>Usage</h2><p>b</p>"})
    text = render_upload(art)
    assert text.count(f"Article URL: {art.url}") == 4  # top, 2 sections, end
    assert "updated_at" not in text
