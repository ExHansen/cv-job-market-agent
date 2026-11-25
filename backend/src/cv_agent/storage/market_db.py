import hashlib
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from cv_agent.config import settings
from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.schemas import MarketSnapshot, SkillFrequency


class MarketDatabase:
    """Embedded DuckDB analytical warehouse with automatic Parquet snapshot sync."""

    def __init__(self, db_path: Path | None = None) -> None:
        is_default_db = db_path is None
        self.db_path = db_path or settings.duckdb_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        if is_default_db:
            self.sync_from_daily_snapshot()

    def sync_from_daily_snapshot(
        self,
        snapshot_path: Path | None = None,
        extractor: SkillTaxonomyExtractor | None = None,
    ) -> int:
        """Auto-sync committed daily Parquet snapshot from GitHub Actions whenever it changes.

        Triggered automatically after `git pull` on the default local DuckDB without needing
        manual re-import or server restarts. Uses file stat + SHA256 change detection so
        repeated calls are O(1) when the snapshot has not changed.
        """
        snapshot_parquet = (
            snapshot_path or settings.data_dir / "snapshots" / "daily" / "jobs_latest.parquet"
        )
        if not snapshot_parquet.exists():
            return 0

        try:
            stat = snapshot_parquet.stat()
            source_key = snapshot_parquet.name
            with self._connect() as con:
                count_row = con.execute("SELECT COUNT(*) FROM job_postings").fetchone()
                existing_count = int(count_row[0]) if count_row and count_row[0] else 0
                state_row = con.execute(
                    """
                    SELECT file_sha256, file_mtime, file_size
                    FROM snapshot_sync_state
                    WHERE source_key = ?
                    """,
                    [source_key],
                ).fetchone()

            if (
                existing_count > 0
                and state_row
                and state_row[1] == stat.st_mtime
                and state_row[2] == stat.st_size
            ):
                return 0

            file_sha256 = hashlib.sha256(snapshot_parquet.read_bytes()).hexdigest()
            if existing_count > 0 and state_row and state_row[0] == file_sha256:
                with self._connect() as con:
                    con.execute(
                        """
                        UPDATE snapshot_sync_state
                        SET file_mtime = ?, file_size = ?
                        WHERE source_key = ?
                        """,
                        [stat.st_mtime, stat.st_size, source_key],
                    )
                return 0

            df = pd.read_parquet(snapshot_parquet)
            synced = self.upsert_jobs(df, extractor=extractor) if not df.empty else 0
            with self._connect() as con:
                con.execute(
                    """
                    INSERT OR REPLACE INTO snapshot_sync_state
                    (source_key, file_sha256, file_mtime, file_size, row_count, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        source_key,
                        file_sha256,
                        stat.st_mtime,
                        stat.st_size,
                        synced,
                        datetime.now(UTC),
                    ],
                )
            return synced
        except Exception:
            return 0

    def get_snapshot_sync_status(self) -> dict[str, str | int | None]:
        """Return metadata about the latest automatic Parquet-to-DuckDB snapshot sync."""
        with self._connect() as con:
            row = con.execute(
                """
                SELECT source_key, file_sha256, row_count, synced_at
                FROM snapshot_sync_state
                ORDER BY synced_at DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return {
                "source_key": None,
                "sha256_prefix": None,
                "last_synced_rows": 0,
                "synced_at": None,
            }
        return {
            "source_key": str(row[0]),
            "sha256_prefix": str(row[1])[:12] if row[1] else None,
            "last_synced_rows": int(row[2] or 0),
            "synced_at": str(row[3]) if row[3] else None,
        }

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS job_postings (
                    job_id VARCHAR PRIMARY KEY,
                    source VARCHAR,
                    search_role VARCHAR,
                    title VARCHAR,
                    company VARCHAR,
                    location VARCHAR,
                    job_url VARCHAR,
                    description VARCHAR,
                    posted_at VARCHAR,
                    scraped_at TIMESTAMP
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS job_skills (
                    job_id VARCHAR,
                    skill_canonical VARCHAR,
                    category VARCHAR,
                    PRIMARY KEY (job_id, skill_canonical)
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshot_sync_state (
                    source_key VARCHAR PRIMARY KEY,
                    file_sha256 VARCHAR,
                    file_mtime DOUBLE,
                    file_size BIGINT,
                    row_count INTEGER,
                    synced_at TIMESTAMP
                );
                """
            )

    def upsert_jobs(
        self,
        jobs_df: pd.DataFrame,
        extractor: SkillTaxonomyExtractor | None = None,
    ) -> int:
        """Upsert raw postings and populate Stage-1 extracted skills."""
        if jobs_df.empty:
            return 0

        skill_extractor = extractor or SkillTaxonomyExtractor()
        skill_rows: list[dict[str, str]] = []
        for _, row in jobs_df.iterrows():
            combined_text = f"{row.get('title', '')}\n{row.get('description', '')}"
            for skill in skill_extractor.extract(combined_text):
                skill_rows.append(
                    {
                        "job_id": str(row["job_id"]),
                        "skill_canonical": skill.canonical,
                        "category": skill.category,
                    }
                )

        with self._connect() as con:
            con.register("incoming_jobs", jobs_df)
            con.execute(
                """
                INSERT OR REPLACE INTO job_postings
                SELECT
                    job_id,
                    source,
                    search_role,
                    title,
                    company,
                    location,
                    job_url,
                    description,
                    posted_at,
                    CAST(scraped_at AS TIMESTAMP)
                FROM incoming_jobs;
                """
            )

            if skill_rows:
                skills_df = pd.DataFrame(skill_rows).drop_duplicates()
                con.register("incoming_skills", skills_df)
                con.execute(
                    """
                    INSERT OR REPLACE INTO job_skills
                    SELECT job_id, skill_canonical, category
                    FROM incoming_skills;
                    """
                )
        return len(jobs_df)

    def find_company_job(
        self,
        company_name: str,
        role: str = "",
    ) -> tuple[str, str, str] | None:
        """Look up the latest stored job description for a specific target company in DuckDB."""
        with self._connect() as con:
            row = con.execute(
                """
                SELECT title, job_url, description
                FROM job_postings
                WHERE lower(company) LIKE lower(?)
                  AND (lower(title) LIKE lower(?) OR ? = '')
                ORDER BY scraped_at DESC
                LIMIT 1
                """,
                [f"%{company_name}%", f"%{role}%", role],
            ).fetchone()
        if not row:
            return None
        return str(row[0] or ""), str(row[1] or ""), str(row[2] or "")

    def list_recent_postings(self, limit: int = 30) -> list[dict]:
        """Return recently stored job postings from DuckDB."""
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT job_id, source, search_role, title, company, location,
                       job_url, description, posted_at, scraped_at
                FROM job_postings
                ORDER BY scraped_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()
        return [
            {
                "job_id": str(r[0]),
                "source": str(r[1] or ""),
                "search_role": str(r[2] or ""),
                "title": str(r[3] or ""),
                "company": str(r[4] or ""),
                "location": str(r[5] or ""),
                "job_url": str(r[6] or ""),
                "description": str(r[7] or ""),
                "posted_at": str(r[8] or ""),
                "scraped_at": str(r[9] or ""),
            }
            for r in rows
        ]

    def get_market_snapshot(self, role: str, region: str = "Indonesia") -> MarketSnapshot:
        """Aggregate skill frequency stats from DuckDB (Gold-layer equivalent)."""
        with self._connect() as con:
            sample_row = con.execute(
                """
                SELECT COUNT(*), MAX(scraped_at)
                FROM job_postings
                WHERE lower(search_role) LIKE lower(?) OR lower(title) LIKE lower(?)
                """,
                [f"%{role}%", f"%{role}%"],
            ).fetchone()

            sample_size = int(sample_row[0]) if sample_row and sample_row[0] else 0
            latest_ts = sample_row[1] if sample_row and sample_row[1] else datetime.now(UTC)

            if sample_size == 0:
                return self.seed_benchmark_snapshot(role=role, region=region)

            skill_rows = con.execute(
                """
                SELECT
                    s.skill_canonical,
                    s.category,
                    COUNT(DISTINCT s.job_id) AS job_count,
                    ROUND(COUNT(DISTINCT s.job_id) * 100.0 / ?, 1) AS freq_pct
                FROM job_skills s
                JOIN job_postings p ON p.job_id = s.job_id
                WHERE lower(p.search_role) LIKE lower(?) OR lower(p.title) LIKE lower(?)
                GROUP BY s.skill_canonical, s.category
                ORDER BY job_count DESC
                LIMIT 25
                """,
                [sample_size, f"%{role}%", f"%{role}%"],
            ).fetchall()

            source_rows = con.execute(
                """
                SELECT source, COUNT(*)
                FROM job_postings
                WHERE lower(search_role) LIKE lower(?) OR lower(title) LIKE lower(?)
                GROUP BY source
                """,
                [f"%{role}%", f"%{role}%"],
            ).fetchall()

        mandatory: list[SkillFrequency] = []
        rising: list[SkillFrequency] = []
        for canonical, category, count, pct in skill_rows:
            item = SkillFrequency(
                skill=canonical,
                category=category,
                job_count=int(count),
                frequency_pct=float(pct),
            )
            if pct >= 40.0:
                mandatory.append(item)
            else:
                rising.append(item)

        return MarketSnapshot(
            role=role,
            region=region,
            snapshot_date=latest_ts if isinstance(latest_ts, datetime) else datetime.now(UTC),
            sample_size=sample_size,
            top_mandatory_skills=mandatory,
            rising_skills=rising,
            source_breakdown={str(src): int(cnt) for src, cnt in source_rows},
        )

    @staticmethod
    def seed_benchmark_snapshot(
        role: str = "Data Engineer",
        region: str = "Indonesia",
    ) -> MarketSnapshot:
        """Fallback curated benchmark snapshot so the UI & agent work before first live scrape."""
        def _sf(skill: str, category: str, count: int) -> SkillFrequency:
            return SkillFrequency(
                skill=skill,
                category=category,
                job_count=count,
                frequency_pct=float(count),
            )

        mandatory = [
            _sf("SQL", "language", 96),
            _sf("Python", "language", 92),
            _sf("Apache Airflow", "orchestration", 67),
            _sf("dbt", "transformation", 55),
            _sf("PySpark", "processing", 51),
            _sf("Google BigQuery", "warehouse", 46),
            _sf("Docker", "dataops", 44),
            _sf("Dimensional Modeling", "modeling", 42),
        ]
        rising = [
            _sf("Snowflake", "warehouse", 38),
            _sf("Apache Kafka", "streaming", 32),
            _sf("Terraform", "dataops", 29),
            _sf("Apache Iceberg", "lakehouse", 25),
            _sf("Data Quality", "governance", 24),
            _sf("Dagster", "orchestration", 19),
        ]
        return MarketSnapshot(
            role=role,
            region=region,
            snapshot_date=datetime.now(UTC),
            sample_size=100,
            top_mandatory_skills=mandatory,
            rising_skills=rising,
            source_breakdown={"benchmark_seed": 100},
        )
