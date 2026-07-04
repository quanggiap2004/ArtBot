"""Scrape the help center, convert to markdown, sync the delta to OpenAI.

Runs once and exits: 0 on success, 1 on failure. Meant to be executed
daily by a scheduler (Render cron in our case).
"""

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from articlebots.convert import article_slug, render_article, render_upload
from articlebots.diff import classify
from articlebots.hashing import content_hash
from articlebots.scraper import Article, fetch_articles
from articlebots.vectorstore import VectorStoreClient

ARTICLES_DIR = Path("data/articles")

log = logging.getLogger("articlebots")


def prepare_local(articles: list[Article]) -> dict[str, tuple[str, str]]:
    """slug -> (hash8, full file text). Also writes data/articles/*.md."""
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    local: dict[str, tuple[str, str]] = {}
    for art in articles:
        slug = article_slug(art)
        if slug in local:  # two titles can slugify identically
            slug = f"{slug}-{art.id}"
        upload_text = render_upload(art)
        digest = content_hash(upload_text)
        (ARTICLES_DIR / f"{slug}.md").write_text(render_article(art), encoding="utf-8")
        local[slug] = (digest, upload_text)
    return local


def run() -> int:
    load_dotenv()
    store_name = os.environ.get("VECTOR_STORE_NAME", "articlebots-kb")
    limit = int(os.environ.get("ARTICLE_LIMIT", "0")) or None  # 0 = everything

    articles = fetch_articles(limit=limit)
    log.info("fetched %d articles", len(articles))

    local = prepare_local(articles)

    # default timeout is 600s, which turns one dead connection into a
    # 10 minute stall - fail fast and let the SDK retry instead
    store = VectorStoreClient(OpenAI(timeout=60.0, max_retries=5), store_name)
    remote = store.remote_state()
    log.info("store has %d tracked files", len(remote))

    plan = classify(
        {slug: digest for slug, (digest, _) in local.items()},
        {slug: digest for slug, (digest, _) in remote.items()},
    )

    def push(slug: str) -> None:
        digest, text = local[slug]
        store.upload(slug, digest, text)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for slug in plan.updated:  # detach stale versions first
            store.remove(remote[slug][1])
        for slug, fut in [(s, pool.submit(push, s)) for s in plan.added + plan.updated]:
            fut.result()
            verb = "added" if slug in plan.added else "updated"
            log.info("%s %s (%s)", verb, slug, local[slug][0])

    if plan.added or plan.updated:
        store.wait_until_indexed()

    files, used_bytes = store.chunk_stats()
    log.info("store now holds %d files, %d bytes indexed", files, used_bytes)
    print(plan.summary(), flush=True)
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        sys.exit(run())
    except Exception:
        log.exception("sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
