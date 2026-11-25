import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from cv_agent.config import settings
from cv_agent.schemas import MasterProfile, TailoredCV


def _resolve_rendercv_bin() -> str:
    """Locate rendercv inside the active virtualenv first, then system PATH."""
    scripts_dir = Path(sys.executable).parent
    for name in ("rendercv.exe", "rendercv"):
        candidate = scripts_dir / name
        if candidate.exists():
            return str(candidate)
    return shutil.which("rendercv") or "rendercv"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text.strip()).strip("_")
    return slug or "CV"


def build_rendercv_dict(
    master_profile: MasterProfile,
    tailored_cv: TailoredCV,
    theme: str = "engineeringresumes",
) -> dict[str, Any]:
    """Convert validated MasterProfile + TailoredCV into RenderCV v2 YAML schema."""
    header = master_profile.profile

    social_networks: list[dict[str, str]] = []
    if header.links.github:
        social_networks.append(
            {"network": "GitHub", "username": header.links.github.rstrip("/").split("/")[-1]}
        )
    if header.links.linkedin:
        social_networks.append(
            {"network": "LinkedIn", "username": header.links.linkedin.rstrip("/").split("/")[-1]}
        )

    experience_items = [
        {
            "company": exp.company,
            "position": exp.role,
            "location": exp.location,
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "highlights": [b.rewritten_text for b in exp.bullets],
        }
        for exp in tailored_cv.experiences
    ]

    project_items = [
        {
            "name": proj.name,
            "date": proj.period,
            "highlights": [b.raw_fact for b in proj.bullets],
        }
        for proj in tailored_cv.projects[:3]
    ]

    education_items = [
        {
            "institution": edu.institution,
            "area": edu.degree,
            "degree": "A.Md." if "a.md" in edu.degree.lower() else "BS",
            "start_date": edu.start_date,
            "end_date": edu.end_date,
            "highlights": [f"GPA: {edu.gpa}"] if edu.gpa else [],
        }
        for edu in master_profile.education
    ]

    skills_items = [
        {"label": group.replace("_", " ").title(), "details": ", ".join(items)}
        for group, items in tailored_cv.grouped_skills.items()
        if items
    ]

    sections: dict[str, Any] = {
        "summary": [tailored_cv.professional_summary],
        "skills": skills_items,
        "experience": experience_items,
        "projects": project_items,
        "education": education_items,
    }

    if master_profile.certifications:
        sections["certifications"] = [
            {"label": cert.name, "details": f"{cert.issuer} ({cert.date})"}
            for cert in master_profile.certifications
        ]

    if master_profile.honors:
        sections["honors"] = [
            {
                "label": honor.title,
                "details": f"{honor.issuer} ({honor.date}) — {honor.summary}".strip(" —"),
            }
            for honor in master_profile.honors
        ]

    cv_block: dict[str, Any] = {
        "name": header.full_name,
        "location": header.location,
        "email": header.email,
        "social_networks": social_networks,
        "sections": sections,
    }
    if header.phone:
        cv_block["phone"] = header.phone
    if header.links.website:
        cv_block["website"] = header.links.website

    return {
        "cv": cv_block,
        "design": {
            "theme": theme,
            "page": {"size": "a4"},
        },
    }


def export_and_render_pdf(
    master_profile: MasterProfile,
    tailored_cv: TailoredCV,
    output_stem: str = "",
    theme: str = "engineeringresumes",
) -> dict[str, str]:
    """Write RenderCV YAML and compile to ATS-friendly PDF if rendercv CLI is installed."""
    out_dir = settings.outputs_dir
    if not output_stem:
        name_slug = _slugify(master_profile.profile.full_name)
        company_slug = _slugify(tailored_cv.target_company) if tailored_cv.target_company else ""
        role_slug = _slugify(tailored_cv.target_role)
        parts = [p for p in ("CV", name_slug, company_slug, role_slug) if p]
        output_stem = "_".join(parts)

    yaml_path = out_dir / f"{output_stem}.yaml"
    payload = build_rendercv_dict(master_profile, tailored_cv, theme=theme)

    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    render_out_dir = out_dir / "rendercv_out"
    render_out_dir.mkdir(parents=True, exist_ok=True)
    rendercv_bin = _resolve_rendercv_bin()
    pdf_target = render_out_dir / f"{output_stem}.pdf"
    result = subprocess.run(
        [
            rendercv_bin,
            "render",
            str(yaml_path),
            "--output-folder",
            "rendercv_out",
            "--pdf-path",
            f"rendercv_out/{output_stem}.pdf",
            "--dont-generate-markdown",
            "--dont-generate-html",
            "--dont-generate-png",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    pdf_path = str(pdf_target) if pdf_target.exists() else ""

    return {
        "filename": f"{output_stem}.pdf",
        "yaml_path": str(yaml_path),
        "pdf_path": pdf_path,
        "render_ok": str(result.returncode == 0),
        "stderr": (result.stderr or result.stdout).strip(),
    }
