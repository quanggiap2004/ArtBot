"""Turn Zendesk article HTML into clean markdown with front matter."""

import re

import yaml
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from slugify import slugify

from articlebots.scraper import Article

# Attributes that carry no meaning outside the Zendesk editor
_NOISE_ATTRS = re.compile(r"^(data-|aria-)")
_KEEP_ATTRS = {"href", "src", "alt", "title", "name", "id"}


class _Converter(MarkdownConverter):
    """markdownify tuned for help-center bodies."""

    def convert_pre(self, el, text, parent_tags):
        code = el.get_text()
        lang = ""
        inner = el.find("code")
        if inner and inner.get("class"):
            for cls in inner["class"]:
                if cls.startswith("language-"):
                    lang = cls.removeprefix("language-")
                    break
        return f"\n```{lang}\n{code.rstrip()}\n```\n"


def _clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style", "iframe"]):
        tag.decompose()

    for tag in soup.find_all(True):
        keep = _KEEP_ATTRS | ({"class"} if tag.name == "code" else set())
        tag.attrs = {
            k: v
            for k, v in tag.attrs.items()
            if k in keep and not _NOISE_ATTRS.match(k)
        }

    # unwrap spans and empty wrappers the editor leaves behind
    for span in soup.find_all("span"):
        span.unwrap()
    for tag in soup.find_all(["div", "p"]):
        if not tag.get_text(strip=True) and not tag.find(["img", "iframe"]):
            tag.decompose()

    return soup


def to_markdown(html: str) -> str:
    soup = _clean_html(html)
    md = _Converter(heading_style="ATX", bullets="*").convert_soup(soup)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = "\n".join(line.rstrip() for line in md.splitlines())
    return md.strip() + "\n"


def article_slug(article: Article) -> str:
    return slugify(article.title, max_length=80)


def render_article(article: Article) -> str:
    """Human-facing file: YAML front matter + converted body."""
    meta = {
        "title": article.title,
        "article_id": article.id,
        "url": article.url,
        "updated_at": article.updated_at,
    }
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return (
        f"---\n{front}\n---\n\n"
        f"Article URL: {article.url}\n\n"
        f"{to_markdown(article.body_html)}"
    )


def render_upload(article: Article) -> str:
    """Variant that goes to the vector store.

    The store splits files into 800 token chunks, and retrieval often
    lands on a middle chunk. If that chunk has no "Article URL:" line
    the bot invents a url from training memory, so the line is repeated
    at the top, after every h2, and at the end - wherever the chunker
    cuts, the url is in context. updated_at is left out on purpose: it
    churns without real edits and would poison the content hash.
    """
    url_line = f"Article URL: {article.url}"
    body = to_markdown(article.body_html)
    body = re.sub(r"(?m)^(## .+)$", lambda m: f"{m.group(1)}\n\n{url_line}", body)
    return f"{url_line}\n\n# {article.title}\n\n{body}\n\n{url_line}\n"
