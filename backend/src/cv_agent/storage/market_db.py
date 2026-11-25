from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from cv_agent.config import settings
from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.schemas import MarketSnapshot, SkillFrequency


class MarketDatabase:
    """Embedded DuckDB analytical warehouse structured cleanly for future dbt-duckdb migration."""

    def __init__(self, db_path: Path | None = None) -> None:
        is_default_db = db_path is None
        self.db_path = db_path or settings.duckdb_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        if is_default_db:
            self._bootstrap_from_daily_snapshot()

    def _bootstrap_from_daily_snapshot(self) -> None:
        """Auto-load committed daily Parquet snapshot from GitHub Actions if DuckDB is empty."""
        snapshot_parquet = settings.data_dir / "snapshots" / "daily" / "jobs_latest.parquet"
        if not snapshot_parquet.exists():
            return
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) FROM job_postings").fetchone()
            count = int(row[0]) if row and row[0] else 0
        if count == 0:
            try:
                df = pd.read_parquet(snapshot_parquet)
                if not df.empty:
                    self.upsert_jobs(df)
            except Exception:
                pass

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
