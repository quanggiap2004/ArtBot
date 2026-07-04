"""Content hashing and the slug__hash8 naming used in the vector store.

Local files are plain <slug>.md so git diffs stay readable; uploads are
named <slug>__<hash8>.md instead. Sync state itself travels in each
file's {slug, hash} attributes (see vectorstore.py). The filename
repeats that information so it can be read by eye in the OpenAI
dashboard, and so citations.py can recover a slug when resolving a
cited file back to its article.
"""

import hashlib
import re

_REMOTE_NAME = re.compile(r"^(?P<slug>.+)__(?P<hash>[0-9a-f]{8})\.md$")


def content_hash(markdown_body: str) -> str:
    """First 8 hex chars of the sha256 of the converted body.

    The front matter is deliberately left out: Zendesk bumps updated_at
    on edits that don't change the visible article, and re-embedding an
    identical body every time that happens is wasted work.
    """
    return hashlib.sha256(markdown_body.encode("utf-8")).hexdigest()[:8]


def remote_name(slug: str, digest: str) -> str:
    return f"{slug}__{digest}.md"


def parse_remote_name(filename: str) -> tuple[str, str] | None:
    """(slug, hash) from an uploaded filename, or None for foreign files."""
    m = _REMOTE_NAME.match(filename)
    if not m:
        return None
    return m.group("slug"), m.group("hash")
