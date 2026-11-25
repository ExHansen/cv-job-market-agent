from pathlib import Path

from cv_agent.storage.applications_db import (
    ApplicationCreate,
    ApplicationsDatabase,
    ApplicationUpdate,
)


def test_applications_crud_lifecycle(tmp_path: Path) -> None:
    db = ApplicationsDatabase(db_path=tmp_path / "apps.duckdb")

    created = db.create_application(
        ApplicationCreate(
            company="FIT HUB",
            role="Data Engineer",
            status="wishlist",
            ats_score=83.8,
            job_url="https://www.linkedin.com/jobs/view/4491875867/",
            pdf_filename="CV_Alex_Pratama_FIT_HUB_Data_Engineer.pdf",
            notes="Strong match on SQL, dbt, Data Quality.",
        )
    )
    assert created.company == "FIT HUB"
    assert created.status == "wishlist"

    listed = db.list_applications()
    assert len(listed) == 1
    assert listed[0].id == created.id

    updated = db.update_application(
        created.id,
        ApplicationUpdate(status="interview", notes="Passed HR screening!"),
    )
    assert updated is not None
    assert updated.status == "interview"
    assert updated.notes == "Passed HR screening!"

    assert db.delete_application(created.id) is True
    assert db.list_applications() == []
