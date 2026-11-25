from datetime import UTC, datetime, timedelta
from pathlib import Path

from cv_agent.ingestion.cv_parser import load_master_profile
from cv_agent.ingestion.job_finder import (
    build_hr_search_shortcuts,
    export_daily_snapshot,
    format_posted_age,
    is_relevant_data_role,
    score_and_enrich_jobs,
)
from cv_agent.storage.companies_db import CompanyKnowledgeDatabase
from cv_agent.storage.market_db import MarketDatabase

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "config" / "company_knowledge_seed.yaml"
PROFILE_PATH = ROOT / "data" / "master_profile.example.yaml"


def test_format_posted_age_labels() -> None:
    two_days_ago = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%d")
    label = format_posted_age(two_days_ago)
    assert "hari lalu" in label


def test_score_and_enrich_jobs_ranks_best_match_first(tmp_path: Path) -> None:
    profile = load_master_profile(PROFILE_PATH)
    cdb = CompanyKnowledgeDatabase(db_path=tmp_path / "kb.duckdb", seed_path=SEED_PATH)

    raw_jobs = [
        {
            "job_id": "j1",
            "source": "linkedin",
            "title": "Data Engineer",
            "company": "Bank Jago",
            "location": "Jakarta, Indonesia (Hybrid)",
            "job_url": "https://example.com/jago",
            "description": "Need Python, SQL, dbt, Apache Airflow, and Google BigQuery.",
            "posted_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        },
        {
            "job_id": "j2",
            "source": "remotive",
            "title": "Principal Scala Flink Architect",
            "company": "Random Corp",
            "location": "Worldwide Remote",
            "job_url": "https://example.com/random",
            "description": "Requires Scala, Apache Flink, Kubernetes, Terraform.",
            "posted_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        },
    ]

    ranked = score_and_enrich_jobs(raw_jobs, profile, cdb, ["Data Engineer"])
    assert len(ranked) == 2
    assert ranked[0].company == "Bank Jago"
    assert ranked[0].match_score > ranked[1].match_score
    assert ranked[0].company_verdict == "Recommended"
    assert "Rp" in ranked[0].company_salary_idr
    assert ranked[1].work_mode == "Remote"


def test_build_hr_search_shortcuts() -> None:
    profile = load_master_profile(PROFILE_PATH)
    shortcuts = build_hr_search_shortcuts(profile, ["Data Engineer", "Data Quality"])
    assert len(shortcuts) >= 4
    assert any("linkedin.com/search/results/content" in s.search_url for s in shortcuts)


def test_is_relevant_data_role_filters_noise() -> None:
    assert is_relevant_data_role("Senior Data Engineer") is True
    assert is_relevant_data_role("Data Quality Analyst") is True
    assert is_relevant_data_role("Analytics Engineer (dbt)") is True
    assert is_relevant_data_role("Roaster Operator") is False
    assert is_relevant_data_role("After-Sales Engineer (Data Center Power)") is False


def test_export_daily_snapshot_writes_parquet_and_json(tmp_path: Path) -> None:
    mdb = MarketDatabase(db_path=tmp_path / "daily.duckdb")
    out_dir = tmp_path / "snapshots"
    exported = export_daily_snapshot(mdb, snapshot_dir=out_dir)
    assert (out_dir / "market_summary.json").exists()
    assert isinstance(exported["total_jobs_exported"], int)
