import json
import queue
import threading
import time
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from cv_agent.agent.career_copilot import CopilotChatRequest, stream_copilot_reply
from cv_agent.agent.company_deep_dive import generate_company_deep_dive
from cv_agent.agent.graph import build_cv_agent_graph
from cv_agent.agent.interview_prep import InterviewChatRequest, stream_interview_reply
from cv_agent.config import settings
from cv_agent.ingestion.company_research import research_company_and_jd
from cv_agent.ingestion.cv_parser import extract_cv_file, load_master_profile
from cv_agent.ingestion.job_fetcher import fetch_greenhouse_board, fetch_jobs_jobspy
from cv_agent.ingestion.job_finder import (
    JobFinderResponse,
    JobScope,
    find_matching_jobs,
)
from cv_agent.observability import get_tracing_status, init_phoenix_tracing
from cv_agent.renderer.rendercv_bridge import export_and_render_pdf
from cv_agent.schemas import (
    CompanyDeepDiveReport,
    CompanyIntel,
    MarketSnapshot,
    MasterProfile,
)
from cv_agent.storage.applications_db import (
    ApplicationCreate,
    ApplicationsDatabase,
    ApplicationUpdate,
    JobApplication,
)
from cv_agent.storage.companies_db import CompanyKnowledgeDatabase, CompanyKnowledgeRecord
from cv_agent.storage.market_db import MarketDatabase

app = FastAPI(
    title="CV & Job Market Intelligence AI Agent API",
    version="0.3.0",
    description="Local-first AI Agent + dbt-duckdb + Dagster + Arize Phoenix Observability.",
)

init_phoenix_tracing()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TailorRequest(BaseModel):
    target_role: str = "Data Engineer"
    target_company: str = ""
    job_url: str = ""
    region: str = "Indonesia"
    target_jd_text: str = ""
    output_language: Literal["en", "id"] = "en"
    use_llm: bool = True
    allow_web_research: bool = True
    master_profile: MasterProfile | None = None


class CompanyDeepDiveRequest(BaseModel):
    company_name: str = ""
    target_role: str = "Data Engineer"
    job_url: str = ""
    pasted_jd: str = ""
    language: Literal["id", "en"] = "id"
    use_llm: bool = True
    allow_web: bool = True


class MarketRefreshRequest(BaseModel):
    role: str = "Data Engineer"
    location: str = "Indonesia"
    results_wanted: int = Field(default=25, ge=5, le=100)
    greenhouse_boards: list[str] = Field(default_factory=list)


class JobFinderRequest(BaseModel):
    roles: list[str] = Field(default_factory=lambda: ["Data Engineer", "Data Quality Engineer"])
    scope: JobScope = "both"
    hours_old: int = Field(default=168, ge=24, le=720)
    limit_per_source: int = Field(default=12, ge=3, le=30)
    allow_live_fetch: bool = True


def _resolve_default_profile() -> MasterProfile:
    primary = settings.data_dir / "master_profile.yaml"
    example = settings.data_dir / "master_profile.example.yaml"
    path = primary if primary.exists() else example
    if not path.exists():
        raise HTTPException(status_code=404, detail="No master_profile.yaml found in data/")
    return load_master_profile(path)


def _build_initial_state(req: TailorRequest, profile: MasterProfile) -> dict:
    return {
        "master_profile": profile,
        "target_role": req.target_role,
        "target_company": req.target_company,
        "job_url": req.job_url,
        "region": req.region,
        "target_jd_text": req.target_jd_text,
        "output_language": req.output_language,
        "use_llm": req.use_llm,
        "allow_web_research": req.allow_web_research,
        "max_revisions": 3,
        "events": [],
    }


@app.get("/health")
def health() -> dict[str, str]:
    active_model = (
        settings.ollama_model if settings.llm_provider == "ollama" else settings.openai_model
    )
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "model": active_model,
    }


@app.get("/api/platform/status")
def platform_status() -> dict:
    """Inspect Phase 2 Data Platform (dbt Gold marts, DuckDB) & Arize Phoenix tracing health."""
    import duckdb

    dbt_marts: dict[str, int] = {}
    bronze_counts: dict[str, int] = {}
    if settings.duckdb_path.exists():
        try:
            with duckdb.connect(str(settings.duckdb_path), read_only=True) as con:
                for tbl in ("job_postings", "job_skills", "company_profiles"):
                    try:
                        r = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                        bronze_counts[tbl] = int(r[0]) if r else 0
                    except Exception:
                        pass
                for mart in (
                    "main_gold.mart_role_skill_trends",
                    "main_gold.mart_company_job_overview",
                    "main_gold.mart_daily_ingestion_health",
                ):
                    try:
                        r = con.execute(f"SELECT COUNT(*) FROM {mart}").fetchone()
                        dbt_marts[mart] = int(r[0]) if r else 0
                    except Exception:
                        pass
        except Exception:
            pass

    return {
        "duckdb_path": str(settings.duckdb_path),
        "bronze_tables": bronze_counts,
        "dbt_gold_marts": dbt_marts,
        "dbt_ready": len(dbt_marts) > 0,
        "dagster_assets": [
            "bronze_company_knowledge",
            "bronze_daily_jobs",
            "dbt_medallion_warehouse",
        ],
        "phoenix_tracing": get_tracing_status(),
    }


@app.get("/api/profile/default", response_model=MasterProfile)
def get_default_profile() -> MasterProfile:
    return _resolve_default_profile()


@app.get("/api/company/research", response_model=CompanyIntel)
def lookup_company(
    company: str,
    role: str = "Data Engineer",
    job_url: str = "",
) -> CompanyIntel:
    db = MarketDatabase()
    return research_company_and_jd(
        company_name=company,
        target_role=role,
        job_url=job_url,
        db=db,
    )


@app.post("/api/company/deep-dive", response_model=CompanyDeepDiveReport)
def company_deep_dive(req: CompanyDeepDiveRequest) -> CompanyDeepDiveReport:
    if not (req.company_name.strip() or req.job_url.strip() or req.pasted_jd.strip()):
        raise HTTPException(
            status_code=400,
            detail="Isi minimal nama perusahaan, link lowongan, atau teks Job Description.",
        )
    profile = _resolve_default_profile()
    db = MarketDatabase()
    return generate_company_deep_dive(
        company_name=req.company_name,
        target_role=req.target_role,
        job_url=req.job_url,
        pasted_jd=req.pasted_jd,
        language=req.language,
        use_llm=req.use_llm,
        allow_web=req.allow_web,
        profile=profile,
        db=db,
    )


@app.post("/api/company/deep-dive/stream")
def company_deep_dive_stream(req: CompanyDeepDiveRequest) -> StreamingResponse:
    """Stream real-time progress stages + heartbeat while local LLM analyzes the company."""
    if not (req.company_name.strip() or req.job_url.strip() or req.pasted_jd.strip()):
        raise HTTPException(
            status_code=400,
            detail="Isi minimal nama perusahaan, link lowongan, atau teks Job Description.",
        )
    profile = _resolve_default_profile()
    db = MarketDatabase()

    def event_generator():
        q: queue.Queue[dict] = queue.Queue()
        start_ts = time.monotonic()

        def _on_progress(stage: str, percent: int, message: str) -> None:
            q.put(
                {
                    "type": "progress",
                    "stage": stage,
                    "percent": percent,
                    "message": message,
                    "elapsed_sec": round(time.monotonic() - start_ts, 1),
                }
            )

        def _worker() -> None:
            try:
                report = generate_company_deep_dive(
                    company_name=req.company_name,
                    target_role=req.target_role,
                    job_url=req.job_url,
                    pasted_jd=req.pasted_jd,
                    language=req.language,
                    use_llm=req.use_llm,
                    allow_web=req.allow_web,
                    profile=profile,
                    db=db,
                    on_progress=_on_progress,
                )
                q.put(
                    {
                        "type": "done",
                        "stage": "finalize",
                        "percent": 100,
                        "elapsed_sec": round(time.monotonic() - start_ts, 1),
                        "report": report.model_dump(mode="json"),
                    }
                )
            except Exception as exc:
                q.put({"type": "error", "message": str(exc)})

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        last_stage = "research"
        last_pct = 10
        while True:
            try:
                event = q.get(timeout=2.0)
                last_stage = str(event.get("stage", last_stage))
                last_pct = int(event.get("percent", last_pct))
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                # Smooth live heartbeat so the UI shows the local LLM is actively generating
                elapsed = round(time.monotonic() - start_ts, 1)
                if last_stage == "llm_analysis" and last_pct < 93:
                    last_pct = min(93, last_pct + 2)
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "heartbeat",
                            "stage": last_stage,
                            "percent": last_pct,
                            "elapsed_sec": elapsed,
                        }
                    )
                    + "\n\n"
                )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/market/trends", response_model=MarketSnapshot)
def get_market_trends(role: str = "Data Engineer", region: str = "Indonesia") -> MarketSnapshot:
    db = MarketDatabase()
    return db.get_market_snapshot(role=role, region=region)


@app.post("/api/market/refresh")
async def refresh_market(req: MarketRefreshRequest) -> dict[str, int | str]:
    db = MarketDatabase()
    total_ingested = 0

    for board in req.greenhouse_boards:
        df = await fetch_greenhouse_board(board_token=board, role_filter=req.role)
        total_ingested += db.upsert_jobs(df)

    try:
        df_jobspy = fetch_jobs_jobspy(
            role=req.role,
            location=req.location,
            results_wanted=req.results_wanted,
        )
        total_ingested += db.upsert_jobs(df_jobspy)
    except RuntimeError as exc:
        if total_ingested == 0:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "refreshed", "role": req.role, "jobs_ingested": total_ingested}


@app.post("/api/cv/parse-file")
async def parse_cv_file(file: Annotated[UploadFile, File(...)]) -> dict[str, str]:
    filename = file.filename or "cv.pdf"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only .pdf and .docx files are supported.")
    tmp_path = settings.outputs_dir / f"upload_{Path(filename).name}"
    tmp_path.write_bytes(await file.read())
    markdown = extract_cv_file(tmp_path)
    return {"filename": filename, "markdown": markdown}


@app.post("/api/cv/tailor")
def tailor_cv(req: TailorRequest) -> dict:
    profile = req.master_profile or _resolve_default_profile()
    graph = build_cv_agent_graph()
    final_state = graph.invoke(_build_initial_state(req, profile))
    return {
        "company_intel": final_state["company_intel"].model_dump(mode="json"),
        "market_snapshot": final_state["market_snapshot"].model_dump(mode="json"),
        "gap_audit": final_state["gap_audit"].model_dump(mode="json"),
        "tailored_cv": final_state["tailored_cv"].model_dump(mode="json"),
        "fact_check": final_state["fact_check"].model_dump(mode="json"),
        "events": final_state.get("events", []),
    }


@app.post("/api/cv/tailor/stream")
def tailor_cv_stream(req: TailorRequest) -> StreamingResponse:
    """Stream each LangGraph node execution to the Next.js UI via Server-Sent Events (SSE)."""
    profile = req.master_profile or _resolve_default_profile()
    graph = build_cv_agent_graph()

    def event_generator():
        initial_state = _build_initial_state(req, profile)
        latest_payload: dict = {}
        for chunk in graph.stream(initial_state):
            for node_name, node_output in chunk.items():
                serialized = {
                    k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                    for k, v in node_output.items()
                }
                latest_payload.update(serialized)
                yield f"data: {json.dumps({'node': node_name, 'data': serialized})}\n\n"
        yield f"data: {json.dumps({'node': 'done', 'data': latest_payload})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/cv/render")
def render_cv(req: TailorRequest) -> dict[str, str]:
    profile = req.master_profile or _resolve_default_profile()
    graph = build_cv_agent_graph()
    final_state = graph.invoke(_build_initial_state(req, profile))
    out = export_and_render_pdf(profile, final_state["tailored_cv"])
    if out.get("pdf_path"):
        out["download_url"] = f"/api/cv/download/{out['filename']}"
    return out


@app.get("/api/cv/download/{filename}")
def download_rendered_pdf(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    pdf_path = settings.outputs_dir / "rendercv_out" / safe_name
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Rendered PDF not found.")
    return FileResponse(path=pdf_path, media_type="application/pdf", filename=safe_name)


# ---------------------------------------------------------------------------
# Persistent Job Application Tracker (DuckDB)
# ---------------------------------------------------------------------------


@app.get("/api/applications", response_model=list[JobApplication])
def list_applications() -> list[JobApplication]:
    return ApplicationsDatabase().list_applications()


@app.post("/api/applications", response_model=JobApplication)
def create_application(payload: ApplicationCreate) -> JobApplication:
    return ApplicationsDatabase().create_application(payload)


@app.patch("/api/applications/{app_id}", response_model=JobApplication)
def update_application(app_id: str, patch: ApplicationUpdate) -> JobApplication:
    updated = ApplicationsDatabase().update_application(app_id, patch)
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found.")
    return updated


@app.delete("/api/applications/{app_id}")
def delete_application(app_id: str) -> dict[str, bool]:
    deleted = ApplicationsDatabase().delete_application(app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found.")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Local Ollama Mock Interview Prep Chat (Token-by-Token SSE)
# ---------------------------------------------------------------------------


@app.post("/api/interview/chat/stream")
def interview_chat_stream(req: InterviewChatRequest) -> StreamingResponse:
    profile = _resolve_default_profile()

    def token_generator():
        try:
            for token in stream_interview_reply(req, profile):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Dedicated Company Knowledge Base (DuckDB: Positives, Keluh Kesah, IDR)
# ---------------------------------------------------------------------------


@app.get("/api/companies/knowledge", response_model=list[CompanyKnowledgeRecord])
def list_company_knowledge(q: str = "") -> list[CompanyKnowledgeRecord]:
    return CompanyKnowledgeDatabase().list_companies(query=q)


@app.post("/api/companies/knowledge", response_model=CompanyKnowledgeRecord)
def upsert_company_knowledge(record: CompanyKnowledgeRecord) -> CompanyKnowledgeRecord:
    return CompanyKnowledgeDatabase().upsert_company(record)


@app.delete("/api/companies/knowledge/{company_name}")
def delete_company_knowledge(company_name: str) -> dict[str, bool]:
    deleted = CompanyKnowledgeDatabase().delete_company(company_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Company record not found.")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# CV-Matched Job Finder (Indonesia + Global Remote + HR Post Discovery)
# ---------------------------------------------------------------------------


@app.post("/api/jobs/find", response_model=JobFinderResponse)
def find_jobs_for_cv(req: JobFinderRequest) -> JobFinderResponse:
    profile = _resolve_default_profile()
    return find_matching_jobs(
        profile=profile,
        roles=req.roles,
        scope=req.scope,
        hours_old=req.hours_old,
        limit_per_source=req.limit_per_source,
        allow_live_fetch=req.allow_live_fetch,
    )


@app.get("/api/jobs/saved", response_model=JobFinderResponse)
def get_saved_matched_jobs(scope: JobScope = "both") -> JobFinderResponse:
    profile = _resolve_default_profile()
    return find_matching_jobs(
        profile=profile,
        scope=scope,
        allow_live_fetch=False,
    )


# ---------------------------------------------------------------------------
# System-Aware CareerOS AI Copilot Chatbot (Token-by-Token SSE)
# ---------------------------------------------------------------------------


@app.post("/api/copilot/chat/stream")
def copilot_chat_stream(req: CopilotChatRequest) -> StreamingResponse:
    profile = _resolve_default_profile()
    company_db = CompanyKnowledgeDatabase()
    market_db = MarketDatabase()
    apps_db = ApplicationsDatabase()

    def event_generator():
        try:
            sources, token_iter = stream_copilot_reply(
                req=req,
                profile=profile,
                company_db=company_db,
                market_db=market_db,
                apps_db=apps_db,
            )
            yield f"data: {json.dumps({'type': 'context', 'sources': sources})}\n\n"
            for token in token_iter:
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
