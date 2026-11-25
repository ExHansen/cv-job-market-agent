from collections.abc import Iterator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from cv_agent.llm import get_chat_model
from cv_agent.schemas import MasterProfile

InterviewMode = Literal["technical", "behavioral", "system_design", "hr"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class InterviewChatRequest(BaseModel):
    company_name: str = "FIT HUB"
    target_role: str = "Data Engineer"
    mode: InterviewMode = "technical"
    language: Literal["id", "en"] = "id"
    messages: list[ChatTurn] = Field(default_factory=list)


def _build_interviewer_system_prompt(
    req: InterviewChatRequest,
    profile: MasterProfile,
) -> str:
    lang_rule = (
        "Conduct the mock interview in natural, professional Bahasa Indonesia "
        "(keep technical terms like dbt, ClickHouse, BigQuery, Kafka, Airflow, SQL in English)."
        if req.language == "id"
        else "Conduct the mock interview in concise, natural professional English."
    )

    exp_lines = [
        f"- {exp.role} at {exp.company}: {b.raw_fact}"
        for exp in profile.experiences
        for b in exp.bullets[:3]
    ]
    proj_lines = [
        f"- {p.name} ({', '.join(p.domain_tags)}): {p.bullets[0].raw_fact}"
        for p in profile.projects
        if p.bullets
    ]

    mode_guide = {
        "technical": (
            "Focus on SQL optimization, dbt modeling, BigQuery/ClickHouse trade-offs, "
            "data quality testing, Python/Airflow orchestration, and Kafka CDC."
        ),
        "behavioral": (
            "Focus on STAR-method behavioral scenarios: ownership, handling production data "
            "incidents, cross-functional communication, and tight deadlines."
        ),
        "system_design": (
            "Focus on end-to-end data architecture: ingestion, lakehouse/warehouse modeling, "
            "idempotency, observability, latency SLAs, and cloud cost optimization."
        ),
        "hr": (
            "Focus on motivation, career progression, role expectations, culture fit, "
            "and salary/growth alignment."
        ),
    }[req.mode]

    return (
        f"You are a Senior Hiring Manager at {req.company_name} interviewing "
        f"{profile.profile.full_name} for a {req.target_role} role.\n"
        f"{lang_rule}\n"
        f"Interview Mode: {req.mode.upper()} — {mode_guide}\n\n"
        "RULES:\n"
        "1. If the user just started the session, greet them briefly and ask ONE sharp, "
        "realistic opening question grounded in their actual resume below.\n"
        "2. When the user answers a question, ALWAYS give:\n"
        "   - **Skor Jawaban (1–10)** + **Kelebihan** + **Yang Bisa Dipertajam** (2–3 poin)\n"
        "   - Followed by **Pertanyaan Lanjutan** (ONE focused follow-up question).\n"
        "3. Stay grounded in the candidate's verified profile — never invent fake roles.\n\n"
        f"CANDIDATE VERIFIED SKILLS: {sorted(profile.all_verified_skills())}\n"
        "CANDIDATE EXPERIENCES:\n"
        + "\n".join(exp_lines)
        + "\nCANDIDATE PROJECTS:\n"
        + "\n".join(proj_lines)
    )


def stream_interview_reply(
    req: InterviewChatRequest,
    profile: MasterProfile,
) -> Iterator[str]:
    """Stream real tokens from local Ollama for low-latency mock interview chat."""
    system_prompt = _build_interviewer_system_prompt(req, profile)
    lc_messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=system_prompt)
    ]

    if not req.messages:
        starter = (
            f"Halo, saya siap mulai sesi mock interview {req.mode} untuk posisi "
            f"{req.target_role} di {req.company_name}."
            if req.language == "id"
            else f"Hi, I am ready to start the {req.mode} mock interview for "
            f"{req.target_role} at {req.company_name}."
        )
        lc_messages.append(HumanMessage(content=starter))
    else:
        for turn in req.messages[-12:]:
            if turn.role == "user":
                lc_messages.append(HumanMessage(content=turn.content))
            else:
                lc_messages.append(AIMessage(content=turn.content))

    llm = get_chat_model(temperature=0.4)
    for chunk in llm.stream(lc_messages):
        content = getattr(chunk, "content", "")
        if content:
            yield str(content)
