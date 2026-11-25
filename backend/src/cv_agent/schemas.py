from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Internal User Career Ground Truth (Master Profile)
# ---------------------------------------------------------------------------


class ProfileLinks(BaseModel):
    github: str = ""
    linkedin: str = ""
    website: str = ""


class ProfileHeader(BaseModel):
    full_name: str
    headline: str = "Data Engineer"
    target_roles: list[str] = Field(default_factory=lambda: ["Data Engineer"])
    location: str = ""
    email: str = ""
    phone: str = ""
    links: ProfileLinks = Field(default_factory=ProfileLinks)
    years_of_experience: float = 0.0


class FactBullet(BaseModel):
    id: str
    raw_fact: str
    metrics: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    verified: bool = True


class ExperienceEntry(BaseModel):
    id: str
    company: str
    role: str
    location: str = ""
    start_date: str
    end_date: str = "present"
    bullets: list[FactBullet] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    id: str
    name: str
    period: str = ""
    url: str = ""
    domain_tags: list[str] = Field(default_factory=list)
    bullets: list[FactBullet] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    degree: str
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""


class CertificationEntry(BaseModel):
    name: str
    issuer: str
    date: str = ""


class HonorEntry(BaseModel):
    title: str
    issuer: str = ""
    date: str = ""
    summary: str = ""


class MasterProfile(BaseModel):
    profile: ProfileHeader
    skills_verified: dict[str, list[str]] = Field(default_factory=dict)
    experiences: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    honors: list[HonorEntry] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    def all_verified_skills(self) -> set[str]:
        skills: set[str] = set()
        for group in self.skills_verified.values():
            skills.update(s.strip() for s in group if s.strip())
        for exp in self.experiences:
            for bullet in exp.bullets:
                skills.update(t.strip() for t in bullet.tools_used if t.strip())
        for proj in self.projects:
            for bullet in proj.bullets:
                skills.update(t.strip() for t in bullet.tools_used if t.strip())
        return skills

    def all_bullet_ids(self) -> set[str]:
        ids: set[str] = set()
        for exp in self.experiences:
            ids.update(b.id for b in exp.bullets)
        for proj in self.projects:
            ids.update(b.id for b in proj.bullets)
        return ids


# ---------------------------------------------------------------------------
# Company & Job Market Intelligence Contracts
# ---------------------------------------------------------------------------


class CompanyIntel(BaseModel):
    company_name: str = ""
    industry: str = "Technology"
    company_summary: str = ""
    source_url: str = ""
    detected_tech_stack: list[str] = Field(default_factory=list)
    job_title_found: str = ""
    job_url_found: str = ""
    jd_text: str = ""
    jd_source: Literal["none", "user_pasted", "direct_url", "ats_board", "duckdb_cache"] = "none"


class CompanyDeepDiveLLMOutput(BaseModel):
    """Strict required-only schema for local LLM strategic company analysis."""

    business_model: str = Field(
        description="Short explanation of how the company makes money and operates"
    )
    company_overview: str = Field(
        description="Clear 3-4 sentence overview of what the company does and its scale"
    )
    strengths: list[str] = Field(
        description="3-5 concrete company strengths and competitive advantages"
    )
    weaknesses_and_challenges: list[str] = Field(
        description="3-5 realistic weaknesses, operational bottlenecks, or industry challenges"
    )
    inferred_team_needs: list[str] = Field(
        description="3-5 concrete needs this company is hiring this role to solve"
    )
    how_candidate_fits: list[str] = Field(
        description="3-4 ways the candidate's verified experience directly solves their needs"
    )
    smart_interview_questions: list[str] = Field(
        description="3 insightful questions the candidate can ask the hiring manager"
    )


class CompanyDeepDiveReport(BaseModel):
    company_name: str
    target_role: str
    industry: str
    business_model: str
    company_overview: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses_and_challenges: list[str] = Field(default_factory=list)
    inferred_team_needs: list[str] = Field(default_factory=list)
    how_candidate_fits: list[str] = Field(default_factory=list)
    smart_interview_questions: list[str] = Field(default_factory=list)
    detected_tech_stack: list[str] = Field(default_factory=list)
    job_title_found: str = ""
    job_url_found: str = ""
    jd_source: str = "none"
    sources: list[str] = Field(default_factory=list)
    used_llm: bool = False


class SkillFrequency(BaseModel):
    skill: str
    category: str = "general"
    job_count: int
    frequency_pct: float


class MarketSnapshot(BaseModel):
    role: str
    region: str
    snapshot_date: datetime
    sample_size: int
    top_mandatory_skills: list[SkillFrequency] = Field(default_factory=list)
    rising_skills: list[SkillFrequency] = Field(default_factory=list)
    source_breakdown: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CV Audit, Tailoring & Anti-Hallucination Fact-Check Contracts
# ---------------------------------------------------------------------------


class GapAuditReport(BaseModel):
    target_role: str
    ats_score: float = Field(ge=0.0, le=100.0)
    matched_skills: list[str] = Field(default_factory=list)
    hidden_quick_wins: list[str] = Field(default_factory=list)
    true_skill_gaps: list[str] = Field(default_factory=list)
    weak_bullet_ids: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    upskilling_recommendations: list[str] = Field(default_factory=list)


class TailoredBullet(BaseModel):
    source_id: str = Field(description="ID of the original FactBullet from MasterProfile")
    original_text: str
    rewritten_text: str
    tools_referenced: list[str] = Field(default_factory=list)


class LLMRewrittenBullet(BaseModel):
    """Focused, required-only schema for local LLM bullet rewriting."""

    source_id: str = Field(description="Exact bullet id from MasterProfile, e.g. exp_01_b1")
    rewritten_text: str = Field(
        description="Concise ATS-optimized XYZ bullet (12-32 words) grounded in the original fact"
    )


class LLMRewritePayload(BaseModel):
    """Minimal structured output payload so local LLMs cannot drop metadata or fields."""

    professional_summary: str = Field(
        description="3-4 line ATS-optimized summary tailored to the target company and role"
    )
    prioritized_project_ids: list[str] = Field(
        description="Project IDs from MasterProfile ordered from most to least relevant"
    )
    rewritten_bullets: list[LLMRewrittenBullet] = Field(
        description="Rewritten version of every experience bullet using exact source_id"
    )


class TailoredExperience(BaseModel):
    id: str
    company: str
    role: str
    location: str = ""
    start_date: str
    end_date: str = "present"
    bullets: list[TailoredBullet] = Field(default_factory=list)


class TailoredCV(BaseModel):
    target_role: str
    target_company: str = ""
    output_language: Literal["en", "id"] = "en"
    professional_summary: str
    grouped_skills: dict[str, list[str]] = Field(default_factory=dict)
    experiences: list[TailoredExperience] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)


class FactCheckViolation(BaseModel):
    severity: Literal["error", "warning"]
    rule: str
    detail: str


class FactCheckResult(BaseModel):
    passed: bool
    ats_score: float = Field(ge=0.0, le=100.0)
    violations: list[FactCheckViolation] = Field(default_factory=list)
