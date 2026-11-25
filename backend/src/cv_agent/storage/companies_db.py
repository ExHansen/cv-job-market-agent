import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import duckdb
import yaml
from pydantic import BaseModel, Field

from cv_agent.config import settings

CompanyVerdict = Literal["Recommended", "Mixed - Selective", "Caution"]


class CompanyKnowledgeRecord(BaseModel):
    company_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    industry: str = "Technology"
    company_stage: str = ""
    headquarters: str = "Indonesia"
    overall_rating: float = Field(default=3.8, ge=1.0, le=5.0)
    work_life_balance: float = Field(default=3.5, ge=1.0, le=5.0)
    culture_score: float = Field(default=3.8, ge=1.0, le=5.0)
    career_growth: float = Field(default=3.8, ge=1.0, le=5.0)
    verdict: CompanyVerdict = "Mixed - Selective"
    condition_summary: str = ""
    positives: list[str] = Field(default_factory=list)
    kesah_kesuh: list[str] = Field(default_factory=list)
    common_positions: list[str] = Field(default_factory=list)
    typical_tech_stack: list[str] = Field(default_factory=list)
    typical_jd_summary: str = ""
    salary_idr_junior: str = ""
    salary_idr_mid: str = ""
    salary_idr_senior: str = ""
    source_notes: str = "User / Curated Knowledge Base"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CompanyKnowledgeDatabase:
    """
    Dedicated DuckDB knowledge base storing structured company conditions, employee positives,
    keluh kesah (pain points), common positions, JD summaries, and IDR salary ranges.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        seed_path: Path | None = None,
    ) -> None:
        self.db_path = db_path or settings.duckdb_path
        self.seed_path = seed_path or (settings.config_dir / "company_knowledge_seed.yaml")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._ensure_seeded()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS company_profiles (
                    company_key VARCHAR PRIMARY KEY,
                    company_name VARCHAR NOT NULL,
                    aliases_json VARCHAR,
                    industry VARCHAR,
                    company_stage VARCHAR,
                    headquarters VARCHAR,
                    overall_rating DOUBLE,
                    work_life_balance DOUBLE,
                    culture_score DOUBLE,
                    career_growth DOUBLE,
                    verdict VARCHAR,
                    condition_summary VARCHAR,
                    positives_json VARCHAR,
                    kesah_kesuh_json VARCHAR,
                    common_positions_json VARCHAR,
                    tech_stack_json VARCHAR,
                    typical_jd_summary VARCHAR,
                    salary_idr_junior VARCHAR,
                    salary_idr_mid VARCHAR,
                    salary_idr_senior VARCHAR,
                    source_notes VARCHAR,
                    updated_at TIMESTAMP
                );
                """
            )

    def _ensure_seeded(self) -> None:
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) FROM company_profiles").fetchone()
            count = int(row[0]) if row and row[0] else 0
        if count > 0 or not self.seed_path.exists():
            return

        with self.seed_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for item in raw.get("companies") or []:
            self.upsert_company(CompanyKnowledgeRecord.model_validate(item))

    @staticmethod
    def _key(company_name: str) -> str:
        return " ".join(company_name.strip().lower().split())

    @staticmethod
    def _row_to_record(row: tuple) -> CompanyKnowledgeRecord:
        return CompanyKnowledgeRecord(
            company_name=str(row[1]),
            aliases=json.loads(row[2] or "[]"),
            industry=str(row[3] or "Technology"),
            company_stage=str(row[4] or ""),
            headquarters=str(row[5] or ""),
            overall_rating=float(row[6] or 3.8),
            work_life_balance=float(row[7] or 3.5),
            culture_score=float(row[8] or 3.8),
            career_growth=float(row[9] or 3.8),
            verdict=row[10] or "Mixed - Selective",
            condition_summary=str(row[11] or ""),
            positives=json.loads(row[12] or "[]"),
            kesah_kesuh=json.loads(row[13] or "[]"),
            common_positions=json.loads(row[14] or "[]"),
            typical_tech_stack=json.loads(row[15] or "[]"),
            typical_jd_summary=str(row[16] or ""),
            salary_idr_junior=str(row[17] or ""),
            salary_idr_mid=str(row[18] or ""),
            salary_idr_senior=str(row[19] or ""),
            source_notes=str(row[20] or ""),
            updated_at=row[21] if isinstance(row[21], datetime) else datetime.now(UTC),
        )

    def upsert_company(self, record: CompanyKnowledgeRecord) -> CompanyKnowledgeRecord:
        now = datetime.now(UTC)
        key = self._key(record.company_name)
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO company_profiles VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    key,
                    record.company_name.strip(),
                    json.dumps(record.aliases),
                    record.industry,
                    record.company_stage,
                    record.headquarters,
                    record.overall_rating,
                    record.work_life_balance,
                    record.culture_score,
                    record.career_growth,
                    record.verdict,
                    record.condition_summary,
                    json.dumps(record.positives),
                    json.dumps(record.kesah_kesuh),
                    json.dumps(record.common_positions),
                    json.dumps(record.typical_tech_stack),
                    record.typical_jd_summary,
                    record.salary_idr_junior,
                    record.salary_idr_mid,
                    record.salary_idr_senior,
                    record.source_notes,
                    now,
                ],
            )
        return record.model_copy(update={"updated_at": now})

    def list_companies(self, query: str = "") -> list[CompanyKnowledgeRecord]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM company_profiles ORDER BY overall_rating DESC, company_name ASC"
            ).fetchall()
        records = [self._row_to_record(r) for r in rows]
        needle = query.strip().lower()
        if not needle:
            return records
        return [
            r
            for r in records
            if needle in r.company_name.lower()
            or needle in r.industry.lower()
            or any(needle in a.lower() for a in r.aliases)
        ]

    def find_company(self, company_name: str) -> CompanyKnowledgeRecord | None:
        needle = self._key(company_name)
        if not needle:
            return None
        for rec in self.list_companies():
            if self._key(rec.company_name) == needle:
                return rec
            if needle in rec.company_name.lower() or rec.company_name.lower() in needle:
                return rec
            if any(a.lower() == needle or a.lower() in needle for a in rec.aliases):
                return rec
        return None

    def match_companies_in_text(self, text: str) -> list[CompanyKnowledgeRecord]:
        """Detect any companies from our DuckDB knowledge base mentioned in a user chat prompt."""
        lowered = (text or "").lower()
        matches: list[CompanyKnowledgeRecord] = []
        for rec in self.list_companies():
            terms = [rec.company_name.lower(), *(a.lower() for a in rec.aliases)]
            if any(t and len(t) >= 3 and t in lowered for t in terms):
                matches.append(rec)
        return matches

    def delete_company(self, company_name: str) -> bool:
        key = self._key(company_name)
        with self._connect() as con:
            exists = con.execute(
                "SELECT 1 FROM company_profiles WHERE company_key = ?", [key]
            ).fetchone()
            if not exists:
                return False
            con.execute("DELETE FROM company_profiles WHERE company_key = ?", [key])
        return True
