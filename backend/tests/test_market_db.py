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
