import os
import shutil
import subprocess
import sys
from pathlib import Path

import dagster as dg
import duckdb
from dagster import AssetExecutionContext

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = REPO_ROOT / "data_platform" / "dbt"
DATA_DIR = REPO_ROOT / "data"
CONFIG_DIR = REPO_ROOT / "config"
DUCKDB_PATH = DATA_DIR / "market.duckdb"

# Ensure backend package is importable when running `dagster dev` from data_platform/
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))


def _resolve_dbt_bin() -> str:
    scripts_dir = Path(sys.executable).parent
    for name in ("dbt.exe", "dbt"):
        candidate = scripts_dir / name
        if candidate.exists():
            return str(candidate)
    return shutil.which("dbt") or "dbt"


@dg.asset(
    group_name="bronze_ingestion",
    description="Ensures curated Indonesia company knowledge base is seeded in DuckDB.",
)
def bronze_company_knowledge(context: AssetExecutionContext) -> dg.MaterializeResult:
    from cv_agent.storage.companies_db import CompanyKnowledgeDatabase

    cdb = CompanyKnowledgeDatabase(
        db_path=DUCKDB_PATH,
        seed_path=CONFIG_DIR / "company_knowledge_seed.yaml",
    )
    records = cdb.list_companies()
    context.log.info(f"Company KB ready in DuckDB with {len(records)} records.")
    return dg.MaterializeResult(
        metadata={
            "company_count": dg.MetadataValue.int(len(records)),
            "duckdb_path": dg.MetadataValue.path(str(DUCKDB_PATH)),
        }
    )


@dg.asset(
    group_name="bronze_ingestion",
    description="Ingests daily Indonesia + Global Remote data jobs into DuckDB and Parquet.",
)
def bronze_daily_jobs(context: AssetExecutionContext) -> dg.MaterializeResult:
    from cv_agent.ingestion.cv_parser import load_master_profile
    from cv_agent.ingestion.job_finder import export_daily_snapshot, find_matching_jobs
    from cv_agent.storage.companies_db import CompanyKnowledgeDatabase
    from cv_agent.storage.market_db import MarketDatabase

    profile_path = DATA_DIR / "master_profile.yaml"
    if not profile_path.exists():
        profile_path = DATA_DIR / "master_profile.example.yaml"

    profile = load_master_profile(profile_path)
    mdb = MarketDatabase(db_path=DUCKDB_PATH)
    cdb = CompanyKnowledgeDatabase(
        db_path=DUCKDB_PATH,
        seed_path=CONFIG_DIR / "company_knowledge_seed.yaml",
    )

    res = find_matching_jobs(
        profile=profile,
        roles=["Data Engineer", "Data Quality Engineer", "Analytics Engineer"],
        scope="both",
        hours_old=72,
        limit_per_source=12,
        allow_live_fetch=True,
        market_db=mdb,
        company_db=cdb,
    )
    exported = export_daily_snapshot(mdb, snapshot_dir=DATA_DIR / "snapshots" / "daily")
    context.log.info(f"Daily ingestion complete: {res.total_fetched} matched jobs.")
    return dg.MaterializeResult(
        metadata={
            "matched_jobs": dg.MetadataValue.int(res.total_fetched),
            "exported_clean_jobs": dg.MetadataValue.int(int(exported["total_jobs_exported"])),
            "sources": dg.MetadataValue.json(res.source_counts),
            "parquet_snapshot": dg.MetadataValue.path(str(exported["parquet_path"])),
        }
    )


@dg.asset(
    group_name="silver_gold_dbt",
    deps=[bronze_company_knowledge, bronze_daily_jobs],
    description="Runs dbt-duckdb Medallion models (Silver views + Gold marts) and dbt tests.",
)
def dbt_medallion_warehouse(context: AssetExecutionContext) -> dg.MaterializeResult:
    env = os.environ.copy()
    env["DUCKDB_PATH"] = str(DUCKDB_PATH)
    dbt_bin = _resolve_dbt_bin()

    proc = subprocess.run(
        [dbt_bin, "build", "--profiles-dir", str(DBT_DIR), "--project-dir", str(DBT_DIR)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    context.log.info(proc.stdout)
    if proc.returncode != 0:
        context.log.error(proc.stderr)
        err_msg = proc.stderr or proc.stdout
        raise RuntimeError(f"dbt build failed (exit {proc.returncode}): {err_msg}")

    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        trend_rows = con.execute("SELECT COUNT(*) FROM main_gold.mart_role_skill_trends").fetchone()
        health_rows = con.execute(
            "SELECT COUNT(*) FROM main_gold.mart_daily_ingestion_health"
        ).fetchone()

    return dg.MaterializeResult(
        metadata={
            "dbt_exit_code": dg.MetadataValue.int(proc.returncode),
            "gold_skill_trend_rows": dg.MetadataValue.int(int(trend_rows[0]) if trend_rows else 0),
            "gold_health_rows": dg.MetadataValue.int(int(health_rows[0]) if health_rows else 0),
        }
    )


@dg.asset_check(asset=bronze_daily_jobs, description="Verify Bronze job_postings is non-empty.")
def check_bronze_jobs_not_empty() -> dg.AssetCheckResult:
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        row = con.execute("SELECT COUNT(*) FROM job_postings").fetchone()
        count = int(row[0]) if row and row[0] else 0
    return dg.AssetCheckResult(
        passed=count > 0,
        metadata={"row_count": dg.MetadataValue.int(count)},
    )


@dg.asset_check(
    asset=bronze_daily_jobs,
    description="Verify zero duplicate job_id primary keys in job_postings.",
)
def check_zero_duplicate_job_ids() -> dg.AssetCheckResult:
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        row = con.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT job_id) FROM job_postings"
        ).fetchone()
        dupes = int(row[0]) if row and row[0] else 0
    return dg.AssetCheckResult(
        passed=dupes == 0,
        metadata={"duplicate_count": dg.MetadataValue.int(dupes)},
    )


@dg.asset_check(
    asset=dbt_medallion_warehouse,
    description="Verify Gold mart_role_skill_trends is materialized and queryable.",
)
def check_gold_mart_populated() -> dg.AssetCheckResult:
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        row = con.execute("SELECT COUNT(*) FROM main_gold.mart_role_skill_trends").fetchone()
        count = int(row[0]) if row and row[0] else 0
    return dg.AssetCheckResult(
        passed=count > 0,
        metadata={"gold_rows": dg.MetadataValue.int(count)},
    )


daily_market_job = dg.define_asset_job(
    name="daily_careeros_market_pipeline",
    selection=[bronze_company_knowledge, bronze_daily_jobs, dbt_medallion_warehouse],
)

daily_market_schedule = dg.ScheduleDefinition(
    job=daily_market_job,
    cron_schedule="0 1 * * *",  # 08:00 WIB daily
)

defs = dg.Definitions(
    assets=[bronze_company_knowledge, bronze_daily_jobs, dbt_medallion_warehouse],
    asset_checks=[
        check_bronze_jobs_not_empty,
        check_zero_duplicate_job_ids,
        check_gold_mart_populated,
    ],
    jobs=[daily_market_job],
    schedules=[daily_market_schedule],
)
