"""Guarantee a real Article URL line in every reply.

file_search always tells you which file it retrieved, via annotations on
the message, even on replies where the model itself never wrote out an
"Article URL:" line - that's the gap this closes. Prompt wording alone
never got the model to transcribe the line reliably (it kept settling
around 3 answers in 4 on questions that draw on several articles), so
this reads the retrieval results directly and appends the real URL
itself.

Two sources for the URL, tried in order:

1. The cited file's name (files.retrieve -> slug -> local front matter).
   Cheap, but fails on "zombie" citations: the index can keep serving
   chunks from a file whose File object an update cycle already deleted,
   and then files.retrieve 404s even though the citation is real.
2. The retrieved chunk text itself, from the run's file_search step.
   Every uploaded chunk carries its own "Article URL:" line (that is
   why render_upload() repeats it), so the URL can be parsed straight
   out of whatever text the model actually read. Works even for zombie
   citations.
"""

import re
from pathlib import Path

from openai import OpenAI

from articlebots.hashing import parse_remote_name

ARTICLES_DIR = Path("data/articles")
_HAS_ARTICLE_URL = re.compile(r"Article URL: https://\S+")
# current upload format first; the front-matter "url:" form covers chunks
# from zombie attachments that predate the render_upload() format change
_CHUNK_URL = re.compile(r"(?m)^(?:Article URL|url): (https://\S+)$")


def _local_url(slug: str) -> str | None:
    """Read the "url: ..." front-matter line out of data/articles/<slug>.md."""
    path = ARTICLES_DIR / f"{slug}.md"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines()[:10]:
        if line.startswith("url: "):
            return line.removeprefix("url: ").strip()
    return None


def _url_from_filename(client: OpenAI, file_id: str) -> str | None:
    """Resolve a citation via the file's name. 404s on zombie citations."""
    try:
        file = client.files.retrieve(file_id)
    except Exception:
        return None
    parsed = parse_remote_name(file.filename)
    if parsed is None:
        return None
    return _local_url(parsed[0])


def _urls_from_run_steps(client: OpenAI, message) -> dict[str, str]:
    """file_id -> url, parsed out of the chunks file_search actually read."""
    urls: dict[str, str] = {}
    if not (message.run_id and message.thread_id):
        return urls
    try:
        steps = client.beta.threads.runs.steps.list(
            thread_id=message.thread_id,
            run_id=message.run_id,
            include=["step_details.tool_calls[*].file_search.results[*].content"],
        )
    except Exception:
        return urls
    for step in steps:
        for call in getattr(step.step_details, "tool_calls", None) or []:
            search = getattr(call, "file_search", None)
            for result in getattr(search, "results", None) or []:
                if result.file_id in urls:
                    continue
                text = "".join(
                    c.text for c in result.content or [] if c.type == "text"
                )
                m = _CHUNK_URL.search(text)
                if m:
                    urls[result.file_id] = m.group(1)
    return urls


def ensure_citation(client: OpenAI, message) -> str:
    """Return the reply text, with a real Article URL line appended if
    the model's own text is missing one but file_search did cite a file.
    """
    block = message.content[0].text
    reply = block.value
    if _HAS_ARTICLE_URL.search(reply):
        return reply

    cited_ids: list[str] = []
    for annotation in block.annotations:
        citation = getattr(annotation, "file_citation", None)
        if citation and citation.file_id not in cited_ids:
            cited_ids.append(citation.file_id)
    if not cited_ids:
        return reply  # nothing was cited - a refusal, say - nothing to add

    chunk_urls: dict[str, str] | None = None  # fetched lazily, one call at most
    urls: list[str] = []
    for file_id in cited_ids:
        url = _url_from_filename(client, file_id)
        if url is None:
            if chunk_urls is None:
                chunk_urls = _urls_from_run_steps(client, message)
            url = chunk_urls.get(file_id)
        if url and url not in urls:
            urls.append(url)

    if not urls:
        return reply
    return reply + "\n\n" + "\n".join(f"Article URL: {u}" for u in urls)
