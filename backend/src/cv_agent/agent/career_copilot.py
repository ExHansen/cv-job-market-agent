from collections.abc import Iterator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from cv_agent.ingestion.company_research import research_company_and_jd
from cv_agent.llm import get_chat_model
from cv_agent.schemas import MasterProfile
from cv_agent.storage.applications_db import ApplicationsDatabase
from cv_agent.storage.companies_db import CompanyKnowledgeDatabase
from cv_agent.storage.market_db import MarketDatabase


class CopilotTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CopilotChatRequest(BaseModel):
    language: Literal["id", "en"] = "id"
    messages: list[CopilotTurn] = Field(default_factory=list)


SYSTEM_ARCHITECTURE_GUIDE = """
CAREROS STUDIO SYSTEM MAP (Features You Know Inside Out):
1. **CareerOS AI Copilot (`/dashboard/assistant`)**: Chatbot pusat ini — mengerti sistem,
   membaca seluruh DuckDB lokal (Company Knowledge Base, Market Radar, Application Tracker)
   dan Master Profile untuk memberi saran karier, review perusahaan, dan panduan fitur.
2. **CV & Company Studio (`/dashboard/cv-studio`)**: Masukkan nama perusahaan atau paste
   link LinkedIn (`/jobs/search-results/?currentJobId=...`) -> LangGraph meriset perusahaan
   & JD -> audit skill gap -> tulis ulang bullet XYZ via Ollama -> cek anti-halusinasi ->
   compile PDF ATS-friendly dengan RenderCV (Typst).
3. **Company Deep-Dive & Knowledge Base (`/dashboard/company-intel`)**: Riset mendalam
   kelebihan, kekurangan/keluh kesah, kebutuhan tim, kecocokan profil, + browsing & tambah
   data perusahaan di DuckDB (rating, WLB, positives, keluh kesah, posisi, estimasi gaji IDR).
4. **Job Market Radar (`/dashboard/market-radar`)**: Grafik & tabel frekuensi skill pasar
   kerja dari DuckDB + tombol Refresh Live Jobs (`python-jobspy`).
5. **Master Profile (`/dashboard/master-profile`)**: Single Source of Truth karier user
   (`data/master_profile.yaml`) + uji upload/parse file `.pdf` / `.docx`.
6. **Application Tracker (`/dashboard/applications`)**: Kanban persisten di DuckDB
   (`Wishlist -> Applied -> Interview -> Offer -> Rejected`) lengkap dengan ATS score & PDF.
7. **Interview Prep Chat (`/dashboard/interview-prep`)**: Simulasi mock interview interaktif
   (Technical, System Design, Behavioral STAR, HR) dengan skor 1–10 per jawaban.
8. **Job Finder & HR Radar (`/dashboard/job-finder`)**: Pencarian live lowongan kerja
   Indonesia (LinkedIn/Indeed via python-jobspy) + Remote Global (Remotive/Arbeitnow),
   diurutkan berdasarkan **Match Score %** terhadap CV user, lengkap dengan umur postingan,
   detail JD, info perusahaan & gaji IDR dari DuckDB, plus shortcut radar postingan HR ID.
""".strip()


def gather_copilot_context(
    user_query: str,
    profile: MasterProfile,
    company_db: CompanyKnowledgeDatabase,
    market_db: MarketDatabase,
    apps_db: ApplicationsDatabase,
) -> tuple[str, list[str]]:
    """
    Retrieve live grounded context from all local DuckDB tables + MasterProfile so the
    CareerOS AI Copilot answers accurately about the system, companies, salaries, and CV fit.
    """
    sources: list[str] = ["CareerOS System Map", "Master Profile"]
    sections: list[str] = [SYSTEM_ARCHITECTURE_GUIDE]

    # 1. Master Profile concise ground truth
    exp_summary = [
        f"- {e.role} @ {e.company} ({e.start_date}–{e.end_date}): "
        + "; ".join(b.raw_fact for b in e.bullets[:2])
        for e in profile.experiences
    ]
    proj_summary = [
        f"- {p.name} [{', '.join(p.domain_tags)}]" for p in profile.projects
    ]
    certs_summary = [f"{c.name} ({c.issuer}, {c.date})" for c in profile.certifications]
    sections.append(
        "USER MASTER PROFILE (VERIFIED FACTS ONLY):\n"
        f"Name: {profile.profile.full_name} ({profile.profile.headline}, "
        f"{profile.profile.years_of_experience:g}+ yrs exp, {profile.profile.location})\n"
        f"Verified Skills: {', '.join(sorted(profile.all_verified_skills()))}\n"
        f"Certifications: {', '.join(certs_summary)}\n"
        "Experiences:\n"
        + "\n".join(exp_summary)
        + "\nProjects:\n"
        + "\n".join(proj_summary)
    )

    # 2. Company Knowledge Base (DuckDB) — detailed records for mentioned companies + catalog index
    all_companies = company_db.list_companies()
    matched = company_db.match_companies_in_text(user_query)

    catalog_lines = [
        f"- {c.company_name} ({c.industry}) | Rating: {c.overall_rating}/5, WLB: "
        f"{c.work_life_balance}/5 | Verdict: {c.verdict} | Mid IDR: {c.salary_idr_mid} | "
        f"Stack: {', '.join(c.typical_tech_stack[:5])}"
        for c in all_companies
    ]
    sections.append(
        f"COMPANY KNOWLEDGE BASE INDEX ({len(all_companies)} companies in DuckDB):\n"
        + "\n".join(catalog_lines)
    )

    if matched:
        sources.append(f"DuckDB Company KB: {', '.join(c.company_name for c in matched)}")
        detail_blocks: list[str] = []
        for c in matched[:3]:
            detail_blocks.append(
                f"### {c.company_name} ({c.industry} — {c.company_stage})\n"
                f"Rating: {c.overall_rating}/5 | WLB: {c.work_life_balance}/5 | "
                f"Culture: {c.culture_score}/5 | Growth: {c.career_growth}/5 | "
                f"Verdict: {c.verdict}\n"
                f"Condition: {c.condition_summary}\n"
                f"The Positives: {'; '.join(c.positives)}\n"
                f"Keluh Kesah (Cons/Pain Points): {'; '.join(c.kesah_kesuh)}\n"
                f"Common Positions: {', '.join(c.common_positions)}\n"
                f"Typical JD: {c.typical_jd_summary}\n"
                f"Salary IDR: Junior ({c.salary_idr_junior}) | Mid ({c.salary_idr_mid}) | "
                f"Senior ({c.salary_idr_senior})\n"
                f"Tech Stack: {', '.join(c.typical_tech_stack)}\n"
                f"Source Note: {c.source_notes}"
            )
        sections.append("DETAILED COMPANY RECORDS MATCHED:\n" + "\n\n".join(detail_blocks))
    else:
        sources.append(f"DuckDB Company KB ({len(all_companies)} companies)")
        # If user pasted a job URL inside chat, extract live JD automatically!
        if "http://" in user_query or "https://" in user_query:
            url_token = next(
                (w.strip(".,) ") for w in user_query.split() if w.startswith(("http://", "https://"))),
                "",
            )
            if url_token:
                intel = research_company_and_jd(
                    company_name="",
                    target_role="Data Engineer",
                    job_url=url_token,
                    allow_web=True,
                    db=market_db,
                )
                if intel.jd_text:
                    sources.append(f"Live Job URL: {intel.company_name or 'Extracted JD'}")
                    sections.append(
                        f"EXTRACTED LIVE JOB FROM URL:\nCompany: {intel.company_name} "
                        f"({intel.industry})\nRole: {intel.job_title_found}\n"
                        f"Stack: {', '.join(intel.detected_tech_stack)}\n"
                        f"JD Excerpt: {intel.jd_text[:1800]}"
                    )

    # 3. Job Market Radar trends (DuckDB)
    snap = market_db.get_market_snapshot(role="Data Engineer", region="Indonesia")
    top_skills = ", ".join(f"{s.skill} ({s.frequency_pct}%)" for s in snap.top_mandatory_skills[:8])
    rising_skills = ", ".join(f"{s.skill} ({s.frequency_pct}%)" for s in snap.rising_skills[:6])
    sections.append(
        f"JOB MARKET RADAR (DuckDB, role={snap.role}, n={snap.sample_size}):\n"
        f"Mandatory Skills: {top_skills}\nRising Skills: {rising_skills}"
    )
    sources.append("DuckDB Job Market Radar")

    # 4. User's active Application Tracker (DuckDB)
    apps = apps_db.list_applications()
    if apps:
        app_lines = [
            f"- {a.company} ({a.role}) -> status: {a.status}, ATS: {a.ats_score or 'N/A'}"
            for a in apps[:8]
        ]
        sections.append("USER APPLICATION TRACKER (DuckDB):\n" + "\n".join(app_lines))
        sources.append(f"DuckDB Applications ({len(apps)})")

    return "\n\n".join(sections), sources


def stream_copilot_reply(
    req: CopilotChatRequest,
    profile: MasterProfile,
    company_db: CompanyKnowledgeDatabase,
    market_db: MarketDatabase,
    apps_db: ApplicationsDatabase,
) -> tuple[list[str], Iterator[str]]:
    """Return (context_sources, token_iterator) for CareerOS AI Copilot SSE streaming."""
    latest_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"),
        "Jelaskan bagaimana sistem CareerOS ini bekerja.",
    )
    context_blob, sources = gather_copilot_context(
        user_query=latest_user,
        profile=profile,
        company_db=company_db,
        market_db=market_db,
        apps_db=apps_db,
    )

    lang_rule = (
        "Jawab dalam Bahasa Indonesia yang santai, jelas, terstruktur (pakai bullet & **bold**), "
        "dan langsung actionable. Pertahankan istilah teknis dalam bahasa Inggris."
        if req.language == "id"
        else "Reply in concise, structured, actionable English."
    )

    system_prompt = (
        "You are **CareerOS AI Copilot**, the central personal career & job-market AI assistant "
        "built directly into this application.\n"
        f"{lang_rule}\n\n"
        "RULES:\n"
        "1. You understand the entire CareerOS system — guide the user to exact pages/features "
        "whenever they ask 'kalau saya mau X gimana?'.\n"
        "2. When asked whether a company is good or bad, ALWAYS give a balanced, honest verdict "
        "covering: **Kondisi Perusahaan**, **The Positives**, **Keluh Kesah (Cons)**, **Posisi & "
        "Estimasi Gaji IDR**, dan **Kecocokan Profil** grounded in the DuckDB records.\n"
        "3. If a company is NOT in the DuckDB Company Knowledge Base, state that honestly and tell "
        "the user they can add it in `/dashboard/company-database` or paste "
        "its LinkedIn job URL right here in chat.\n"
        "4. Never fabricate skills or metrics that are not in the User Master Profile.\n\n"
        f"=== LIVE LOCAL CONTEXT ===\n{context_blob}"
    )

    lc_messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=system_prompt)
    ]
    for turn in req.messages[-12:]:
        if turn.role == "user":
            lc_messages.append(HumanMessage(content=turn.content))
        else:
            lc_messages.append(AIMessage(content=turn.content))

    def _tokens() -> Iterator[str]:
        llm = get_chat_model(temperature=0.35)
        for chunk in llm.stream(lc_messages):
            text = getattr(chunk, "content", "")
            if text:
                yield str(text)

    return sources, _tokens()
