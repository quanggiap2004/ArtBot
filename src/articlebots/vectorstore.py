"""Thin wrapper around the OpenAI vector store endpoints.

Each attached file carries {"slug": ..., "hash": ...} attributes, set when
the file is attached. Listing the store therefore gives us the full remote
state in one paginated call - no local database, no filename parsing.
The uploaded filename still follows <slug>__<hash8>.md so the state is
also visible by eye in the OpenAI dashboard.
"""

import logging
import time

from openai import OpenAI

from articlebots.hashing import remote_name

log = logging.getLogger(__name__)


class VectorStoreClient:
    def __init__(self, client: OpenAI, store_name: str):
        self.client = client
        self.store_id = self._find_or_create(store_name)

    def _find_or_create(self, name: str) -> str:
        for store in self.client.vector_stores.list():
            if store.name == name:
                log.info("using vector store %s (%s)", name, store.id)
                return store.id
        store = self.client.vector_stores.create(name=name)
        log.info("created vector store %s (%s)", name, store.id)
        return store.id

    def remote_state(self) -> dict[str, tuple[str, str]]:
        """slug -> (hash8, file_id) for every file we previously attached.

        Detaching a file right after deleting its file object sometimes
        doesn't stick on OpenAI's side, so a slug can show several
        attachments. We treat the newest one as truth and detach the
        rest here, which makes every run clean up after the last one.
        """
        newest: dict[str, tuple[int, str, str]] = {}
        stale: list[str] = []
        for f in self.client.vector_stores.files.list(vector_store_id=self.store_id):
            attrs = f.attributes or {}
            slug, digest = attrs.get("slug"), attrs.get("hash")
            if not (slug and digest):
                log.warning("detaching foreign file %s", f.id)
                stale.append(f.id)
                continue
            slug = str(slug)
            if slug in newest:
                older = min(newest[slug], (f.created_at, str(digest), f.id))
                stale.append(older[2])
            if slug not in newest or f.created_at > newest[slug][0]:
                newest[slug] = (f.created_at, str(digest), f.id)
        for file_id in stale:
            self.detach(file_id)
        if stale:
            log.info("detached %d stale attachments", len(stale))
        return {slug: (digest, fid) for slug, (_, digest, fid) in newest.items()}

    def detach(self, file_id: str) -> None:
        self.client.vector_stores.files.delete(
            file_id=file_id, vector_store_id=self.store_id
        )

    def upload(self, slug: str, digest: str, content: str) -> str:
        """Upload one article and attach it, without waiting for embedding.

        Embedding runs server-side; call wait_until_indexed() once after
        the last upload instead of polling per file.
        """
        file = self.client.files.create(
            file=(remote_name(slug, digest), content.encode("utf-8")),
            purpose="assistants",
        )
        self.client.vector_stores.files.create(
            vector_store_id=self.store_id,
            file_id=file.id,
            attributes={"slug": slug, "hash": digest},
        )
        return file.id

    def wait_until_indexed(self, timeout: float = 900.0) -> None:
        """Block until the store has no files left in progress."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            counts = self.client.vector_stores.retrieve(self.store_id).file_counts
            if counts.in_progress == 0:
                if counts.failed:
                    raise RuntimeError(f"{counts.failed} files failed to embed")
                return
            log.info("indexing: %d in progress", counts.in_progress)
            time.sleep(5)
        raise TimeoutError("vector store still indexing after %ss" % timeout)

    def remove(self, file_id: str) -> None:
        """Detach from the store and delete the underlying file.

        Detach must settle before the file object goes away - deleting
        the file first is what caused the zombie attachments above.
        """
        self.detach(file_id)
        try:
            self.client.files.delete(file_id)
        except Exception:  # already gone - nothing to clean up
            log.warning("file object %s was already deleted", file_id)

    def chunk_stats(self) -> tuple[int, int]:
        """(file_count, total_bytes_used) straight from the store."""
        store = self.client.vector_stores.retrieve(self.store_id)
        return store.file_counts.completed, store.usage_bytes
