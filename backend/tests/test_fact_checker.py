from pathlib import Path

from cv_agent.agent.critic import run_deterministic_fact_check
from cv_agent.ingestion.cv_parser import load_master_profile
from cv_agent.schemas import TailoredBullet, TailoredCV, TailoredExperience
from cv_agent.storage.market_db import MarketDatabase

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PROFILE = ROOT / "data" / "master_profile.example.yaml"
TAXONOMY_PATH = ROOT / "config" / "skills_taxonomy.yaml"
RULES_PATH = ROOT / "config" / "ats_rules.yaml"


def test_fact_checker_passes_grounded_cv() -> None:
    profile = load_master_profile(EXAMPLE_PROFILE)
    snapshot = MarketDatabase.seed_benchmark_snapshot("Data Engineer", "Indonesia")

    tailored = TailoredCV(
        target_role="Data Engineer",
        output_language="en",
        professional_summary=(
            "Data Engineer with 2.5 years of experience building Python, SQL, dbt, "
            "and Apache Airflow pipelines on Google BigQuery."
        ),
        grouped_skills=profile.skills_verified,
        experiences=[
            TailoredExperience(
                id="exp_01",
                company="PT Nusantara Retail Analytics",
                role="Data Engineer",
                start_date="2024-01",
                end_date="present",
                bullets=[
                    TailoredBullet(
                        source_id="exp_01_b1",
                        original_text=profile.experiences[0].bullets[0].raw_fact,
                        rewritten_text=(
                            "Architected Python and Apache Airflow ELT pipelines into BigQuery "
                            "processing 12M+ daily rows and cutting latency from 4 hours "
                            "to 40 minutes."
                        ),
                        tools_referenced=["Python", "Apache Airflow", "Google BigQuery"],
                    )
                ],
            )
        ],
        projects=profile.projects,
    )

    result = run_deterministic_fact_check(
        master_profile=profile,
        tailored_cv=tailored,
        market_snapshot=snapshot,
        taxonomy_path=TAXONOMY_PATH,
        rules_path=RULES_PATH,
    )
    assert result.passed is True
    assert result.ats_score > 0


def test_fact_checker_catches_hallucinated_skill_and_metric() -> None:
    profile = load_master_profile(EXAMPLE_PROFILE)
    snapshot = MarketDatabase.seed_benchmark_snapshot("Data Engineer", "Indonesia")

    tailored = TailoredCV(
        target_role="Data Engineer",
        output_language="en",
        professional_summary="Data Engineer.",
        grouped_skills={"streaming": ["Apache Kafka"]},  # Not in MasterProfile!
        experiences=[
            TailoredExperience(
                id="exp_01",
                company="PT Nusantara Retail Analytics",
                role="Data Engineer",
                start_date="2024-01",
                end_date="present",
                bullets=[
                    TailoredBullet(
                        source_id="exp_01_b1",
                        original_text="raw",
                        rewritten_text=(
                            "Built Kubernetes and Apache Kafka pipelines that saved 99% cloud cost."
                        ),
                        tools_referenced=["Kubernetes", "Apache Kafka"],
                    )
                ],
            )
        ],
        projects=[],
    )

    result = run_deterministic_fact_check(
        master_profile=profile,
        tailored_cv=tailored,
        market_snapshot=snapshot,
        taxonomy_path=TAXONOMY_PATH,
        rules_path=RULES_PATH,
    )
    rules_triggered = {v.rule for v in result.violations}
    assert result.passed is False
    assert "unverified_skill" in rules_triggered
    assert "hallucinated_tool_in_bullet" in rules_triggered
    assert "ungrounded_metric" in rules_triggered
