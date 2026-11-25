import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

import httpx
import pandas as pd
from pydantic import BaseModel, Field

from cv_agent.config import settings
from cv_agent.ingestion.company_research import infer_industry, strip_html
from cv_agent.ingestion.job_fetcher import compute_job_fingerprint, fetch_jobs_jobspy
from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.schemas import MasterProfile
from cv_agent.storage.companies_db import CompanyKnowledgeDatabase
from cv_agent.storage.market_db import MarketDatabase

JobScope = Literal["indonesia", "remote", "both"]

DATA_ROLE_POSITIVE_TERMS = (
    "data",
    "analytics",
    "bi ",
    "business intelligence",
    "etl",
    "elt",
    "dbt",
    "sql",
    "warehouse",
    "lakehouse",
    "flink",
    "spark",
    "kafka",
    "streaming",
    "machine learning",
    "ml ",
    "ai ",
    "database",
    "quality",
)

NON_DATA_EXCLUDE_TERMS = (
    "roaster",
    "barista",
    "driver",
    "courier",
    "after-sales",
    "data center power",
    "data center technician",
    "electrician",
    "mechanic",
    "chef",
    "nurse",
    "sales executive",
)


def is_relevant_data_role(title: str) -> bool:
    """Filter out unrelated non-data postings (e.g. coffee roaster mentioning 'airflow')."""
    lowered = f" {(title or '').lower()} "
    if any(bad in lowered for bad in NON_DATA_EXCLUDE_TERMS):
        return False
    return any(good in lowered for good in DATA_ROLE_POSITIVE_TERMS)


class MatchedJobListing(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    work_mode: Literal["Remote", "Hybrid", "On-site"]
    source: str
    posted_at: str
    posted_age_label: str
    job_url: str
    salary_info: str = ""
    company_industry: str = "Technology"
    company_about: str = ""
    company_verdict: str = ""
    company_rating: float | None = None
    company_salary_idr: str = ""
    description: str = ""
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    match_score: float = Field(ge=0.0, le=100.0)


class HrSearchShortcut(BaseModel):
    platform: str
    title: str
    description: str
    search_url: str


class JobFinderResponse(BaseModel):
    query_roles: list[str]
    scope: JobScope
    total_fetched: int
    jobs: list[MatchedJobListing] = Field(default_factory=list)
    hr_post_shortcuts: list[HrSearchShortcut] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def format_posted_age(posted_raw: str) -> str:
    """Convert ISO/date string into human-friendly Indonesian age label (e.g. '2 hari lalu')."""
    text = (posted_raw or "").strip()
    if not text or text.lower() in ("nan", "none", "nat"):
        return "Baru-baru ini"

    parsed: datetime | None = None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(text[:19], fmt[: len(text[:19])])
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text[:16]

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    delta = now - parsed
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return "Baru saja (< 1 jam)"
    if hours < 24:
        return f"{hours} jam lalu"
    days = delta.days
    if days == 1:
        return "1 hari lalu"
    if days < 30:
        return f"{days} hari lalu"
    months = max(1, days // 30)
    return f"{months} bulan lalu"


def detect_work_mode(title: str, location: str, description: str, source: str) -> Literal[
    "Remote", "Hybrid", "On-site"
]:
    if source in ("remotive", "remoteok"):
        return "Remote"
    blob = f"{title} {location} {description[:500]}".lower()
    if "remote" in blob or "work from anywhere" in blob or "wfa" in blob:
        return "Remote"
    if "hybrid" in blob:
        return "Hybrid"
    return "On-site"


def fetch_remotive_remote_jobs(role_keywords: list[str], limit: int = 20) -> list[dict]:
    """Fetch free, public remote data jobs from Remotive API (no API key needed)."""
    results: list[dict] = []
    headers = {"User-Agent": "cv-job-market-agent/0.2"}
    try:
        with httpx.Client(timeout=12.0, headers=headers) as client:
            resp = client.get("https://remotive.com/api/remote-jobs?category=data&limit=40")
            if resp.status_code != 200:
                return []
            jobs = resp.json().get("jobs", [])
    except Exception:
        return []

    needles = [k.lower() for k in role_keywords]
    now = datetime.now(UTC).isoformat()
    for job in jobs:
        title = str(job.get("title") or "")
        company = str(job.get("company_name") or "Unknown")
        desc = strip_html(str(job.get("description") or ""))
        title_lower = title.lower()
        if needles and not any(
            tok in title_lower
            for kw in needles
            for tok in kw.split()
            if len(tok) > 3
        ):
            continue
        results.append(
            {
                "job_id": compute_job_fingerprint(company, title, desc),
                "source": "remotive",
                "search_role": role_keywords[0] if role_keywords else "Data Engineer",
                "title": title,
                "company": company,
                "location": str(job.get("candidate_required_location") or "Worldwide Remote"),
                "job_url": str(job.get("url") or ""),
                "description": desc[:5000],
                "posted_at": str(job.get("publication_date") or now),
                "scraped_at": now,
                "salary_info": str(job.get("salary") or ""),
            }
        )
        if len(results) >= limit:
            break
    return results


def fetch_arbeitnow_remote_jobs(role_keywords: list[str], limit: int = 15) -> list[dict]:
    """Fetch free, public tech/remote jobs from Arbeitnow API."""
    results: list[dict] = []
    headers = {"User-Agent": "cv-job-market-agent/0.2"}
    try:
        with httpx.Client(timeout=12.0, headers=headers) as client:
            resp = client.get("https://www.arbeitnow.com/api/job-board-api")
            if resp.status_code != 200:
                return []
            jobs = resp.json().get("data", [])
    except Exception:
        return []

    now = datetime.now(UTC).isoformat()
    data_terms = ("data", "analytics", "etl", "dbt", "bi ", "sql", "warehouse")
    for job in jobs:
        title = str(job.get("title") or "")
        if not any(t in title.lower() for t in data_terms):
            continue
        is_remote = bool(job.get("remote"))
        if not is_remote:
            continue
        company = str(job.get("company_name") or "Unknown")
        desc = strip_html(str(job.get("description") or ""))
        created_ts = job.get("created_at")
        posted_iso = (
            datetime.fromtimestamp(int(created_ts), tz=UTC).isoformat()
            if isinstance(created_ts, (int, float))
            else now
        )
        results.append(
            {
                "job_id": compute_job_fingerprint(company, title, desc),
                "source": "arbeitnow",
                "search_role": role_keywords[0] if role_keywords else "Data Engineer",
                "title": title,
                "company": company,
                "location": f"{job.get('location') or 'Remote'} (Remote)",
                "job_url": str(job.get("url") or ""),
                "description": desc[:5000],
                "posted_at": posted_iso,
                "scraped_at": now,
                "salary_info": "",
            }
        )
        if len(results) >= limit:
            break
    return results


def build_hr_search_shortcuts(
    profile: MasterProfile,
    roles: list[str],
) -> list[HrSearchShortcut]:
    """
    Generate smart 1-click Boolean search links to discover live Indonesian HR & Recruiter
    hiring posts (respecting LinkedIn login walls without bypassing authentication).
    """
    primary_roles = roles[:3] or ["Data Engineer", "Data Quality", "Analytics Engineer"]
    role_or = " OR ".join(f'"{r}"' for r in primary_roles)
    top_skills = sorted(profile.all_verified_skills())
    highlight_skills = [
        s for s in ("dbt", "SQL", "BigQuery", "ClickHouse", "Airflow", "Python", "Kafka")
        if any(s.lower() in v.lower() for v in top_skills)
    ][:4] or ["SQL", "Python"]
    skill_or = " OR ".join(f'"{s}"' for s in highlight_skills)

    li_posts_query = (
        f'("hiring" OR "we are looking for" OR "loker") ({role_or}) '
        f'("Indonesia" OR "Jakarta" OR "Remote")'
    )
    li_posts_url = (
        "https://www.linkedin.com/search/results/content/?datePosted=%22past-week%22"
        f"&keywords={quote_plus(li_posts_query)}&sortBy=%22date_posted%22"
    )

    li_remote_query = f'("hiring" OR "remote") ({role_or}) ({skill_or})'
    li_remote_url = (
        "https://www.linkedin.com/search/results/content/?datePosted=%22past-week%22"
        f"&keywords={quote_plus(li_remote_query)}&sortBy=%22date_posted%22"
    )

    google_xray_query = (
        f'site:linkedin.com/posts ("hiring" OR "we\'re hiring" OR "open role") '
        f'({role_or}) ("Indonesia" OR "Jakarta")'
    )
    google_xray_url = f"https://www.google.com/search?q={quote_plus(google_xray_query)}&tbs=qdr:w"

    glints_url = (
        "https://glints.com/id/opportunities/jobs/explore?"
        f"keyword={quote_plus(primary_roles[0])}&country=ID"
    )
    jobstreet_slug = re.sub(r"[^a-z0-9]+", "-", primary_roles[0].lower()).strip("-")
    jobstreet_url = f"https://id.jobstreet.com/id/{jobstreet_slug}-jobs"

    return [
        HrSearchShortcut(
            platform="LinkedIn HR Posts (Indonesia)",
            title="Postingan HR Indonesia (7 Hari Terakhir)",
            description=(
                "Mencari postingan langsung dari HR/Recruiter/Hiring Manager di Indonesia "
                f"yang mencari {role_or} dalam 7 hari terakhir."
            ),
            search_url=li_posts_url,
        ),
        HrSearchShortcut(
            platform="LinkedIn HR Posts (Remote Global)",
            title="Postingan Hiring Manager Remote (Sesuai Stack CV)",
            description=(
                f"Mencari postingan hiring remote yang cocok dengan stack utama kamu ({skill_or})."
            ),
            search_url=li_remote_url,
        ),
        HrSearchShortcut(
            platform="Google X-Ray (Public HR Posts)",
            title="X-Ray Search Postingan HR Publik (Minggu Ini)",
            description=(
                "Mencari postingan LinkedIn publik dari HR Indonesia lewat Google Search "
                "yang diindeks dalam 7 hari terakhir."
            ),
            search_url=google_xray_url,
        ),
        HrSearchShortcut(
            platform="JobStreet Indonesia",
            title=f"Lowongan {primary_roles[0]} di JobStreet ID",
            description="Portal kerja lokal utama dengan info perusahaan & range gaji IDR.",
            search_url=jobstreet_url,
        ),
        HrSearchShortcut(
            platform="Glints Indonesia",
            title=f"Lowongan {primary_roles[0]} di Glints ID",
            description="Startup & tech company Indonesia yang sering menampilkan range gaji IDR.",
            search_url=glints_url,
        ),
    ]


def score_and_enrich_jobs(
    raw_jobs: list[dict],
    profile: MasterProfile,
    company_db: CompanyKnowledgeDatabase,
    target_roles: list[str],
) -> list[MatchedJobListing]:
    """Score every job against MasterProfile verified skills and enrich with DuckDB Company KB."""
    extractor = SkillTaxonomyExtractor()
    verified_skills = {extractor.normalize(s) for s in profile.all_verified_skills()}
    role_tokens = {
        tok
        for role in (target_roles or profile.profile.target_roles)
        for tok in role.lower().split()
        if len(tok) > 2
    }

    scored: list[MatchedJobListing] = []
    seen_ids: set[str] = set()

    for raw in raw_jobs:
        job_id = str(raw.get("job_id") or "")
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        title = str(raw.get("title") or "Data Role")
        if not is_relevant_data_role(title):
            continue
        company = str(raw.get("company") or "Unknown")
        location = str(raw.get("location") or "")
        source = str(raw.get("source") or "web")
        desc = str(raw.get("description") or "")
        posted_at = str(raw.get("posted_at") or "")
        job_url = str(raw.get("job_url") or "")
        salary_info = str(raw.get("salary_info") or "")

        extracted = [s.canonical for s in extractor.extract(f"{title}\n{desc}")]
        unique_jd_skills = list(dict.fromkeys(extracted))
        matched = [s for s in unique_jd_skills if s in verified_skills]
        missing = [s for s in unique_jd_skills if s not in verified_skills]

        # Skill match (up to 65 pts) + Role title alignment (up to 25 pts) + Seniority fit (10 pts)
        if unique_jd_skills:
            skill_pts = (len(matched) / len(unique_jd_skills)) * 65.0
        else:
            skill_pts = 35.0

        title_lower = title.lower()
        title_hits = sum(1 for tok in role_tokens if tok in title_lower)
        title_pts = min(25.0, title_hits * 12.5)

        seniority_penalty = 0.0
        if any(w in title_lower for w in ("principal", "staff", "director", "vp ", "head of")):
            seniority_penalty = 12.0
        elif "senior" in title_lower and profile.profile.years_of_experience < 3.0:
            seniority_penalty = 6.0
        seniority_pts = max(0.0, 10.0 - seniority_penalty)

        match_score = round(min(99.0, max(15.0, skill_pts + title_pts + seniority_pts)), 1)

        # Enrich with DuckDB Company Knowledge Base if available
        kb = company_db.find_company(company)
        industry = kb.industry if kb else infer_industry(f"{company} {desc[:1200]}")
        about = kb.condition_summary if kb else (desc[:240].strip() if desc else "")
        verdict = kb.verdict if kb else ""
        rating = kb.overall_rating if kb else None
        if kb and profile.profile.years_of_experience < 2.5:
            kb_salary = kb.salary_idr_junior
        elif kb:
            kb_salary = kb.salary_idr_mid
        else:
            kb_salary = ""

        scored.append(
            MatchedJobListing(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                work_mode=detect_work_mode(title, location, desc, source),
                source=source,
                posted_at=posted_at,
                posted_age_label=format_posted_age(posted_at),
                job_url=job_url,
                salary_info=salary_info,
                company_industry=industry,
                company_about=about,
                company_verdict=verdict,
                company_rating=rating,
                company_salary_idr=kb_salary,
                description=desc[:2500],
                matched_skills=matched,
                missing_skills=missing[:8],
                match_score=match_score,
            )
        )

    scored.sort(key=lambda j: j.match_score, reverse=True)
    return scored


def find_matching_jobs(
    profile: MasterProfile,
    roles: list[str] | None = None,
    scope: JobScope = "both",
    hours_old: int = 168,
    limit_per_source: int = 15,
    allow_live_fetch: bool = True,
    market_db: MarketDatabase | None = None,
    company_db: CompanyKnowledgeDatabase | None = None,
) -> JobFinderResponse:
    """
    Search live Indonesia + Global Remote jobs, store into DuckDB, score against MasterProfile,
    and return ranked listings + Indonesian HR post discovery links.
    """
    query_roles = [r.strip() for r in (roles or profile.profile.target_roles[:2]) if r.strip()]
    if not query_roles:
        query_roles = ["Data Engineer"]

    mdb = market_db or MarketDatabase()
    cdb = company_db or CompanyKnowledgeDatabase()
    raw_jobs: list[dict] = []
    warnings: list[str] = []

    if allow_live_fetch:
        # 1. Indonesia local jobs via python-jobspy (LinkedIn + Indeed)
        if scope in ("indonesia", "both"):
            for role in query_roles[:2]:
                try:
                    df = fetch_jobs_jobspy(
                        role=role,
                        location="Indonesia",
                        results_wanted=limit_per_source,
                        hours_old=hours_old,
                        sites=["linkedin", "indeed"],
                    )
                    if not df.empty:
                        mdb.upsert_jobs(df)
                        raw_jobs.extend(df.to_dict(orient="records"))
                except Exception as exc:
                    warnings.append(f"JobSpy Indonesia ({role}): {exc}")

        # 2. Global Remote jobs via free public APIs (Remotive + Arbeitnow)
        if scope in ("remote", "both"):
            remotive_jobs = fetch_remotive_remote_jobs(query_roles, limit=limit_per_source)
            arbeitnow_jobs = fetch_arbeitnow_remote_jobs(query_roles, limit=10)
            remote_batch = remotive_jobs + arbeitnow_jobs
            if remote_batch:
                df_remote = pd.DataFrame(remote_batch)
                mdb.upsert_jobs(df_remote.drop(columns=["salary_info"], errors="ignore"))
                raw_jobs.extend(remote_batch)

    # Also include any previously stored DuckDB postings if live list is small
    if len(raw_jobs) < 5:
        cached = mdb.list_recent_postings(limit=30)
        raw_jobs.extend(cached)

    scored = score_and_enrich_jobs(raw_jobs, profile, cdb, query_roles)

    # Apply scope filter cleanly when merging cached postings
    if scope == "remote":
        scored = [j for j in scored if j.work_mode == "Remote"]

    source_counts: dict[str, int] = {}
    for j in scored:
        source_counts[j.source] = source_counts.get(j.source, 0) + 1

    return JobFinderResponse(
        query_roles=query_roles,
        scope=scope,
        total_fetched=len(scored),
        jobs=scored[:40],
        hr_post_shortcuts=build_hr_search_shortcuts(profile, query_roles),
        source_counts=source_counts,
        warnings=warnings,
    )


def export_daily_snapshot(
    market_db: MarketDatabase,
    snapshot_dir: Path | None = None,
) -> dict[str, str | int]:
    """
    Export clean, deduplicated public job postings from DuckDB to a compact Parquet file
    + JSON market summary suitable for daily GitHub Actions auto-commits.
    """
    out_dir = snapshot_dir or (settings.data_dir / "snapshots" / "daily")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        r for r in market_db.list_recent_postings(limit=500) if is_relevant_data_role(r["title"])
    ]
    parquet_path = out_dir / "jobs_latest.parquet"
    if rows:
        df = pd.DataFrame(rows).drop_duplicates(subset=["job_id"])
        df.to_parquet(parquet_path, index=False)

    snap = market_db.get_market_snapshot(role="Data Engineer", region="Indonesia")
    summary_path = out_dir / "market_summary.json"
    summary_payload = {
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "total_public_jobs": len(rows),
        "data_engineer_snapshot": snap.model_dump(mode="json"),
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "total_jobs_exported": len(rows),
        "parquet_path": str(parquet_path),
        "summary_path": str(summary_path),
    }
