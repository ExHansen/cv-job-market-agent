from typing import Literal, TypedDict

from cv_agent.schemas import (
    CompanyIntel,
    FactCheckResult,
    GapAuditReport,
    MarketSnapshot,
    MasterProfile,
    TailoredCV,
)


class AgentState(TypedDict, total=False):
    master_profile: MasterProfile
    target_role: str
    target_company: str
    job_url: str
    region: str
    target_jd_text: str
    output_language: Literal["en", "id"]
    use_llm: bool
    allow_web_research: bool

    company_intel: CompanyIntel
    market_snapshot: MarketSnapshot
    gap_audit: GapAuditReport
    tailored_cv: TailoredCV
    fact_check: FactCheckResult

    revision_count: int
    max_revisions: int
    events: list[str]
