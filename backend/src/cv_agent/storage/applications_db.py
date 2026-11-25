from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import duckdb
from pydantic import BaseModel, Field

from cv_agent.config import settings

ApplicationStatus = Literal["wishlist", "applied", "interview", "offer", "rejected"]


class JobApplication(BaseModel):
    id: str
    company: str
    role: str
    status: ApplicationStatus = "wishlist"
    ats_score: float | None = None
    job_url: str = ""
    pdf_filename: str = ""
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    status: ApplicationStatus = "wishlist"
    ats_score: float | None = None
    job_url: str = ""
    pdf_filename: str = ""
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    ats_score: float | None = None
    job_url: str | None = None
    pdf_filename: str | None = None
    notes: str | None = None


class ApplicationsDatabase:
    """Persistent DuckDB store for the Job Hunt Application Tracker Kanban board."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.duckdb_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS job_applications (
                    id VARCHAR PRIMARY KEY,
                    company VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    ats_score DOUBLE,
                    job_url VARCHAR,
                    pdf_filename VARCHAR,
                    notes VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                """
            )

    @staticmethod
    def _row_to_model(row: tuple) -> JobApplication:
        return JobApplication(
            id=str(row[0]),
            company=str(row[1]),
            role=str(row[2]),
            status=row[3],
            ats_score=float(row[4]) if row[4] is not None else None,
            job_url=str(row[5] or ""),
            pdf_filename=str(row[6] or ""),
            notes=str(row[7] or ""),
            created_at=row[8] if isinstance(row[8], datetime) else datetime.now(UTC),
            updated_at=row[9] if isinstance(row[9], datetime) else datetime.now(UTC),
        )

    def list_applications(self) -> list[JobApplication]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT id, company, role, status, ats_score, job_url,
                       pdf_filename, notes, created_at, updated_at
                FROM job_applications
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def create_application(self, payload: ApplicationCreate) -> JobApplication:
        now = datetime.now(UTC)
        app_id = uuid4().hex[:12]
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO job_applications
                (id, company, role, status, ats_score, job_url, pdf_filename, notes,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    app_id,
                    payload.company.strip(),
                    payload.role.strip(),
                    payload.status,
                    payload.ats_score,
                    payload.job_url.strip(),
                    payload.pdf_filename.strip(),
                    payload.notes.strip(),
                    now,
                    now,
                ],
            )
        return JobApplication(
            id=app_id,
            company=payload.company.strip(),
            role=payload.role.strip(),
            status=payload.status,
            ats_score=payload.ats_score,
            job_url=payload.job_url.strip(),
            pdf_filename=payload.pdf_filename.strip(),
            notes=payload.notes.strip(),
            created_at=now,
            updated_at=now,
        )

    def update_application(self, app_id: str, patch: ApplicationUpdate) -> JobApplication | None:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT id, company, role, status, ats_score, job_url,
                       pdf_filename, notes, created_at, updated_at
                FROM job_applications
                WHERE id = ?
                """,
                [app_id],
            ).fetchone()
            if not row:
                return None

            current = self._row_to_model(row)
            now = datetime.now(UTC)
            updated = current.model_copy(
                update={
                    "status": patch.status if patch.status is not None else current.status,
                    "ats_score": (
                        patch.ats_score if patch.ats_score is not None else current.ats_score
                    ),
                    "job_url": patch.job_url if patch.job_url is not None else current.job_url,
                    "pdf_filename": (
                        patch.pdf_filename
                        if patch.pdf_filename is not None
                        else current.pdf_filename
                    ),
                    "notes": patch.notes if patch.notes is not None else current.notes,
                    "updated_at": now,
                }
            )
            con.execute(
                """
                UPDATE job_applications
                SET status = ?, ats_score = ?, job_url = ?, pdf_filename = ?,
                    notes = ?, updated_at = ?
                WHERE id = ?
                """,
                [
                    updated.status,
                    updated.ats_score,
                    updated.job_url,
                    updated.pdf_filename,
                    updated.notes,
                    now,
                    app_id,
                ],
            )
        return updated

    def delete_application(self, app_id: str) -> bool:
        with self._connect() as con:
            existing = con.execute(
                "SELECT 1 FROM job_applications WHERE id = ?", [app_id]
            ).fetchone()
            if not existing:
                return False
            con.execute("DELETE FROM job_applications WHERE id = ?", [app_id])
        return True
