import html
import json
import re
from urllib.parse import parse_qs, quote, urlparse

import httpx

from cv_agent.ingestion.skill_extractor import SkillTaxonomyExtractor
from cv_agent.schemas import CompanyIntel
from cv_agent.storage.market_db import MarketDatabase

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
WHITESPACE_RE = re.compile(r"\s+")
LINKEDIN_VIEW_ID_RE = re.compile(r"/jobs/view/(?:[^/?#]*-)?(\d+)")
LD_JSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
LINKEDIN_JD_RE = re.compile(
    r'class=["\'][^"\']*show-more-less-html__markup[^"\']*["\'][^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)

INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "Fintech / Banking / Lending": [
        "bank",
        "fintech",
        "payment",
        "lending",
        "paylater",
        "credit",
        "financial",
        "wallet",
        "insurance",
        "ojk",
    ],
    "E-Commerce / Marketplace": [
        "e-commerce",
        "ecommerce",
        "marketplace",
        "retail",
        "shopping",
        "merchant",
        "store",
    ],
    "Health / Fitness / Wellness": [
        "health",
        "wellness",
        "fitness",
        "gym",
        "healthcare",
        "clinic",
        "medical",
    ],
    "FMCG / Supply Chain": ["fmcg", "consumer goods", "supply chain", "logistics", "distribution"],
    "Travel / Mobility / Superapp": [
        "ride-hailing",
        "travel",
        "airline",
        "hotel",
        "mobility",
        "delivery",
        "superapp",
    ],
    "AI / Cloud / Data SaaS": [
        "artificial intelligence",
        "machine learning",
        "cloud",
        "database",
        "analytics",
        "saas",
        "software",
    ],
}


def strip_html(raw_html: str) -> str:
    """Clean HTML markup into readable plain text."""
    cleaned = SCRIPT_STYLE_RE.sub(" ", raw_html or "")
    cleaned = TAG_RE.sub(" ", cleaned)
    cleaned = html.unescape(cleaned)
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def infer_industry(text: str) -> str:
    lowered = (text or "").lower()
    best_industry = "Technology"
    best_hits = 0
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best_hits = hits
            best_industry = industry
    return best_industry


def normalize_job_url(job_url: str) -> tuple[str, str]:
    """
    Normalize job board search URLs (e.g. LinkedIn /jobs/search-results/?currentJobId=...)
    into canonical public job posting URLs, plus return any URL role hint.
    """
    raw = (job_url or "").strip()
    if not raw:
        return "", ""

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    qs = parse_qs(parsed.query)
    role_hint = (qs.get("keywords") or [""])[0].strip()

    if "linkedin.com" in host:
        job_id = (qs.get("currentJobId") or [""])[0].strip()
        if not job_id:
            match = LINKEDIN_VIEW_ID_RE.search(parsed.path)
            if match:
                job_id = match.group(1)
        if job_id and job_id.isdigit():
            return f"https://www.linkedin.com/jobs/view/{job_id}/", role_hint

    return raw, role_hint


def _parse_linkedin_title(title_text: str) -> tuple[str, str]:
    """Parse LinkedIn public <title> into (job_title, company_name)."""
    clean = re.sub(r"\s*\|\s*LinkedIn.*$", "", title_text or "", flags=re.IGNORECASE).strip()
    # Pattern A: "Data Engineer at FIT HUB — Jakarta, Indonesia"
    match_at = re.match(r"^(.+?)\s+at\s+(.+?)(?:\s+[—–-]\s+.*)?$", clean, re.IGNORECASE)
    if match_at:
        return match_at.group(1).strip(), match_at.group(2).strip()
    # Pattern B: "FIT HUB hiring Data Engineer in Jakarta, Indonesia"
    match_hiring = re.match(r"^(.+?)\s+hiring\s+(.+?)(?:\s+in\s+.*)?$", clean, re.IGNORECASE)
    if match_hiring:
        return match_hiring.group(2).strip(), match_hiring.group(1).strip()
    return clean, ""


def _extract_jsonld_job(raw_html: str) -> tuple[str, str, str]:
    """Extract (job_title, company_name, jd_text) from standard schema.org JobPosting JSON-LD."""
    for block in LD_JSON_RE.findall(raw_html or ""):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            is_job = item_type == "JobPosting" or (
                isinstance(item_type, list) and "JobPosting" in item_type
            )
            if not is_job:
                continue
            title = str(item.get("title") or "").strip()
            org = item.get("hiringOrganization")
            company = str(org.get("name") or "").strip() if isinstance(org, dict) else ""
            desc = strip_html(str(item.get("description") or ""))
            if desc:
                return title, company, desc[:6000]
    return "", "", ""


def _extract_linkedin_guest_job(raw_html: str) -> tuple[str, str, str]:
    """Extract (job_title, company_name, jd_text) from LinkedIn public guest job page HTML."""
    title_match = TITLE_TAG_RE.search(raw_html or "")
    raw_title = html.unescape(title_match.group(1).strip()) if title_match else ""
    job_title, company_name = _parse_linkedin_title(raw_title)

    jd_match = LINKEDIN_JD_RE.search(raw_html or "")
    jd_text = strip_html(jd_match.group(1))[:6000] if jd_match else ""
    return job_title, company_name, jd_text


def _fetch_direct_job_page(job_url: str) -> tuple[str, str, str, str]:
    """
    Fetch a public job posting URL and return (canonical_url, job_title, company_name, jd_text).
    Respects auth walls cleanly without bypassing authentication or anti-bot gates.
    """
    canonical_url, _ = normalize_job_url(job_url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; cv-job-market-agent/0.2)"}
    try:
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(canonical_url)
            if resp.status_code in (429, 502, 503):
                resp = client.get(canonical_url)
            final_url = str(resp.url)
            if resp.status_code != 200 or "authwall" in final_url.lower():
                return canonical_url, "", "", ""

            # 1. Try standard schema.org JobPosting JSON-LD (works across many boards)
            title, company, desc = _extract_jsonld_job(resp.text)
            if desc:
                return canonical_url, title, company, desc

            # 2. Try LinkedIn public guest details markup
            if "linkedin.com" in final_url.lower():
                title, company, desc = _extract_linkedin_guest_job(resp.text)
                if desc:
                    return canonical_url, title, company, desc

            # 3. Generic public page fallback
            return canonical_url, "", "", strip_html(resp.text)[:6000]
    except Exception:
        return canonical_url, "", "", ""


def _company_slugs(company_name: str) -> list[str]:
    clean = re.sub(r"[^a-z0-9\s-]", "", company_name.lower()).strip()
    tokens = clean.split()
    if not tokens:
        return []
    candidates = ["".join(tokens), "-".join(tokens), tokens[0]]
    return list(dict.fromkeys(c for c in candidates if len(c) >= 2))


def _title_matches_company(company_name: str, candidate_title: str) -> bool:
    """Reject unrelated fuzzy Wikipedia matches (e.g. 'Bank Jago' -> 'Bank Hapoalim')."""
    company_tokens = [t for t in re.findall(r"[a-z0-9]+", company_name.lower()) if len(t) >= 3]
    title_lower = candidate_title.lower()
    if not company_tokens:
        return False
    generic = {"bank", "pt", "tbk", "inc", "ltd", "corp", "group", "indonesia", "tech"}
    distinctive = [t for t in company_tokens if t not in generic] or company_tokens
    return all(tok in title_lower for tok in distinctive)


def _lookup_company_summary(company_name: str) -> tuple[str, str]:
    """Fetch public company summary via English & Indonesian Wikipedia + DuckDuckGo (no key)."""
    headers = {"User-Agent": "cv-job-market-agent/0.2 (portfolio-research)"}
    with httpx.Client(timeout=8.0, headers=headers, follow_redirects=True) as client:
        for lang in ("en", "id"):
            try:
                search_url = (
                    f"https://{lang}.wikipedia.org/w/api.php?action=opensearch"
                    "&limit=3&format=json&search=" + quote(company_name)
                )
                s_resp = client.get(search_url)
                if s_resp.status_code == 200:
                    payload = s_resp.json()
                    titles = payload[1] if len(payload) > 1 else []
                    matched_title = next(
                        (t for t in titles if _title_matches_company(company_name, t)),
                        None,
                    )
                    if matched_title:
                        sum_url = (
                            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                            + quote(matched_title.replace(" ", "_"))
                        )
                        r_sum = client.get(sum_url)
                        if r_sum.status_code == 200:
                            data = r_sum.json()
                            extract = str(data.get("extract") or "").strip()
                            page_url = str(
                                (data.get("content_urls") or {}).get("desktop", {}).get("page")
                                or ""
                            )
                            if extract:
                                return extract[:900], page_url
            except Exception:
                pass

        try:
            ddg_url = f"https://api.duckduckgo.com/?q={quote(company_name)}&format=json&no_html=1"
            d_resp = client.get(ddg_url)
            if d_resp.status_code == 200:
                data = d_resp.json()
                abstract = str(data.get("AbstractText") or "").strip()
                src_url = str(data.get("AbstractURL") or "").strip()
                if abstract:
                    return abstract[:900], src_url
        except Exception:
            pass

    return "", ""


def _probe_public_ats_boards(
    company_name: str,
    target_role: str,
) -> tuple[str, str, str]:
    """Probe Greenhouse & Lever public ATS APIs for matching open role at target company."""
    role_tokens = [t for t in target_role.lower().split() if len(t) > 2]
    slugs = _company_slugs(company_name)
    headers = {"User-Agent": "cv-job-market-agent/0.2"}

    with httpx.Client(timeout=6.0, headers=headers) as client:
        for slug in slugs:
            try:
                gh_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
                resp = client.get(gh_url)
                if resp.status_code == 200:
                    jobs = resp.json().get("jobs", [])
                    best = _pick_best_matching_job(jobs, role_tokens, title_key="title")
                    if best:
                        return (
                            str(best.get("title") or target_role),
                            str(best.get("absolute_url") or ""),
                            strip_html(str(best.get("content") or ""))[:5000],
                        )
            except Exception:
                pass

            try:
                lv_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
                resp = client.get(lv_url)
                if resp.status_code == 200 and isinstance(resp.json(), list):
                    jobs = resp.json()
                    best = _pick_best_matching_job(jobs, role_tokens, title_key="text")
                    if best:
                        desc = str(best.get("descriptionPlain") or "")
                        lists_text = " ".join(
                            str(item.get("content") or "") for item in best.get("lists", [])
                        )
                        return (
                            str(best.get("text") or target_role),
                            str(best.get("hostedUrl") or ""),
                            strip_html(f"{desc} {lists_text}")[:5000],
                        )
            except Exception:
                pass

    return "", "", ""


def _pick_best_matching_job(
    jobs: list[dict],
    role_tokens: list[str],
    title_key: str,
) -> dict | None:
    best_job: dict | None = None
    best_score = 0
    for job in jobs:
        title = str(job.get(title_key) or "").lower()
        score = sum(1 for tok in role_tokens if tok in title)
        if score > best_score:
            best_score = score
            best_job = job
    return best_job if best_score > 0 else None


def research_company_and_jd(
    company_name: str,
    target_role: str,
    job_url: str = "",
    pasted_jd: str = "",
    allow_web: bool = True,
    db: MarketDatabase | None = None,
) -> CompanyIntel:
    """
    Research a target company's business profile & find the most relevant Job Description
    using a tiered strategy: pasted JD -> direct/LinkedIn URL -> public ATS -> DuckDB cache.
    """
    company_clean = company_name.strip()
    canonical_url, _ = normalize_job_url(job_url)
    if not company_clean and not pasted_jd and not canonical_url:
        return CompanyIntel()

    jd_text = ""
    jd_source = "none"
    job_title_found = ""
    job_url_found = canonical_url

    if pasted_jd.strip():
        jd_text = pasted_jd.strip()
        jd_source = "user_pasted"
    elif canonical_url and allow_web:
        canon, parsed_title, parsed_company, fetched = _fetch_direct_job_page(canonical_url)
        job_url_found = canon
        if parsed_title:
            job_title_found = parsed_title
        if parsed_company and not company_clean:
            company_clean = parsed_company
        if fetched:
            jd_text = fetched
            jd_source = "direct_url"
    elif company_clean and allow_web:
        title, url, content = _probe_public_ats_boards(company_clean, target_role)
        if content:
            job_title_found = title
            job_url_found = url
            jd_text = content
            jd_source = "ats_board"

    if not jd_text and company_clean and db is not None:
        cached = db.find_company_job(company_name=company_clean, role=target_role)
        if cached:
            job_title_found, job_url_found, jd_text = cached
            jd_source = "duckdb_cache"

    summary, src_url = ("", "")
    if company_clean and allow_web:
        summary, src_url = _lookup_company_summary(company_clean)
    if not summary and jd_text:
        summary = jd_text[:450]
        src_url = src_url or job_url_found

    extractor = SkillTaxonomyExtractor()
    combined = f"{company_clean}\n{summary}\n{jd_text}"
    detected_stack = [s.canonical for s in extractor.extract(combined)]
    industry = infer_industry(combined)

    return CompanyIntel(
        company_name=company_clean,
        industry=industry,
        company_summary=summary,
        source_url=src_url,
        detected_tech_stack=detected_stack,
        job_title_found=job_title_found,
        job_url_found=job_url_found,
        jd_text=jd_text,
        jd_source=jd_source,  # type: ignore[arg-type]
    )
