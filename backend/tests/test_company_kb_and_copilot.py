from pathlib import Path

from cv_agent.agent.career_copilot import gather_copilot_context
from cv_agent.ingestion.cv_parser import load_master_profile
from cv_agent.storage.applications_db import ApplicationsDatabase
from cv_agent.storage.companies_db import CompanyKnowledgeDatabase, CompanyKnowledgeRecord
from cv_agent.storage.market_db import MarketDatabase

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "config" / "company_knowledge_seed.yaml"
PROFILE_PATH = ROOT / "data" / "master_profile.example.yaml"


def test_company_kb_auto_seeds_and_supports_upsert(tmp_path: Path) -> None:
    db = CompanyKnowledgeDatabase(
        db_path=tmp_path / "kb.duckdb",
        seed_path=SEED_PATH,
    )
    all_records = db.list_companies()
    assert len(all_records) >= 8

    jago = db.find_company("Bank Jago")
    assert jago is not None
    assert "Rp" in jago.salary_idr_mid
    assert len(jago.positives) >= 2
    assert len(jago.kesah_kesuh) >= 2

    # User adds custom company review data (e.g., from Glassdoor/JobStreet notes)
    custom = db.upsert_company(
        CompanyKnowledgeRecord(
            company_name="Flip",
            industry="Fintech / Payments",
            overall_rating=4.2,
            work_life_balance=4.1,
            verdict="Recommended",
            positives=["Budaya kolaboratif dan produk fintech besar"],
            kesah_kesuh=["Target growth ketat"],
            salary_idr_mid="Rp 15.000.000 – Rp 24.000.000 / bulan",
        )
    )
    assert custom.company_name == "Flip"
    assert db.find_company("Flip") is not None


def test_copilot_gathers_system_and_company_context(tmp_path: Path) -> None:
    db_path = tmp_path / "copilot.duckdb"
    company_db = CompanyKnowledgeDatabase(db_path=db_path, seed_path=SEED_PATH)
    market_db = MarketDatabase(db_path=db_path)
    apps_db = ApplicationsDatabase(db_path=db_path)
    profile = load_master_profile(PROFILE_PATH)

    context_blob, sources = gather_copilot_context(
        user_query="Bandingkan Shopee vs Bank Jago dong, mana yang lebih bagus dan gajinya berapa?",
        profile=profile,
        company_db=company_db,
        market_db=market_db,
        apps_db=apps_db,
    )
    assert "Bank Jago" in context_blob
    assert "Shopee Indonesia" in context_blob
    assert "Keluh Kesah" in context_blob
    assert any("DuckDB Company KB" in s for s in sources)
