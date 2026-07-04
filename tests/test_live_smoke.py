"""End-to-end check against the real assistant. Costs a few cents.

Excluded by default (see pytest config). Run with:
    uv run pytest -m live
"""

import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

from articlebots.citations import ensure_citation

load_dotenv()

pytestmark = pytest.mark.live

QUESTION = "How do I add a YouTube video?"


@pytest.fixture(scope="module")
def client():
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    from openai import OpenAI

    return OpenAI()


@pytest.fixture(scope="module")
def assistant_id(client):
    for a in client.beta.assistants.list():
        if a.name == "OptiBot":
            return a.id
    pytest.skip("assistant not created yet - run scripts/create_assistant.py")


def corpus_urls() -> set[str]:
    """Every article url we actually uploaded, read from front matter."""
    urls = set()
    for path in Path("data/articles").glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines()[:8]:
            if line.startswith("url: "):
                urls.add(line.removeprefix("url: ").strip())
                break
    return urls


def ask_once(client, assistant_id) -> str:
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=QUESTION
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        tool_choice={"type": "file_search"},  # skipping the search = hallucinated urls
    )
    assert run.status == "completed", run.last_error
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    return ensure_citation(client, messages.data[0])


def test_assistant_answers_with_citation(client, assistant_id):
    """Model output varies run to run, so this allows three attempts.

    An attempt passes when the answer is on topic, cites at least one
    literal "Article URL:" line, and every cited url is one we actually
    uploaded. A url that 404s is worse than no citation at all - that is
    exactly the bug this test exists to catch.
    """
    known = corpus_urls()
    failures = []
    for _ in range(3):
        reply = ask_once(client, assistant_id)
        # stop at whitespace, annotation markers and markdown link closers
        cited = re.findall(r"https://support\.optisigns\.com/[^\s【)\]]+", reply)
        fake = [u for u in cited if u.rstrip(".,") not in known]
        assert not fake, f"hallucinated url(s): {fake}\nreply:\n{reply}"
        if "youtube" in reply.lower() and "Article URL:" in reply and cited:
            return
        failures.append(reply[-300:])
    raise AssertionError(
        "no attempt produced a literal Article URL citation:\n---\n"
        + "\n---\n".join(failures)
    )
