from pathlib import Path

from cv_agent.agent.company_deep_dive import generate_company_deep_dive
from cv_agent.agent.graph import _rank_projects_for_target
from cv_agent.ingestion.company_research import (
    _extract_linkedin_guest_job,
    infer_industry,
    normalize_job_url,
    research_company_and_jd,
    strip_html,
)
from cv_agent.ingestion.cv_parser import load_master_profile
from cv_agent.schemas import CompanyIntel

ROOT = Path(__file__).resolve().parents[2]
MASTER_PROFILE = ROOT / "data" / "master_profile.yaml"


def test_normalize_linkedin_search_results_url() -> None:
    raw = (
        "https://www.linkedin.com/jobs/search-results/"
        "?currentJobId=4491875867&keywords=Data%20Quality%20Analyst&geoId=90010101"
    )
    canonical, role_hint = normalize_job_url(raw)
    assert canonical == "https://www.linkedin.com/jobs/view/4491875867/"
    assert role_hint == "Data Quality Analyst"


def test_extract_linkedin_guest_job_html() -> None:
    sample_html = (
        "<html><head>"
        "<title>Data Engineer at FIT HUB — Jakarta, Indonesia | LinkedIn Jobs</title>"
        "</head><body>"
        '<div class="show-more-less-html__markup">'
        "FIT HUB is a health and wellness startup building BigQuery, dbt, and Airflow pipelines."
        "</div></body></html>"
    )
    title, company, jd = _extract_linkedin_guest_job(sample_html)
    assert title == "Data Engineer"
    assert company == "FIT HUB"
    assert "BigQuery" in jd


def test_strip_html_and_infer_industry() -> None:
    raw = (
        "<div><h1>Bank Jago</h1><script>bad()</script>"
        "<p>Digital bank and fintech lending</p></div>"
    )
    cleaned = strip_html(raw)
    assert "bad()" not in cleaned
    assert "Digital bank" in cleaned
    assert infer_industry(cleaned) == "Fintech / Banking / Lending"


def test_company_research_uses_pasted_jd_and_extracts_stack() -> None:
    intel = research_company_and_jd(
        company_name="Kredivo",
        target_role="Data Engineer",
        pasted_jd=(
            "Building real-time fintech lending pipelines using Python, SQL, Kafka, "
            "dbt, and Airflow."
        ),
        allow_web=False,
    )
    assert intel.company_name == "Kredivo"
    assert intel.jd_source == "user_pasted"
    assert intel.industry == "Fintech / Banking / Lending"
    assert {"Python", "SQL", "Apache Kafka", "dbt", "Apache Airflow"}.issubset(
        set(intel.detected_tech_stack)
    )


def test_project_ranking_matches_company_domain() -> None:
    if not MASTER_PROFILE.exists():
        return
    profile = load_master_profile(MASTER_PROFILE)

    fintech_intel = CompanyIntel(
        company_name="Kredivo",
        industry="Fintech / Banking / Lending",
        jd_text="BNPL lending Kafka streaming CDC dbt Airflow",
    )
    fintech_ranked = _rank_projects_for_target(profile.projects, "Data Engineer", fintech_intel)
    assert fintech_ranked[0].id == "proj_paylater"

    fmcg_intel = CompanyIntel(
        company_name="Unilever",
        industry="FMCG / Supply Chain",
        jd_text="FMCG retail demand forecasting supply chain Metabase dbt",
    )
    fmcg_ranked = _rank_projects_for_target(profile.projects, "Data Analyst", fmcg_intel)
    assert fmcg_ranked[0].id == "proj_fmcg"


def test_company_deep_dive_deterministic_fallback() -> None:
    profile = load_master_profile(MASTER_PROFILE) if MASTER_PROFILE.exists() else None
    report = generate_company_deep_dive(
        company_name="FIT HUB",
        target_role="Data Engineer",
        pasted_jd="Health and wellness startup needing Python, SQL, and Data Quality pipelines.",
        language="id",
        use_llm=False,
        allow_web=False,
        profile=profile,
    )
    assert report.company_name == "FIT HUB"
    assert report.industry == "Health / Fitness / Wellness"
    assert len(report.strengths) >= 2
    assert len(report.weaknesses_and_challenges) >= 2
    assert len(report.inferred_team_needs) >= 2
    assert len(report.how_candidate_fits) >= 2
    assert len(report.smart_interview_questions) >= 2
