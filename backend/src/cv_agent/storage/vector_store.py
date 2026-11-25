from pathlib import Path
from typing import Any

from cv_agent.config import settings
from cv_agent.llm import get_embeddings


class JobVectorStore:
    """Embedded LanceDB semantic search wrapper for matching projects against JDs."""

    TABLE_NAME = "job_descriptions"

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.lancedb_path

    def _connect(self) -> Any:
        try:
            import lancedb
        except ImportError as exc:
            raise RuntimeError(
                "lancedb is not installed. Run `uv sync --extra vector` to enable semantic search."
            ) from exc
        self.db_path.mkdir(parents=True, exist_ok=True)
        return lancedb.connect(str(self.db_path))

    def index_jobs(self, records: list[dict[str, str]]) -> int:
        """Embed and store job postings into LanceDB."""
        if not records:
            return 0
        embedder = get_embeddings()
        texts = [f"{r.get('title', '')}\n{r.get('description', '')[:4000]}" for r in records]
        vectors = embedder.embed_documents(texts)

        rows = [
            {
                "job_id": r["job_id"],
                "title": r.get("title", ""),
                "company": r.get("company", ""),
                "text": texts[i],
                "vector": vectors[i],
            }
            for i, r in enumerate(records)
        ]

        db = self._connect()
        if self.TABLE_NAME in db.table_names():
            table = db.open_table(self.TABLE_NAME)
            table.add(rows)
        else:
            db.create_table(self.TABLE_NAME, data=rows)
        return len(rows)

    def search_similar_jobs(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve top-k semantically similar JDs for a given user profile or bullet."""
        db = self._connect()
        if self.TABLE_NAME not in db.table_names():
            return []
        embedder = get_embeddings()
        query_vec = embedder.embed_query(query)
        table = db.open_table(self.TABLE_NAME)
        return list(table.search(query_vec).limit(limit).to_list())
