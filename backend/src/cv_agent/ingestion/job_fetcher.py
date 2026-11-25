import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from cv_agent.config import settings


def compute_job_fingerprint(company: str, title: str, description: str) -> str:
    """Create a deterministic deduplication hash across multi-board job postings."""
    snippet = " ".join((description or "").lower().split())[:300]
    raw = f"{(company or '').strip().lower()}|{(title or '').strip().lower()}|{snippet}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_jobs_jobspy(
    role: str,
    location: str = "Indonesia",
    results_wanted: int = 30,
    hours_old: int = 168,
    sites: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch recent jobs via python-jobspy and normalize into the Bronze schema."""
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        raise RuntimeError(
            "python-jobspy is not installed. Run `uv sync --extra scraping` to enable scraping."
        ) from exc

    target_sites = sites or ["linkedin", "indeed", "google"]
    df = scrape_jobs(
        site_name=target_sites,
        search_term=role,
        location=location,
        results_wanted=results_wanted,
        hours_old=hours_old,
        country_indeed="Indonesia" if "indonesia" in location.lower() else "USA",
    )

    if df.empty:
        return pd.DataFrame()

    now = datetime.now(UTC)
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        company = str(row.get("company") or "Unknown")
        title = str(row.get("title") or role)
        description = str(row.get("description") or "")
        records.append(
            {
                "job_id": compute_job_fingerprint(company, title, description),
                "source": str(row.get("site") or "jobspy"),
                "search_role": role,
                "title": title,
                "company": company,
                "location": str(row.get("location") or location),
                "job_url": str(row.get("job_url") or ""),
                "description": description,
                "posted_at": str(row.get("date_posted") or now.date().isoformat()),
                "scraped_at": now.isoformat(),
            }
        )

    out_df = pd.DataFrame(records).drop_duplicates(subset=["job_id"])
    save_bronze_parquet(out_df, role=role, source="jobspy")
    return out_df


async def fetch_greenhouse_board(board_token: str, role_filter: str = "") -> pd.DataFrame:
    """Fetch structured job postings directly from a public Greenhouse ATS board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()

    now = datetime.now(UTC)
    records: list[dict[str, Any]] = []
    needle = role_filter.strip().lower()
    for job in payload.get("jobs", []):
        title = str(job.get("title") or "")
        if needle and needle not in title.lower():
            continue
        description = str(job.get("content") or "")
        location = str((job.get("location") or {}).get("name") or "")
        records.append(
            {
                "job_id": compute_job_fingerprint(board_token, title, description),
                "source": f"greenhouse:{board_token}",
                "search_role": role_filter or "all",
                "title": title,
                "company": board_token,
                "location": location,
                "job_url": str(job.get("absolute_url") or ""),
                "description": description,
                "posted_at": str(job.get("updated_at") or now.isoformat()),
                "scraped_at": now.isoformat(),
            }
        )

    out_df = pd.DataFrame(records).drop_duplicates(subset=["job_id"])
    if not out_df.empty:
        save_bronze_parquet(out_df, role=role_filter or "all", source=f"greenhouse_{board_token}")
    return out_df


def save_bronze_parquet(df: pd.DataFrame, role: str, source: str) -> Path:
    """Save raw scraped postings to Bronze Parquet files (ready for Week 3 dbt-duckdb)."""
    raw_dir = settings.data_dir / "raw" / "jobs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    slug = "_".join(role.lower().split())
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = raw_dir / f"{source}_{slug}_{stamp}.parquet"
    df.to_parquet(output_path, index=False)
    return output_path
