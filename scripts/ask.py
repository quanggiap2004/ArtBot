"""Ask the assistant a question from the command line.

    uv run python scripts/ask.py "How do I add a YouTube video?"
"""

import sys
import warnings

from dotenv import load_dotenv
from openai import OpenAI

from articlebots.citations import ensure_citation

# the assistants api is deprecated but required by the product spec;
# keep demo output free of the sdk's warning noise
warnings.filterwarnings("ignore", category=DeprecationWarning)

# file_search embeds citation markers like "【4:0†source】" directly in
# the reply text. Windows consoles default to cp1252, which can't encode
# them, so printing crashes without this.
sys.stdout.reconfigure(encoding="utf-8")

ASSISTANT_NAME = "OptiBot"


def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        sys.exit('usage: python scripts/ask.py "your question"')

    load_dotenv()
    client = OpenAI(timeout=120)

    assistant = next(
        (a for a in client.beta.assistants.list() if a.name == ASSISTANT_NAME), None
    )
    if assistant is None:
        sys.exit("assistant not found - run scripts/create_assistant.py first")

    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=question
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
        tool_choice={"type": "file_search"},
    )
    if run.status != "completed":
        sys.exit(f"run ended with status {run.status}: {run.last_error}")

    reply = client.beta.threads.messages.list(thread_id=thread.id)
    print(ensure_citation(client, reply.data[0]))


if __name__ == "__main__":
    main()
