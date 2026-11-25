import re
from pathlib import Path

import yaml

from cv_agent.config import settings
from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.schemas import (
    FactCheckResult,
    FactCheckViolation,
    MarketSnapshot,
    MasterProfile,
    TailoredCV,
)

NUMBER_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|x|k|m|b|tb|gb|mb|ms|hrs?|hours?|mins?|minutes?)?\b",
    re.IGNORECASE,
)


def _load_ats_rules(rules_path: Path | None = None) -> dict:
    path = rules_path or settings.ats_rules_path
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _extract_numeric_tokens(text: str) -> set[str]:
    return {m.group(0).strip().lower() for m in NUMBER_PATTERN.finditer(text or "")}


def run_deterministic_fact_check(
    master_profile: MasterProfile,
    tailored_cv: TailoredCV,
    market_snapshot: MarketSnapshot,
    taxonomy_path: Path | None = None,
    rules_path: Path | None = None,
) -> FactCheckResult:
    """
    Deterministic anti-hallucination & ATS guardrail.
    Ensures every skill, source_id, and numeric metric in TailoredCV is grounded in MasterProfile.
    """
    extractor = SkillTaxonomyExtractor(taxonomy_path=taxonomy_path)
    rules = _load_ats_rules(rules_path=rules_path)
    bullet_rules = rules.get("bullet_rules", {})
    max_words = int(bullet_rules.get("max_words", 35))
    min_words = int(bullet_rules.get("min_words", 8))
    forbidden_fluff = [p.lower() for p in rules.get("forbidden_fluff_phrases", [])]

    verified_skills_norm = {extractor.normalize(s) for s in master_profile.all_verified_skills()}
    valid_bullet_ids = master_profile.all_bullet_ids()

    # Collect all verified numbers present anywhere in the MasterProfile
    verified_numbers: set[str] = set()
    for exp in master_profile.experiences:
        for b in exp.bullets:
            verified_numbers.update(_extract_numeric_tokens(b.raw_fact))
            for metric in b.metrics:
                verified_numbers.update(_extract_numeric_tokens(metric))
    for proj in master_profile.projects:
        for b in proj.bullets:
            verified_numbers.update(_extract_numeric_tokens(b.raw_fact))
            for metric in b.metrics:
                verified_numbers.update(_extract_numeric_tokens(metric))
    if master_profile.profile.years_of_experience:
        verified_numbers.add(str(int(master_profile.profile.years_of_experience)))
        verified_numbers.add(str(master_profile.profile.years_of_experience))

    violations: list[FactCheckViolation] = []

    # 0. Completeness checks (prevent local LLM from returning empty sections)
    if not tailored_cv.grouped_skills:
        violations.append(
            FactCheckViolation(
                severity="error",
                rule="empty_skills",
                detail="TailoredCV grouped_skills is empty.",
            )
        )
    if not tailored_cv.experiences and master_profile.experiences:
        violations.append(
            FactCheckViolation(
                severity="error",
                rule="empty_experiences",
                detail="TailoredCV experiences is empty despite MasterProfile having experiences.",
            )
        )

    # 1. Check skills listed in TailoredCV against verified skills
    for group_name, skills in tailored_cv.grouped_skills.items():
        for skill in skills:
            norm = extractor.normalize(skill)
            if norm not in verified_skills_norm:
                violations.append(
                    FactCheckViolation(
                        severity="error",
                        rule="unverified_skill",
                        detail=(
                            f"Skill '{skill}' in group '{group_name}' "
                            "does not exist in MasterProfile."
                        ),
                    )
                )

    # 2. Check bullets for valid source_id, hallucinated tools/numbers, fluff, and length
    total_bullets = 0
    quantified_bullets = 0
    all_tailored_text_parts = [tailored_cv.professional_summary]

    for exp in tailored_cv.experiences:
        for bullet in exp.bullets:
            total_bullets += 1
            all_tailored_text_parts.append(bullet.rewritten_text)

            if bullet.source_id not in valid_bullet_ids:
                violations.append(
                    FactCheckViolation(
                        severity="error",
                        rule="invalid_source_id",
                        detail=f"Bullet source_id '{bullet.source_id}' not found in MasterProfile.",
                    )
                )

            # Check canonical tools mentioned in bullet text
            for extracted in extractor.extract(bullet.rewritten_text):
                if extracted.canonical not in verified_skills_norm:
                    violations.append(
                        FactCheckViolation(
                            severity="error",
                            rule="hallucinated_tool_in_bullet",
                            detail=(
                                f"Bullet '{bullet.source_id}' mentions unverified tool "
                                f"'{extracted.canonical}'."
                            ),
                        )
                    )

            # Check numeric claims are grounded
            bullet_nums = _extract_numeric_tokens(bullet.rewritten_text)
            if bullet_nums:
                quantified_bullets += 1
            ungrounded_nums = bullet_nums - verified_numbers
            for num in sorted(ungrounded_nums):
                violations.append(
                    FactCheckViolation(
                        severity="error",
                        rule="ungrounded_metric",
                        detail=(
                            f"Bullet '{bullet.source_id}' contains numeric claim '{num}' "
                            "not present in MasterProfile."
                        ),
                    )
                )

            # ATS word count & fluff checks
            words = bullet.rewritten_text.split()
            if len(words) > max_words:
                violations.append(
                    FactCheckViolation(
                        severity="warning",
                        rule="bullet_too_long",
                        detail=(
                            f"Bullet '{bullet.source_id}' has {len(words)} words "
                            f"(max {max_words})."
                        ),
                    )
                )
            elif len(words) < min_words:
                violations.append(
                    FactCheckViolation(
                        severity="warning",
                        rule="bullet_too_short",
                        detail=(
                            f"Bullet '{bullet.source_id}' has {len(words)} words "
                            f"(min {min_words})."
                        ),
                    )
                )

            lowered = bullet.rewritten_text.lower()
            for fluff in forbidden_fluff:
                if fluff in lowered:
                    violations.append(
                        FactCheckViolation(
                            severity="warning",
                            rule="forbidden_fluff",
                            detail=f"Bullet '{bullet.source_id}' uses weak phrase '{fluff}'.",
                        )
                    )

    # 3. Compute ATS coverage score against market snapshot
    combined_text = "\n".join(all_tailored_text_parts)
    mentioned_skills = {s.canonical for s in extractor.extract(combined_text)}
    mentioned_skills.update(
        extractor.normalize(s) for grp in tailored_cv.grouped_skills.values() for s in grp
    )

    mandatory_skills = [s.skill for s in market_snapshot.top_mandatory_skills]
    rising_skills = [s.skill for s in market_snapshot.rising_skills]

    mandatory_cov = (
        len([s for s in mandatory_skills if s in mentioned_skills]) / len(mandatory_skills)
        if mandatory_skills
        else 1.0
    )
    rising_cov = (
        len([s for s in rising_skills if s in mentioned_skills]) / len(rising_skills)
        if rising_skills
        else 1.0
    )
    quant_ratio = quantified_bullets / total_bullets if total_bullets else 0.0
    format_score = 1.0 if not any(v.severity == "warning" for v in violations) else 0.7

    weights = rules.get("scoring_weights", {})
    ats_score = round(
        100.0
        * (
            mandatory_cov * float(weights.get("mandatory_skill_coverage", 0.5))
            + rising_cov * float(weights.get("rising_skill_coverage", 0.2))
            + quant_ratio * float(weights.get("quantified_impact_ratio", 0.2))
            + format_score * float(weights.get("ats_format_compliance", 0.1))
        ),
        1,
    )

    has_errors = any(v.severity == "error" for v in violations)
    return FactCheckResult(passed=not has_errors, ats_score=ats_score, violations=violations)
