export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SkillFrequency {
  skill: string;
  category: string;
  job_count: number;
  frequency_pct: number;
}

export interface CompanyIntel {
  company_name: string;
  industry: string;
  company_summary: string;
  source_url: string;
  detected_tech_stack: string[];
  job_title_found: string;
  job_url_found: string;
  jd_text: string;
  jd_source: "none" | "user_pasted" | "direct_url" | "ats_board" | "duckdb_cache";
}

export interface MarketSnapshot {
  role: string;
  region: string;
  snapshot_date: string;
  sample_size: number;
  top_mandatory_skills: SkillFrequency[];
  rising_skills: SkillFrequency[];
  source_breakdown: Record<string, number>;
}

export interface GapAuditReport {
  target_role: string;
  ats_score: number;
  matched_skills: string[];
  hidden_quick_wins: string[];
  true_skill_gaps: string[];
  weak_bullet_ids: string[];
  interview_questions: string[];
  upskilling_recommendations: string[];
}

export interface TailoredBullet {
  source_id: string;
  original_text: string;
  rewritten_text: string;
  tools_referenced: string[];
}

export interface TailoredExperience {
  id: string;
  company: string;
  role: string;
  location: string;
  start_date: string;
  end_date: string;
  bullets: TailoredBullet[];
}

export interface FactBullet {
  id: string;
  raw_fact: string;
  metrics: string[];
  tools_used: string[];
  verified: boolean;
}

export interface ProjectEntry {
  id: string;
  name: string;
  period: string;
  url: string;
  domain_tags: string[];
  bullets: FactBullet[];
}

export interface MasterProfile {
  profile: {
    full_name: string;
    headline: string;
    target_roles: string[];
    location: string;
    email: string;
    phone: string;
    links: { github: string; linkedin: string; website: string };
    years_of_experience: number;
  };
  skills_verified: Record<string, string[]>;
  experiences: Array<{
    id: string;
    company: string;
    role: string;
    location: string;
    start_date: string;
    end_date: string;
    bullets: FactBullet[];
  }>;
  projects: ProjectEntry[];
  education: Array<{
    institution: string;
    degree: string;
    start_date: string;
    end_date: string;
    gpa: string;
  }>;
  certifications: Array<{ name: string; issuer: string; date: string }>;
  honors: Array<{ title: string; issuer: string; date: string; summary: string }>;
  languages: string[];
}

export interface TailoredCV {
  target_role: string;
  target_company: string;
  output_language: "en" | "id";
  professional_summary: string;
  grouped_skills: Record<string, string[]>;
  experiences: TailoredExperience[];
  projects: ProjectEntry[];
}

export interface FactCheckViolation {
  severity: "error" | "warning";
  rule: string;
  detail: string;
}

export interface FactCheckResult {
  passed: boolean;
  ats_score: number;
  violations: FactCheckViolation[];
}

export interface TailorResponse {
  company_intel: CompanyIntel;
  market_snapshot: MarketSnapshot;
  gap_audit: GapAuditReport;
  tailored_cv: TailoredCV;
  fact_check: FactCheckResult;
  events: string[];
}

export interface TailorPayload {
  target_role: string;
  target_company: string;
  job_url: string;
  region: string;
  target_jd_text: string;
  output_language: "en" | "id";
  use_llm: boolean;
}

export interface CompanyDeepDiveReport {
  company_name: string;
  target_role: string;
  industry: string;
  business_model: string;
  company_overview: string;
  strengths: string[];
  weaknesses_and_challenges: string[];
  inferred_team_needs: string[];
  how_candidate_fits: string[];
  smart_interview_questions: string[];
  detected_tech_stack: string[];
  job_title_found: string;
  job_url_found: string;
  jd_source: string;
  sources: string[];
  used_llm: boolean;
}

export interface DeepDiveProgressEvent {
  type: "progress" | "heartbeat" | "done" | "error";
  stage?: string;
  percent?: number;
  message?: string;
  elapsed_sec?: number;
  report?: CompanyDeepDiveReport;
}

export async function streamCompanyDeepDive(
  payload: {
    company_name: string;
    target_role: string;
    job_url: string;
    pasted_jd: string;
    language: "id" | "en";
    use_llm: boolean;
  },
  onEvent: (event: DeepDiveProgressEvent) => void,
  signal?: AbortSignal
): Promise<CompanyDeepDiveReport> {
  const res = await fetch(`${API_URL}/api/company/deep-dive/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok || !res.body) {
    const errText = await res.text();
    throw new Error(errText || `Company deep-dive stream failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalReport: CompanyDeepDiveReport | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const trimmed = chunk.trim();
      if (!trimmed.startsWith("data:")) continue;
      const parsed = JSON.parse(trimmed.slice(5).trim()) as DeepDiveProgressEvent;
      onEvent(parsed);
      if (parsed.type === "error") {
        throw new Error(parsed.message || "Analysis error");
      }
      if (parsed.type === "done" && parsed.report) {
        finalReport = parsed.report;
      }
    }
  }

  if (!finalReport) {
    throw new Error("Stream ended without final report");
  }
  return finalReport;
}

export async function fetchCompanyDeepDive(payload: {
  company_name: string;
  target_role: string;
  job_url: string;
  pasted_jd: string;
  language: "id" | "en";
  use_llm: boolean;
}): Promise<CompanyDeepDiveReport> {
  const res = await fetch(`${API_URL}/api/company/deep-dive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(errText || `Company deep-dive failed (${res.status})`);
  }
  return res.json();
}

export async function fetchHealth(): Promise<{
  status: string;
  llm_provider: string;
  model: string;
}> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}

export async function fetchDefaultProfile(): Promise<MasterProfile> {
  const res = await fetch(`${API_URL}/api/profile/default`);
  if (!res.ok) throw new Error(`Failed to load master profile (${res.status})`);
  return res.json();
}

export async function fetchMarketTrends(
  role = "Data Engineer",
  region = "Indonesia"
): Promise<MarketSnapshot> {
  const params = new URLSearchParams({ role, region });
  const res = await fetch(`${API_URL}/api/market/trends?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch market trends (${res.status})`);
  return res.json();
}

export async function refreshMarketTrends(payload: {
  role: string;
  location: string;
  results_wanted?: number;
  greenhouse_boards?: string[];
}): Promise<{ status: string; role: string; jobs_ingested: number }> {
  const res = await fetch(`${API_URL}/api/market/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Refresh failed (${res.status})`);
  }
  return res.json();
}

export async function parseUploadedCv(file: File): Promise<{
  filename: string;
  markdown: string;
}> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/api/cv/parse-file`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload parse failed (${res.status})`);
  return res.json();
}

export async function streamTailorCV(
  payload: TailorPayload,
  onStep: (node: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal
): Promise<TailorResponse> {
  const res = await fetch(`${API_URL}/api/cv/tailor/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalData: TailorResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const chunk of lines) {
      const trimmed = chunk.trim();
      if (!trimmed.startsWith("data:")) continue;
      const parsed = JSON.parse(trimmed.slice(5).trim());
      onStep(parsed.node, parsed.data);
      if (parsed.node === "done") {
        finalData = parsed.data as TailorResponse;
      }
    }
  }

  if (!finalData) {
    throw new Error("Stream ended without final payload");
  }
  return finalData;
}

export async function renderCvPdf(
  payload: TailorPayload
): Promise<{
  filename: string;
  download_url?: string;
  render_ok: string;
  stderr: string;
}> {
  const res = await fetch(`${API_URL}/api/cv/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Render request failed (${res.status})`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Application Tracker (DuckDB CRUD)
// ---------------------------------------------------------------------------

export type ApplicationStatus =
  | "wishlist"
  | "applied"
  | "interview"
  | "offer"
  | "rejected";

export interface JobApplication {
  id: string;
  company: string;
  role: string;
  status: ApplicationStatus;
  ats_score: number | null;
  job_url: string;
  pdf_filename: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export async function listApplications(): Promise<JobApplication[]> {
  const res = await fetch(`${API_URL}/api/applications`);
  if (!res.ok) throw new Error(`Failed to fetch applications (${res.status})`);
  return res.json();
}

export async function createApplication(payload: {
  company: string;
  role: string;
  status?: ApplicationStatus;
  ats_score?: number | null;
  job_url?: string;
  pdf_filename?: string;
  notes?: string;
}): Promise<JobApplication> {
  const res = await fetch(`${API_URL}/api/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to save application (${res.status})`);
  return res.json();
}

export async function updateApplication(
  appId: string,
  patch: Partial<{
    status: ApplicationStatus;
    ats_score: number | null;
    job_url: string;
    pdf_filename: string;
    notes: string;
  }>
): Promise<JobApplication> {
  const res = await fetch(`${API_URL}/api/applications/${appId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`Failed to update application (${res.status})`);
  return res.json();
}

export async function deleteApplication(appId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/applications/${appId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete application (${res.status})`);
}

// ---------------------------------------------------------------------------
// Interview Prep Chat (Local Ollama Streaming SSE)
// ---------------------------------------------------------------------------

export type InterviewMode = "technical" | "behavioral" | "system_design" | "hr";

export interface InterviewTurn {
  role: "user" | "assistant";
  content: string;
}

export async function streamInterviewChat(
  payload: {
    company_name: string;
    target_role: string;
    mode: InterviewMode;
    language: "id" | "en";
    messages: InterviewTurn[];
  },
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_URL}/api/interview/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Interview chat stream failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const trimmed = chunk.trim();
      if (!trimmed.startsWith("data:")) continue;
      const parsed = JSON.parse(trimmed.slice(5).trim()) as {
        type: "token" | "done" | "error";
        content?: string;
        message?: string;
      };
      if (parsed.type === "error") {
        throw new Error(parsed.message || "Interview AI error");
      }
      if (parsed.type === "token" && parsed.content) {
        onToken(parsed.content);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Company Knowledge Base (DuckDB: Positives, Keluh Kesah, IDR Salaries)
// ---------------------------------------------------------------------------

export type CompanyVerdict = "Recommended" | "Mixed - Selective" | "Caution";

export interface CompanyKnowledgeRecord {
  company_name: string;
  aliases: string[];
  industry: string;
  company_stage: string;
  headquarters: string;
  overall_rating: number;
  work_life_balance: number;
  culture_score: number;
  career_growth: number;
  verdict: CompanyVerdict;
  condition_summary: string;
  positives: string[];
  kesah_kesuh: string[];
  common_positions: string[];
  typical_tech_stack: string[];
  typical_jd_summary: string;
  salary_idr_junior: string;
  salary_idr_mid: string;
  salary_idr_senior: string;
  source_notes: string;
}

export async function listCompanyKnowledge(
  query = ""
): Promise<CompanyKnowledgeRecord[]> {
  const qs = query ? `?q=${encodeURIComponent(query)}` : "";
  const res = await fetch(`${API_URL}/api/companies/knowledge${qs}`);
  if (!res.ok) throw new Error(`Failed to load company DB (${res.status})`);
  return res.json();
}

export async function upsertCompanyKnowledge(
  record: CompanyKnowledgeRecord
): Promise<CompanyKnowledgeRecord> {
  const res = await fetch(`${API_URL}/api/companies/knowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
  if (!res.ok) throw new Error(`Failed to save company record (${res.status})`);
  return res.json();
}

export async function deleteCompanyKnowledge(companyName: string): Promise<void> {
  const res = await fetch(
    `${API_URL}/api/companies/knowledge/${encodeURIComponent(companyName)}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error(`Failed to delete company (${res.status})`);
}

// ---------------------------------------------------------------------------
// System-Aware CareerOS AI Copilot Chatbot (Token-by-Token SSE)
// ---------------------------------------------------------------------------

export async function streamCopilotChat(
  payload: {
    language: "id" | "en";
    messages: InterviewTurn[];
  },
  callbacks: {
    onContext?: (sources: string[]) => void;
    onToken: (token: string) => void;
  },
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_URL}/api/copilot/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Copilot chat stream failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const trimmed = chunk.trim();
      if (!trimmed.startsWith("data:")) continue;
      const parsed = JSON.parse(trimmed.slice(5).trim()) as {
        type: "context" | "token" | "done" | "error";
        sources?: string[];
        content?: string;
        message?: string;
      };
      if (parsed.type === "error") {
        throw new Error(parsed.message || "Copilot AI error");
      }
      if (parsed.type === "context" && parsed.sources) {
        callbacks.onContext?.(parsed.sources);
      }
      if (parsed.type === "token" && parsed.content) {
        callbacks.onToken(parsed.content);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// CV-Matched Job Finder (Indonesia + Global Remote + HR Post Discovery)
// ---------------------------------------------------------------------------

export type JobScope = "indonesia" | "remote" | "both";

export interface MatchedJobListing {
  job_id: string;
  title: string;
  company: string;
  location: string;
  work_mode: "Remote" | "Hybrid" | "On-site";
  source: string;
  posted_at: string;
  posted_age_label: string;
  job_url: string;
  salary_info: string;
  company_industry: string;
  company_about: string;
  company_verdict: string;
  company_rating: number | null;
  company_salary_idr: string;
  description: string;
  matched_skills: string[];
  missing_skills: string[];
  match_score: number;
}

export interface HrSearchShortcut {
  platform: string;
  title: string;
  description: string;
  search_url: string;
}

export interface JobFinderResponse {
  query_roles: string[];
  scope: JobScope;
  total_fetched: number;
  jobs: MatchedJobListing[];
  hr_post_shortcuts: HrSearchShortcut[];
  source_counts: Record<string, number>;
  warnings: string[];
}

export async function findMatchingJobs(payload: {
  roles: string[];
  scope: JobScope;
  hours_old?: number;
  limit_per_source?: number;
  allow_live_fetch?: boolean;
}): Promise<JobFinderResponse> {
  const res = await fetch(`${API_URL}/api/jobs/find`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Job Finder failed (${res.status})`);
  return res.json();
}

export async function getSavedMatchingJobs(
  scope: JobScope = "both"
): Promise<JobFinderResponse> {
  const res = await fetch(`${API_URL}/api/jobs/saved?scope=${scope}`);
  if (!res.ok) throw new Error(`Failed to load saved jobs (${res.status})`);
  return res.json();
}

export interface PlatformStatus {
  duckdb_path: string;
  bronze_tables: Record<string, number>;
  dbt_gold_marts: Record<string, number>;
  dbt_ready: boolean;
  dagster_assets: string[];
  phoenix_tracing: {
    enabled: boolean;
    status: string;
    endpoint: string;
    ui_url: string;
  };
}

export async function fetchPlatformStatus(): Promise<PlatformStatus> {
  const res = await fetch(`${API_URL}/api/platform/status`);
  if (!res.ok) throw new Error(`Failed to fetch platform status (${res.status})`);
  return res.json();
}
