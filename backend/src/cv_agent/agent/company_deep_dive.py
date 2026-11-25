from collections.abc import Callable
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from cv_agent.config import settings
from cv_agent.ingestion.company_research import research_company_and_jd
from cv_agent.llm import get_chat_model
from cv_agent.schemas import (
    CompanyDeepDiveLLMOutput,
    CompanyDeepDiveReport,
    CompanyIntel,
    MasterProfile,
)
from cv_agent.storage.companies_db import CompanyKnowledgeDatabase, CompanyKnowledgeRecord
from cv_agent.storage.market_db import MarketDatabase

ProgressCallback = Callable[[str, int, str], None]


def _deterministic_deep_dive_fallback(
    intel: CompanyIntel,
    target_role: str,
    profile: MasterProfile | None,
    language: Literal["id", "en"],
) -> CompanyDeepDiveReport:
    name = intel.company_name or "Perusahaan Target"
    stack = intel.detected_tech_stack or ["Python", "SQL", "dbt", "Data Quality"]
    verified = sorted(profile.all_verified_skills()) if profile else []
    overlap = [s for s in stack if s in verified]

    if language == "id":
        overview = intel.company_summary or (
            f"{name} beroperasi di sektor {intel.industry} dan sedang membuka atau "
            f"membutuhkan talenta {target_role} untuk memperkuat fondasi data serta operasional."
        )
        strengths = [
            f"Beroperasi di sektor bertumbuh ({intel.industry}) dengan kebutuhan data strategis.",
            f"Menggunakan atau mencari fondasi teknologi modern: {', '.join(stack[:5])}.",
            "Memiliki ruang kontribusi langsung bagi engineer data untuk berdampak ke bisnis.",
        ]
        weaknesses = [
            "Pertumbuhan volume data dan operasional sering memicu inkonsistensi kualitas data.",
            "Ketergantungan pada laporan manual/ad-hoc memperlambat pengambilan keputusan tim.",
            "Tantangan menjaga efisiensi biaya komputasi dan kecepatan query saat skala data naik.",
        ]
        needs = [
            f"Membutuhkan {target_role} yang mampu membangun pipeline andal dan mudah dirawat.",
            "Membutuhkan standar data quality, validasi otomatis, dan data modeling yang rapi.",
            "Membutuhkan kolaborasi erat antara tim data dan stakeholder bisnis untuk KPI akurat.",
        ]
        fits = [
            f"Kecocokan skill terverifikasi langsung: {', '.join(overlap or verified[:5])}.",
            "Pengalaman nyata menjaga akurasi data >=95% pada skala ~200 GB/hari & migrasi 2 TB.",
            "Terbiasa mengoptimalkan pipeline SQL/dbt untuk mempercepat proses & menekan biaya.",
        ]
        questions = [
            "Apa bottleneck terbesar di pipeline data atau kualitas data tim saat ini?",
            "Seperti apa target kesuksesan 90 hari pertama untuk posisi ini?",
            "Bagaimana kolaborasi antara Data Engineer, Analyst, dan tim bisnis soal KPI?",
        ]
        biz_model = f"Bisnis berbasis layanan/produk di sektor {intel.industry}."
    else:
        overview = intel.company_summary or (
            f"{name} operates in {intel.industry} and is investing in {target_role} capabilities."
        )
        strengths = [
            f"Active growth in the {intel.industry} sector.",
            f"Focus on practical data stack: {', '.join(stack[:5])}.",
        ]
        weaknesses = [
            "Scaling operational data often creates data quality and schema drift challenges.",
            "Balancing dashboard query speed against cloud warehouse compute costs.",
        ]
        needs = [
            f"Reliable {target_role} foundation powering business and product analytics.",
            "Automated data validation, dimensional modeling, and clear SLA ownership.",
        ]
        fits = [
            f"Direct verified stack overlap: {', '.join(overlap or verified[:5])}.",
            "Proven TB-scale warehouse migration and daily ~200 GB data quality operations.",
        ]
        questions = [
            "What is the biggest data reliability or pipeline bottleneck in the next 6 months?",
            "What does success in the first 90 days look like for this role?",
            "How are data quality standards and ownership shared across teams?",
        ]
        biz_model = f"Product/service business operating in {intel.industry}."

    sources = [s for s in (intel.source_url, intel.job_url_found) if s]
    return CompanyDeepDiveReport(
        company_name=name,
        target_role=intel.job_title_found or target_role,
        industry=intel.industry,
        business_model=biz_model,
        company_overview=overview,
        strengths=strengths,
        weaknesses_and_challenges=weaknesses,
        inferred_team_needs=needs,
        how_candidate_fits=fits,
        smart_interview_questions=questions,
        detected_tech_stack=intel.detected_tech_stack,
        job_title_found=intel.job_title_found,
        job_url_found=intel.job_url_found,
        jd_source=intel.jd_source,
        sources=list(dict.fromkeys(sources)),
        used_llm=False,
    )


def generate_company_deep_dive(
    company_name: str,
    target_role: str = "Data Engineer",
    job_url: str = "",
    pasted_jd: str = "",
    language: Literal["id", "en"] = "id",
    use_llm: bool = True,
    allow_web: bool = True,
    profile: MasterProfile | None = None,
    db: MarketDatabase | None = None,
    on_progress: ProgressCallback | None = None,
) -> CompanyDeepDiveReport:
    """
    Gather grounded company + JD intel and analyze strengths, weaknesses/challenges,
    team needs, and candidate fit using local LLM structured output.
    """
    if on_progress:
        on_progress(
            "research",
            15,
            f"Mengumpulkan profil publik & lowongan untuk '{company_name or 'URL'}'...",
        )

    intel = research_company_and_jd(
        company_name=company_name,
        target_role=target_role,
        job_url=job_url,
        pasted_jd=pasted_jd,
        allow_web=allow_web,
        db=db,
    )

    # Enrich with local DuckDB Company Knowledge Base (positives, keluh kesah, IDR salaries)
    kb_record: CompanyKnowledgeRecord | None = None
    lookup_name = intel.company_name or company_name
    if lookup_name:
        try:
            kb_record = CompanyKnowledgeDatabase().find_company(lookup_name)
        except Exception:
            kb_record = None

    if on_progress:
        found_name = intel.company_name or company_name or "Perusahaan Target"
        kb_note = f" + DuckDB KB ({kb_record.overall_rating}/5)" if kb_record else ""
        stack_preview = ", ".join(intel.detected_tech_stack[:5]) or "market benchmark"
        on_progress(
            "profile_match",
            40,
            f"Data ditemukan: {found_name} ({intel.industry}){kb_note} | "
            f"JD: {intel.jd_source} | Stack: {stack_preview}",
        )

    if not use_llm:
        report = _deterministic_deep_dive_fallback(intel, target_role, profile, language)
        if on_progress:
            on_progress("finalize", 100, "Analisis cepat selesai!")
        return report

    active_model = (
        settings.ollama_model if settings.llm_provider == "ollama" else settings.openai_model
    )
    if on_progress:
        on_progress(
            "llm_analysis",
            55,
            f"Menjalankan analisis strategis dengan {active_model} "
            "(estimasi ~25–60 detik di GPU lokal)...",
        )

    lang_instruction = (
        "Write all explanations in clear, natural Bahasa Indonesia (keep technical tool names "
        "like dbt, ClickHouse, BigQuery, Kafka, SQL, Airflow in English)."
        if language == "id"
        else "Write all explanations in concise, natural English."
    )

    candidate_summary = ""
    if profile:
        exp_facts = [
            f"- {exp.role} at {exp.company}: {b.raw_fact}"
            for exp in profile.experiences
            for b in exp.bullets[:3]
        ]
        proj_names = [f"{p.name} ({', '.join(p.domain_tags)})" for p in profile.projects]
        candidate_summary = (
            f"Candidate Verified Skills: {sorted(profile.all_verified_skills())}\n"
            f"Candidate Key Experiences:\n" + "\n".join(exp_facts) + "\n"
            f"Candidate Projects: {', '.join(proj_names)}\n"
        )

    system_prompt = (
        "You are a Senior Career Strategist and Tech Industry Analyst.\n"
        f"{lang_instruction}\n"
        "GROUNDING & HONESTY RULES:\n"
        "1. Base company overview and strengths strictly on the provided company summary, JD, "
        "and well-known public business model facts.\n"
        "2. For weaknesses_and_challenges, focus on realistic operational/data/competitive "
        "challenges signaled by the JD and industry (clearly framed as tantangan/kebutuhan "
        "bisnis, never fabricate scandals or fake internal leaks).\n"
        "3. For how_candidate_fits, ONLY reference verified skills, projects, and metrics "
        "from the candidate profile provided.\n"
        "4. For smart_interview_questions, write 3 smart questions that the CANDIDATE asks "
        "the hiring manager about the company's data challenges, architecture, or 90-day goals "
        "(NOT questions the interviewer asks the candidate).\n"
        "5. Be specific, sharp, and practical so the candidate knows exactly what the company "
        "needs and how to position their CV and interview answers."
    )

    kb_context = ""
    if kb_record:
        kb_context = (
            f"Local DuckDB Company Knowledge Record:\n"
            f"- Stage: {kb_record.company_stage} | Rating: {kb_record.overall_rating}/5 | "
            f"WLB: {kb_record.work_life_balance}/5 | Verdict: {kb_record.verdict}\n"
            f"- Condition: {kb_record.condition_summary}\n"
            f"- Employee Positives: {'; '.join(kb_record.positives)}\n"
            f"- Employee Keluh Kesah: {'; '.join(kb_record.kesah_kesuh)}\n"
            f"- Estimated Salary IDR: Junior {kb_record.salary_idr_junior} | "
            f"Mid {kb_record.salary_idr_mid} | Senior {kb_record.salary_idr_senior}\n"
            f"- Typical JD: {kb_record.typical_jd_summary}\n\n"
        )

    user_prompt = (
        f"Target Company: {intel.company_name or company_name}\n"
        f"Target Role: {intel.job_title_found or target_role}\n"
        f"Detected Industry: {intel.industry}\n"
        f"Detected Tech Stack: {intel.detected_tech_stack}\n"
        f"{kb_context}"
        f"Public Company Summary:\n{intel.company_summary or 'Not found directly'}\n\n"
        f"Job Description Excerpt (source={intel.jd_source}):\n"
        f"{intel.jd_text[:3000] or 'No specific JD provided — infer from role & industry'}\n\n"
        f"{candidate_summary}"
    )

    try:
        llm = get_chat_model(temperature=0.3).with_structured_output(
            CompanyDeepDiveLLMOutput, method="json_schema"
        )
        parsed = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        sources = [s for s in (intel.source_url, intel.job_url_found) if s]
        report = CompanyDeepDiveReport(
            company_name=intel.company_name or company_name or "Target Company",
            target_role=intel.job_title_found or target_role,
            industry=intel.industry,
            business_model=parsed.business_model,
            company_overview=parsed.company_overview,
            strengths=parsed.strengths,
            weaknesses_and_challenges=parsed.weaknesses_and_challenges,
            inferred_team_needs=parsed.inferred_team_needs,
            how_candidate_fits=parsed.how_candidate_fits,
            smart_interview_questions=parsed.smart_interview_questions,
            detected_tech_stack=intel.detected_tech_stack,
            job_title_found=intel.job_title_found,
            job_url_found=intel.job_url_found,
            jd_source=intel.jd_source,
            sources=list(dict.fromkeys(sources)),
            used_llm=True,
        )
        if on_progress:
            on_progress("finalize", 100, "Laporan strategis selesai disusun!")
        return report
    except Exception:
        report = _deterministic_deep_dive_fallback(intel, target_role, profile, language)
        if on_progress:
            on_progress(
                "finalize",
                100,
                "Ollama tidak merespons — memakai analisis fallback terverifikasi.",
            )
        return report
