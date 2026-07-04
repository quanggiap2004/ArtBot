"""One-off: create (or refresh) the assistant and point it at the store.

Kept separate from main.py on purpose - the daily job only syncs
documents, it never touches assistant configuration.
"""

import logging
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

ASSISTANT_NAME = "OptiBot"
MODEL = "gpt-4o"

# The first block is fixed by the product spec - do not edit it.
# The note below it exists because file_search replaces URLs with
# annotation markers unless the model is told to write them out.
INSTRUCTIONS = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply.

Formatting note: always search the uploaded docs before answering,
even when you already know the product - never answer from memory.
Each doc contains lines like
"Article URL: https://support.optisigns.com/...". To cite, copy that
line from the retrieved document into your reply as plain text on its
own line, character for character. Never write a URL from memory:
if the text you retrieved does not contain an Article URL line, say
the relevant doc exists but give no URL rather than guessing one.
Always include at least one "Article URL:" line in every reply, even
when the answer draws on more than one article - pick the single most
relevant source document and cite that one line, rather than omitting
a citation because several documents were relevant."""

log = logging.getLogger(__name__)


def find_store_id(client: OpenAI, name: str) -> str:
    for store in client.vector_stores.list():
        if store.name == name:
            return store.id
    sys.exit(f"vector store {name!r} not found - run main.py first")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv()
    client = OpenAI()
    store_id = find_store_id(
        client, os.environ.get("VECTOR_STORE_NAME", "articlebots-kb")
    )

    config = {
        "name": ASSISTANT_NAME,
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "tools": [{"type": "file_search"}],
        "tool_resources": {"file_search": {"vector_store_ids": [store_id]}},
    }
    for a in client.beta.assistants.list():
        if a.name == ASSISTANT_NAME:
            client.beta.assistants.update(a.id, **config)
            log.info("updated assistant %s -> store %s", a.id, store_id)
            print(a.id)
            return

    a = client.beta.assistants.create(**config)
    log.info("created assistant %s -> store %s", a.id, store_id)
    print(a.id)


if __name__ == "__main__":
    main()
