import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from cv_agent.config import settings


@dataclass(frozen=True)
class ExtractedSkill:
    canonical: str
    category: str


class SkillTaxonomyExtractor:
    """Fast Stage-1 deterministic skill extractor backed by config/skills_taxonomy.yaml."""

    def __init__(self, taxonomy_path: Path | None = None) -> None:
        path = taxonomy_path or settings.skills_taxonomy_path
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        self._patterns: list[tuple[str, str, re.Pattern[str]]] = []
        for canonical, meta in (raw.get("skills") or {}).items():
            category = meta.get("category", "general")
            aliases = meta.get("aliases", [canonical])
            escaped = [re.escape(a.strip()) for a in aliases if a.strip()]
            if not escaped:
                continue
            regex = re.compile(r"(?i)(?<![A-Za-z0-9_])(" + "|".join(escaped) + r")(?![A-Za-z0-9_])")
            self._patterns.append((canonical, category, regex))

    def extract(self, text: str) -> list[ExtractedSkill]:
        if not text:
            return []
        found: list[ExtractedSkill] = []
        for canonical, category, pattern in self._patterns:
            if pattern.search(text):
                found.append(ExtractedSkill(canonical=canonical, category=category))
        return found

    def normalize(self, skill_name: str) -> str:
        matches = self.extract(skill_name)
        return matches[0].canonical if matches else skill_name.strip()
