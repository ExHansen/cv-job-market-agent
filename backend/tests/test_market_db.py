from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.storage.market_db import MarketDatabase

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = ROOT / "config" / "skills_taxonomy.yaml"


def test_market_db_upsert_and_aggregation(tmp_path: Path) -> None:
    db = MarketDatabase(db_path=tmp_path / "test_market.duckdb")
    extractor = SkillTaxonomyExtractor(taxonomy_path=TAXONOMY_PATH)

    df = pd.DataFrame(
        [
            {
                "job_id": "job_1",
                "source": "linkedin",
                "search_role": "Data Engineer",
                "title": "Senior Data Engineer",
                "company": "Alpha Tech",
                "location": "Jakarta, Indonesia",
                "job_url": "https://example.com/1",
                "description": (
                    "Looking for Python, SQL, dbt, Apache Airflow, and Apache Iceberg on BigQuery."
                ),
                "posted_at": "2026-11-24",
                "scraped_at": datetime.now(UTC).isoformat(),
            },
            {
                "job_id": "job_2",
                "source": "indeed",
                "search_role": "Data Engineer",
                "title": "Data Engineer",
                "company": "Beta Commerce",
                "location": "Remote",
                "job_url": "https://example.com/2",
                "description": (
                    "Strong Python, SQL, Snowflake, Docker, and Airflow experience required."
                ),
                "posted_at": "2026-11-24",
                "scraped_at": datetime.now(UTC).isoformat(),
            },
        ]
    )

    inserted = db.upsert_jobs(df, extractor=extractor)
    assert inserted == 2

    snap = db.get_market_snapshot(role="Data Engineer", region="Indonesia")
    assert snap.sample_size == 2
    top_names = {s.skill for s in snap.top_mandatory_skills}
    assert {"Python", "SQL", "Apache Airflow"}.issubset(top_names)


def test_auto_sync_from_daily_parquet_snapshot(tmp_path: Path) -> None:
    """Verify incremental Parquet-to-DuckDB sync after simulated `git pull` updates."""
    db = MarketDatabase(db_path=tmp_path / "sync_market.duckdb")
    extractor = SkillTaxonomyExtractor(taxonomy_path=TAXONOMY_PATH)
    snapshot_file = tmp_path / "jobs_latest.parquet"

    # Day 1 snapshot
    day1_df = pd.DataFrame(
        [
            {
                "job_id": "snap_1",
                "source": "remotive_remote",
                "search_role": "Data Engineer",
                "title": "Senior Data Engineer",
                "company": "CloudScale",
                "location": "Remote",
                "job_url": "https://example.com/snap1",
                "description": "Python, SQL, dbt, and DuckDB pipeline engineering.",
                "posted_at": "2026-11-24",
                "scraped_at": datetime.now(UTC).isoformat(),
            }
        ]
    )
    day1_df.to_parquet(snapshot_file, index=False)

    synced_first = db.sync_from_daily_snapshot(snapshot_path=snapshot_file, extractor=extractor)
    assert synced_first == 1
    assert len(db.list_recent_postings(limit=10)) == 1

    # Unchanged snapshot should be an O(1) no-op
    synced_noop = db.sync_from_daily_snapshot(snapshot_path=snapshot_file, extractor=extractor)
    assert synced_noop == 0

    # Day 2 snapshot after `git pull` adds a new posting
    day2_df = pd.DataFrame(
        [
            day1_df.iloc[0].to_dict(),
            {
                "job_id": "snap_2",
                "source": "linkedin",
                "search_role": "Data Engineer",
                "title": "Analytics Engineer",
                "company": "Nusantara Fintech",
                "location": "Jakarta, Indonesia",
                "job_url": "https://example.com/snap2",
                "description": "BigQuery, dbt, Dagster, Python, SQL.",
                "posted_at": "2026-11-25",
                "scraped_at": datetime.now(UTC).isoformat(),
            },
        ]
    )
    day2_df.to_parquet(snapshot_file, index=False)

    synced_second = db.sync_from_daily_snapshot(snapshot_path=snapshot_file, extractor=extractor)
    assert synced_second == 2
    assert len(db.list_recent_postings(limit=10)) == 2
    status = db.get_snapshot_sync_status()
    assert status["source_key"] == "jobs_latest.parquet"
    assert status["last_synced_rows"] == 2
    assert status["sha256_prefix"] is not None
