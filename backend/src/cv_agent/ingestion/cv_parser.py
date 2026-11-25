import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf4llm
import yaml

from cv_agent.schemas import MasterProfile

DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF resume to layout-aware Markdown using PyMuPDF4LLM."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"CV file not found: {pdf_path}")
    return str(pymupdf4llm.to_markdown(str(pdf_path)))


def extract_docx_to_markdown(docx_path: Path) -> str:
    """Extract clean plain text / markdown from a DOCX resume without external dependencies."""
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")
    with zipfile.ZipFile(docx_path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    lines: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("}p"):
            text = "".join(t.text or "" for t in elem.findall(".//w:t", DOCX_NS)).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def extract_cv_file(cv_path: Path) -> str:
    """Dispatch PDF or DOCX resume extraction."""
    suffix = cv_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_to_markdown(cv_path)
    if suffix == ".docx":
        return extract_docx_to_markdown(cv_path)
    raise ValueError(f"Unsupported CV format '{suffix}'. Use .pdf or .docx.")


def load_master_profile(yaml_path: Path) -> MasterProfile:
    """Load and validate the user's Single Source of Truth profile from YAML."""
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return MasterProfile.model_validate(data)


def save_master_profile(profile: MasterProfile, yaml_path: Path) -> None:
    """Persist validated MasterProfile back to YAML."""
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(profile.model_dump(mode="json"), f, sort_keys=False, allow_unicode=True)
