"""Fetch articles from the Zendesk help center API."""

from dataclasses import dataclass

import httpx

BASE_URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
PER_PAGE = 100
TIMEOUT = 30.0


@dataclass
class Article:
    id: int
    title: str
    url: str
    body_html: str
    updated_at: str
    section_id: int


def fetch_articles(limit: int | None = None) -> list[Article]:
    """Walk the paginated article listing and return up to `limit` articles.

    Drafts are excluded. Articles come back in the API's default order,
    sorted here by id so runs are deterministic regardless of what the
    API decides to promote.
    """
    articles: list[Article] = []
    url: str | None = f"{BASE_URL}?per_page={PER_PAGE}"

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        while url:
            resp = client.get(url)
            resp.raise_for_status()
            payload = resp.json()

            for raw in payload["articles"]:
                if raw.get("draft"):
                    continue
                if not raw.get("body"):
                    continue
                articles.append(
                    Article(
                        id=raw["id"],
                        title=raw["title"],
                        url=raw["html_url"],
                        body_html=raw["body"],
                        updated_at=raw["updated_at"],
                        section_id=raw["section_id"],
                    )
                )

            url = payload.get("next_page")
            if limit is not None and len(articles) >= limit:
                break

    articles.sort(key=lambda a: a.id)
    if limit is not None:
        articles = articles[:limit]
    return articles
