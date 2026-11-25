import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from cv_agent.agent.critic import run_deterministic_fact_check
from cv_agent.agent.state import AgentState
from cv_agent.ingestion.company_research import research_company_and_jd
from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.llm import get_chat_model
from cv_agent.schemas import (
    CompanyIntel,
    GapAuditReport,
    LLMRewritePayload,
    ProjectEntry,
    TailoredBullet,
    TailoredCV,
    TailoredExperience,
)
from cv_agent.storage.market_db import MarketDatabase


def company_research_node(state: AgentState) -> dict:
    company_name = (state.get("target_company") or "").strip()
    role = state.get("target_role") or state["master_profile"].profile.headline
    job_url = (state.get("job_url") or "").strip()
    pasted_jd = (state.get("target_jd_text") or "").strip()
    allow_web = bool(state.get("allow_web_research", True))

    events = list(state.get("events", []))
    if not company_name and not job_url and not pasted_jd:
        return {"company_intel": CompanyIntel(), "events": events}

    db = MarketDatabase()
    intel = research_company_and_jd(
        company_name=company_name,
        target_role=role,
        job_url=job_url,
        pasted_jd=pasted_jd,
        allow_web=allow_web,
        db=db,
    )

    label = intel.company_name or "Target JD"
    stack_note = (
        f"stack={', '.join(intel.detected_tech_stack[:6])}"
        if intel.detected_tech_stack
        else "using market benchmark stack"
    )
    events.append(
        f"[Company Intel] Researched '{label}' ({intel.industry}) | "
        f"JD source: {intel.jd_source} | {stack_note}."
    )
    updates: dict = {"company_intel": intel, "events": events}
    if intel.company_name and not company_name:
        updates["target_company"] = intel.company_name
    if intel.job_title_found and not state.get("target_role"):
        updates["target_role"] = intel.job_title_found
    return updates


def market_intel_node(state: AgentState) -> dict:
    role = state.get("target_role") or state["master_profile"].profile.headline
    region = state.get("region", "Indonesia")
    db = MarketDatabase()
    snapshot = db.get_market_snapshot(role=role, region=region)
    events = list(state.get("events", []))
    events.append(
        f"[Market Intel] Loaded {snapshot.sample_size} '{role}' postings ({region}) "
        f"with {len(snapshot.top_mandatory_skills)} core skills."
    )
    return {"market_snapshot": snapshot, "events": events}


def _rank_projects_for_target(
    projects: list[ProjectEntry],
    role: str,
    intel: CompanyIntel,
    llm_order: list[str] | None = None,
) -> list[ProjectEntry]:
    if not projects:
        return []
    by_id = {p.id: p for p in projects}
    if llm_order:
        ordered = [by_id[pid] for pid in llm_order if pid in by_id]
        remaining = [p for p in projects if p.id not in set(llm_order)]
        return ordered + remaining

    target_blob = f"{role} {intel.company_name} {intel.industry} {intel.jd_text}".lower()

    def _score(proj: ProjectEntry) -> int:
        score = sum(3 for tag in proj.domain_tags if tag.lower() in target_blob)
        for b in proj.bullets:
            score += sum(1 for t in b.tools_used if t.lower() in target_blob)
        return score

    return sorted(projects, key=_score, reverse=True)


def gap_audit_node(state: AgentState) -> dict:
    profile = state["master_profile"]
    snapshot = state["market_snapshot"]
    intel = state.get("company_intel") or CompanyIntel()
    extractor = SkillTaxonomyExtractor()

    verified_skills = {extractor.normalize(s) for s in profile.all_verified_skills()}
    bullet_text = "\n".join(b.raw_fact for exp in profile.experiences for b in exp.bullets)
    bullet_skills = {s.canonical for s in extractor.extract(bullet_text)}

    mandatory = [s.skill for s in snapshot.top_mandatory_skills]
    rising = [s.skill for s in snapshot.rising_skills]

    jd_skills = list(intel.detected_tech_stack)
    priority_market = list(dict.fromkeys(jd_skills + mandatory + rising))

    matched = [s for s in priority_market if s in verified_skills and s in bullet_skills]
    hidden_quick_wins = [
        s for s in priority_market if s in verified_skills and s not in bullet_skills
    ]
    true_gaps = [s for s in priority_market if s not in verified_skills]

    weak_bullet_ids: list[str] = []
    interview_questions: list[str] = []
    for exp in profile.experiences:
        for b in exp.bullets:
            if not b.metrics:
                weak_bullet_ids.append(b.id)
                interview_questions.append(
                    f"Di {exp.company} ({b.id}), ada angka dampak nyata untuk: '{b.raw_fact}'? "
                    "(misal volume data/hari, penurunan latency, atau hemat biaya)"
                )

    ats_score = round(
        (len([s for s in mandatory if s in verified_skills]) / len(mandatory) * 100.0)
        if mandatory
        else 75.0,
        1,
    )

    upskilling = [
        f"Skill '{skill}' banyak dicari market namun belum ada di Master Profile — "
        "jangan dikarang di CV; pertimbangkan membuat 1 mini portfolio project."
        for skill in true_gaps[:4]
    ]

    report = GapAuditReport(
        target_role=snapshot.role,
        ats_score=ats_score,
        matched_skills=matched,
        hidden_quick_wins=hidden_quick_wins,
        true_skill_gaps=true_gaps[:10],
        weak_bullet_ids=weak_bullet_ids,
        interview_questions=interview_questions,
        upskilling_recommendations=upskilling,
    )

    events = list(state.get("events", []))
    events.append(
        f"[Gap Audit] Initial ATS coverage {ats_score}% | "
        f"{len(matched)} matched, {len(hidden_quick_wins)} quick wins, {len(true_gaps)} gaps."
    )
    return {"gap_audit": report, "events": events}


def _deterministic_tailor_fallback(state: AgentState) -> TailoredCV:
    """Safe zero-hallucination baseline rewriter used when LLM is disabled or unreachable."""
    profile = state["master_profile"]
    snapshot = state["market_snapshot"]
    intel = state.get("company_intel") or CompanyIntel()
    top_verified = [
        s.skill
        for s in snapshot.top_mandatory_skills
        if s.skill in profile.all_verified_skills()
    ][:6]

    years = f"{profile.profile.years_of_experience:g}+"
    target_focus = (
        f" Targeting {snapshot.role} roles at {intel.company_name} ({intel.industry})."
        if intel.company_name
        else ""
    )
    summary = (
        f"{profile.profile.headline} with {years} years of experience "
        f"building reliable data pipelines and analytics systems using {', '.join(top_verified)}."
        f"{target_focus}"
    )

    experiences: list[TailoredExperience] = []
    for exp in profile.experiences:
        tailored_bullets: list[TailoredBullet] = []
        for b in exp.bullets:
            metric_suffix = f" ({'; '.join(b.metrics)})" if b.metrics else ""
            rewritten = f"{b.raw_fact.rstrip('.')}{metric_suffix}."
            tailored_bullets.append(
                TailoredBullet(
                    source_id=b.id,
                    original_text=b.raw_fact,
                    rewritten_text=rewritten,
                    tools_referenced=b.tools_used,
                )
            )
        experiences.append(
            TailoredExperience(
                id=exp.id,
                company=exp.company,
                role=exp.role,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                bullets=tailored_bullets,
            )
        )

    ranked_projects = _rank_projects_for_target(profile.projects, snapshot.role, intel)
    return TailoredCV(
        target_role=snapshot.role,
        target_company=intel.company_name,
        output_language=state.get("output_language", "en"),
        professional_summary=summary,
        grouped_skills=profile.skills_verified,
        experiences=experiences,
        projects=ranked_projects,
    )


def rewrite_cv_node(state: AgentState) -> dict:
    revision = int(state.get("revision_count", 0))
    events = list(state.get("events", []))

    if not state.get("use_llm", True):
        tailored = _deterministic_tailor_fallback(state)
        events.append(f"[CV Rewriter] Generated deterministic baseline draft (rev {revision + 1}).")
        return {"tailored_cv": tailored, "revision_count": revision + 1, "events": events}

    profile = state["master_profile"]
    snapshot = state["market_snapshot"]
    intel = state.get("company_intel") or CompanyIntel()
    prev_check = state.get("fact_check")
    violations_hint = (
        json.dumps([v.model_dump() for v in prev_check.violations], indent=2)
        if prev_check and prev_check.violations
        else "None"
    )

    bullet_inputs = [
        {
            "source_id": b.id,
            "company": exp.company,
            "role": exp.role,
            "raw_fact": b.raw_fact,
            "verified_metrics": b.metrics,
            "verified_tools": b.tools_used,
        }
        for exp in profile.experiences
        for b in exp.bullets
    ]
    project_catalog = [
        {"id": p.id, "name": p.name, "domain_tags": p.domain_tags}
        for p in profile.projects
    ]

    system_prompt = (
        "You are an expert Technical Recruiter and ATS CV Optimizer.\n"
        "STRICT GROUNDING RULES (ZERO HALLUCINATION):\n"
        "1. ONLY use tools, skills, companies, and numbers explicitly present in the input.\n"
        "2. NEVER invent new tools, percentages, or metrics.\n"
        "3. Return a rewritten_bullets entry for EVERY source_id provided.\n"
        "4. Rewrite each bullet using Google XYZ (Impact + Metric + Tool), 14-32 words each.\n"
        "5. Order prioritized_project_ids from most to least relevant for the target company.\n"
        "6. Avoid weak phrases like 'Responsible for', 'hardworking', or 'team player'."
    )

    company_block = (
        f"Target Company: {intel.company_name} (Industry: {intel.industry})\n"
        f"Company Summary: {intel.company_summary[:500] or 'N/A'}\n"
        f"Company/JD Tech Stack: {intel.detected_tech_stack}\n"
        f"Target JD Excerpt: {intel.jd_text[:1500] or 'Use market benchmark'}\n"
        if intel.company_name or intel.jd_text
        else "Target Company: General Market Benchmark\n"
    )

    user_prompt = (
        f"Target Role: {snapshot.role}\n"
        f"{company_block}"
        f"Candidate: {profile.profile.full_name} ({profile.profile.headline}, "
        f"{profile.profile.years_of_experience:g}+ yrs exp)\n"
        f"Output Language: {state.get('output_language', 'en')}\n"
        f"Candidate Verified Skills: {sorted(profile.all_verified_skills())}\n"
        f"Top Market Skills to Highlight (only if in Verified Skills): "
        f"{[s.skill for s in snapshot.top_mandatory_skills[:10]]}\n"
        f"Available Projects (rank by relevance): {json.dumps(project_catalog)}\n"
        f"Previous Fact-Check Violations to Fix:\n{violations_hint}\n\n"
        f"Experience Bullets to Rewrite (return ALL {len(bullet_inputs)} source_ids):\n"
        f"{json.dumps(bullet_inputs, indent=2)}"
    )

    try:
        llm = get_chat_model(temperature=0.2).with_structured_output(
            LLMRewritePayload, method="json_schema"
        )
        payload = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        rewritten_map = {item.source_id: item.rewritten_text for item in payload.rewritten_bullets}

        experiences: list[TailoredExperience] = []
        for exp in profile.experiences:
            bullets: list[TailoredBullet] = []
            for b in exp.bullets:
                fallback_text = (
                    f"{b.raw_fact.rstrip('.')} ({'; '.join(b.metrics)})."
                    if b.metrics
                    else b.raw_fact
                )
                bullets.append(
                    TailoredBullet(
                        source_id=b.id,
                        original_text=b.raw_fact,
                        rewritten_text=rewritten_map.get(b.id, fallback_text).strip(),
                        tools_referenced=b.tools_used,
                    )
                )
            experiences.append(
                TailoredExperience(
                    id=exp.id,
                    company=exp.company,
                    role=exp.role,
                    location=exp.location,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    bullets=bullets,
                )
            )

        ranked_projects = _rank_projects_for_target(
            profile.projects,
            snapshot.role,
            intel,
            llm_order=payload.prioritized_project_ids,
        )
        summary = payload.professional_summary.strip() or _deterministic_tailor_fallback(
            state
        ).professional_summary

        tailored = TailoredCV(
            target_role=snapshot.role,
            target_company=intel.company_name,
            output_language=state.get("output_language", "en"),
            professional_summary=summary,
            grouped_skills=profile.skills_verified,
            experiences=experiences,
            projects=ranked_projects,
        )
        events.append(
            f"[CV Rewriter] LLM tailored {len(rewritten_map)}/{len(bullet_inputs)} bullets "
            f"& ranked {len(ranked_projects)} projects (rev {revision + 1})."
        )
    except Exception as exc:
        tailored = _deterministic_tailor_fallback(state)
        events.append(
            f"[CV Rewriter] Fallback to deterministic rewriter ({type(exc).__name__})."
        )

    return {"tailored_cv": tailored, "revision_count": revision + 1, "events": events}


def fact_check_node(state: AgentState) -> dict:
    result = run_deterministic_fact_check(
        master_profile=state["master_profile"],
        tailored_cv=state["tailored_cv"],
        market_snapshot=state["market_snapshot"],
    )
    events = list(state.get("events", []))
    status = "PASSED" if result.passed else f"FAILED ({len(result.violations)} issues)"
    events.append(f"[Critic Fact-Check] {status} | ATS Score: {result.ats_score}%")
    return {"fact_check": result, "events": events}


def route_after_fact_check(state: AgentState) -> Literal["rewrite_cv", "end"]:
    check = state["fact_check"]
    max_revisions = int(state.get("max_revisions", 3))
    if not check.passed and int(state.get("revision_count", 0)) < max_revisions:
        return "rewrite_cv"
    return "end"


def build_cv_agent_graph():
    """Compile stateful LangGraph workflow with Company Intel + Anti-Hallucination Critic Loop."""
    graph = StateGraph(AgentState)
    graph.add_node("company_research", company_research_node)
    graph.add_node("market_intel", market_intel_node)
    graph.add_node("gap_audit", gap_audit_node)
    graph.add_node("rewrite_cv", rewrite_cv_node)
    graph.add_node("fact_check", fact_check_node)

    graph.add_edge(START, "company_research")
    graph.add_edge("company_research", "market_intel")
    graph.add_edge("market_intel", "gap_audit")
    graph.add_edge("gap_audit", "rewrite_cv")
    graph.add_edge("rewrite_cv", "fact_check")
    graph.add_conditional_edges(
        "fact_check",
        route_after_fact_check,
        {"rewrite_cv": "rewrite_cv", "end": END},
    )
    return graph.compile()
