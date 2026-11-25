"use client";

import { useEffect, useRef, useState } from "react";

import {
  Activity,
  AlertTriangle,
  Building2,
  CheckCircle2,
  Cpu,
  Download,
  FileCheck2,
  FolderGit2,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import {
  AgentProgressPanel,
  type ProgressStep,
} from "@/components/agent-progress-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  API_URL,
  createApplication,
  fetchHealth,
  fetchMarketTrends,
  type MarketSnapshot,
  renderCvPdf,
  streamTailorCV,
  type TailorResponse,
} from "@/lib/cv-api";

const chartConfig = {
  frequency_pct: {
    label: "Job Market Demand (%)",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

const CV_STUDIO_STEPS: ProgressStep[] = [
  { id: "company_research", label: "1. Company & JD", detail: "Riset profil & lowongan" },
  { id: "gap_audit", label: "2. Market & Gap Audit", detail: "Cocokkan tren DuckDB" },
  { id: "rewrite_cv", label: "3. Local LLM Rewrite", detail: "Tulis ulang XYZ bullets" },
  { id: "fact_check", label: "4. Fact-Check Guardrail", detail: "Cek anti-halusinasi" },
];

export default function CvStudioPage() {
  const [role, setRole] = useState("Data Engineer");
  const [company, setCompany] = useState("Bank Jago");
  const [jobUrl, setJobUrl] = useState("");
  const [region, setRegion] = useState("Indonesia");
  const [jdText, setJdText] = useState("");
  const [useLlm, setUseLlm] = useState(true);

  const [health, setHealth] = useState<{ model: string; llm_provider: string } | null>(null);
  const [market, setMarket] = useState<MarketSnapshot | null>(null);
  const [backendError, setBackendError] = useState("");

  const [running, setRunning] = useState(false);
  const [activeStage, setActiveStage] = useState("company_research");
  const [progressPct, setProgressPct] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [elapsedSec, setElapsedSec] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const [rendering, setRendering] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [pdfFilename, setPdfFilename] = useState("");
  const [streamEvents, setStreamEvents] = useState<string[]>([]);
  const [result, setResult] = useState<TailorResponse | null>(null);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setElapsedSec((prev) => prev + 1);
      setProgressPct((prev) => (prev >= 55 && prev < 92 ? prev + 1 : prev));
    }, 1000);
    return () => window.clearInterval(id);
  }, [running]);

  function handleCancel() {
    abortRef.current?.abort();
    setRunning(false);
    toast.info("Proses tailoring CV dibatalkan.");
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const qCompany = params.get("company");
    const qRole = params.get("role");
    const qJobUrl = params.get("jobUrl");
    if (qCompany) setCompany(qCompany);
    if (qRole) setRole(qRole);
    if (qJobUrl) setJobUrl(qJobUrl);

    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    setBackendError("");
    fetchMarketTrends(role, region)
      .then(setMarket)
      .catch((err) => setBackendError(err instanceof Error ? err.message : String(err)));
  }, [role, region]);

  const payload = {
    target_role: role,
    target_company: company,
    job_url: jobUrl,
    region,
    target_jd_text: jdText,
    output_language: "en" as const,
    use_llm: useLlm,
  };

  async function handleRunAgent() {
    const controller = new AbortController();
    abortRef.current = controller;

    setRunning(true);
    setDownloadUrl("");
    setActiveStage("company_research");
    setProgressPct(12);
    setElapsedSec(0);
    setStatusMessage("Memulai riset perusahaan & lowongan...");
    setStreamEvents(["Connecting to LangGraph agent stream..."]);
    try {
      const output = await streamTailorCV(
        payload,
        (node, data) => {
          if (Array.isArray(data.events)) {
            setStreamEvents(data.events as string[]);
            const latest = (data.events as string[]).at(-1);
            if (latest) setStatusMessage(latest);
          }
          if (node === "company_research") {
            setActiveStage("gap_audit");
            setProgressPct(30);
          } else if (node === "market_intel") {
            setActiveStage("gap_audit");
            setProgressPct(42);
          } else if (node === "gap_audit") {
            setActiveStage("rewrite_cv");
            setProgressPct(55);
            setStatusMessage(
              useLlm
                ? "Local LLM sedang menulis ulang CV (estimasi ~25–60 detik)..."
                : "Menyusun baseline CV terverifikasi..."
            );
          } else if (node === "rewrite_cv") {
            setActiveStage("fact_check");
            setProgressPct(92);
          } else if (node === "fact_check" || node === "done") {
            setActiveStage("fact_check");
            setProgressPct(100);
          }
        },
        controller.signal
      );
      setResult(output);
      toast.success(
        `CV tailored (${output.fact_check.ats_score}% ATS) — ${output.fact_check.passed ? "Grounded" : "Review warnings"}`
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      toast.error(err instanceof Error ? err.message : "Agent execution failed");
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  async function handleExportPdf() {
    setRendering(true);
    try {
      const res = await renderCvPdf(payload);
      if (res.download_url) {
        setDownloadUrl(`${API_URL}${res.download_url}`);
        setPdfFilename(res.filename);
        toast.success(`Compiled ${res.filename} with RenderCV (Typst)!`);
      } else {
        toast.error(res.stderr || "PDF compilation failed");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to render PDF");
    } finally {
      setRendering(false);
    }
  }

  async function handleSaveToTracker() {
    const targetCompany = result?.company_intel.company_name || company || "Target Company";
    try {
      await createApplication({
        company: targetCompany,
        role: result?.company_intel.job_title_found || role,
        status: "applied",
        ats_score: result?.fact_check.ats_score ?? null,
        job_url: result?.company_intel.job_url_found || jobUrl,
        pdf_filename: pdfFilename,
        notes: result?.fact_check.passed
          ? `Tailored CV passed anti-hallucination check (${result.fact_check.ats_score}% ATS).`
          : "",
      });
      toast.success(`${targetCompany} tersimpan ke Application Tracker!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan ke tracker");
    }
  }

  const chartData = market
    ? [...market.top_mandatory_skills, ...market.rising_skills].slice(0, 10)
    : [];

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="gap-1.5">
              <Cpu className="size-3.5" />
              {health ? `${health.llm_provider} • ${health.model}` : "Local Ollama / FastAPI"}
            </Badge>
            <Badge variant="outline">LangGraph + DuckDB + RenderCV</Badge>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            CV &amp; Company Intelligence Studio
          </h1>
          <p className="text-muted-foreground text-sm">
            Riset profil perusahaan target &amp; kondisi job market, lalu buat CV ATS-friendly tanpa halusinasi.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Target Role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Data Engineer">Data Engineer</SelectItem>
              <SelectItem value="Data Quality Engineer">Data Quality Engineer</SelectItem>
              <SelectItem value="Data Analyst">Data Analyst</SelectItem>
              <SelectItem value="Analytics Engineer">Analytics Engineer</SelectItem>
              <SelectItem value="AI Engineer">AI Engineer</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="Region"
            className="w-36"
          />
        </div>
      </div>

      {backendError && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>Backend API Belum Aktif</AlertTitle>
          <AlertDescription>
            Jalankan FastAPI di port 8000 (`.\.venv\Scripts\uvicorn.exe cv_agent.api.main:app --reload --port 8000`). Detail: {backendError}
          </AlertDescription>
        </Alert>
      )}

      {/* Top Grid: Market Radar + Target Company Form */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Radar className="size-4 text-primary" />
                Job Market Skill Demand ({role} — {region})
              </CardTitle>
              <CardDescription>
                Agregasi DuckDB dari {market?.sample_size ?? 0} lowongan kerja
              </CardDescription>
            </div>
            <Badge variant="outline">
              {market?.top_mandatory_skills.length ?? 0} Core Skills
            </Badge>
          </CardHeader>
          <CardContent className="pt-4">
            <ChartContainer config={chartConfig} className="h-[310px] w-full">
              <BarChart data={chartData} layout="vertical" margin={{ left: 16, right: 16 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tickLine={false} axisLine={false} unit="%" />
                <YAxis
                  type="category"
                  dataKey="skill"
                  tickLine={false}
                  axisLine={false}
                  width={135}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="frequency_pct" fill="var(--color-frequency_pct)" radius={6} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4 text-primary" />
              Target Perusahaan &amp; Tailor CV
            </CardTitle>
            <CardDescription>
              Masukkan nama perusahaan agar agent meriset bisnis &amp; JD-nya otomatis.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="company">Perusahaan Target</Label>
              <Input
                id="company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Shopee, Bank Jago, Traveloka, Grab..."
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="jobUrl">Link Lowongan (Opsional)</Label>
              <Input
                id="jobUrl"
                value={jobUrl}
                onChange={(e) => setJobUrl(e.target.value)}
                placeholder="https://boards.greenhouse.io/..."
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="jdText">Atau Paste Job Description (Opsional)</Label>
              <Textarea
                id="jdText"
                rows={3}
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder="Tempel persyaratan lowongan di sini..."
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border px-3 py-2">
              <Label htmlFor="useLlm" className="cursor-pointer text-xs">
                Gunakan Local LLM (Ollama)
              </Label>
              <Switch id="useLlm" checked={useLlm} onCheckedChange={setUseLlm} />
            </div>

            <div className="flex flex-col gap-2 pt-1">
              <Button onClick={handleRunAgent} disabled={running} className="w-full">
                {running ? "Riset Perusahaan & Tailor CV..." : "Riset & Buat CV"}
              </Button>
              <Button
                variant="outline"
                onClick={handleExportPdf}
                disabled={rendering}
                className="w-full gap-2"
              >
                <Download className="size-4" />
                {rendering ? "Compiling Typst PDF..." : "Compile ATS PDF (RenderCV)"}
              </Button>
              {downloadUrl && (
                <Button asChild variant="secondary" size="sm" className="w-full">
                  <a href={downloadUrl} target="_blank" rel="noreferrer">
                    Download PDF CV Siap Lamar →
                  </a>
                </Button>
              )}
              {result && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSaveToTracker}
                  className="w-full text-xs"
                >
                  + Simpan ke Application Tracker
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Live Progress Stepper while running */}
      {running && (
        <AgentProgressPanel
          title={`Menyusun CV ATS untuk ${company || role}`}
          steps={CV_STUDIO_STEPS}
          activeStageId={activeStage}
          percent={progressPct}
          statusMessage={statusMessage}
          elapsedSec={elapsedSec}
          etaHint={
            useLlm
              ? "Est. ~25–60 detik (Local LLM Ollama)"
              : "Est. ~2–4 detik (Mode Cepat)"
          }
          onCancel={handleCancel}
        />
      )}

      {/* Live LangGraph Execution Trace */}
      {streamEvents.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Activity className="size-4 text-primary" />
              Live LangGraph Execution Trace
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 font-mono text-xs text-muted-foreground">
              {streamEvents.map((ev, i) => (
                <li key={i}>→ {ev}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Results Area */}
      {result && (
        <div className="space-y-6">
          {/* KPI Summary Row */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>ATS Market Coverage Score</CardDescription>
                <CardTitle className="text-3xl">{result.fact_check.ats_score}%</CardTitle>
              </CardHeader>
              <CardContent>
                <Progress value={result.fact_check.ats_score} className="h-2" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Anti-Hallucination Guardrail</CardDescription>
                <CardTitle className="flex items-center gap-2 text-xl">
                  {result.fact_check.passed ? (
                    <>
                      <ShieldCheck className="size-5 text-emerald-500" />
                      PASSED (Grounded)
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="size-5 text-amber-500" />
                      {result.fact_check.violations.length} Issues
                    </>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Semua metrik &amp; tools terverifikasi terhadap Master Profile.
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Target Company &amp; Domain</CardDescription>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Building2 className="size-5 text-primary" />
                  {result.company_intel.company_name || "General Market"}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">{result.company_intel.industry}</Badge>
                <Badge variant="outline">JD: {result.company_intel.jd_source}</Badge>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="diff" className="w-full">
            <TabsList>
              <TabsTrigger value="diff">Before vs After CV Diff</TabsTrigger>
              <TabsTrigger value="gaps">Skill Gaps &amp; Quick Wins</TabsTrigger>
              <TabsTrigger value="company">Company Intel &amp; Projects</TabsTrigger>
            </TabsList>

            <TabsContent value="diff" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileCheck2 className="size-4 text-emerald-500" />
                    Rewritten ATS-Optimized Summary &amp; Bullets
                  </CardTitle>
                  <CardDescription>{result.tailored_cv.professional_summary}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {result.tailored_cv.experiences.map((exp) => (
                    <div key={exp.id} className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold text-sm">
                          {exp.role} — {exp.company}
                        </h3>
                        <Badge variant="outline">
                          {exp.start_date} – {exp.end_date}
                        </Badge>
                      </div>
                      <Separator />
                      <div className="space-y-3">
                        {exp.bullets.map((b) => (
                          <div
                            key={b.source_id}
                            className="grid gap-4 rounded-lg border p-3 md:grid-cols-2"
                          >
                            <div>
                              <span className="text-[11px] font-medium uppercase text-muted-foreground">
                                Before ({b.source_id})
                              </span>
                              <p className="mt-1 text-xs text-muted-foreground">{b.original_text}</p>
                            </div>
                            <div>
                              <span className="flex items-center gap-1 text-[11px] font-medium uppercase text-emerald-500">
                                <CheckCircle2 className="size-3.5" />
                                After (ATS XYZ)
                              </span>
                              <p className="mt-1 text-xs">{b.rewritten_text}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="gaps" className="mt-4">
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Matched in Experience</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-1.5">
                    {result.gap_audit.matched_skills.map((s) => (
                      <Badge key={s} variant="default">
                        {s}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Hidden Quick Wins</CardTitle>
                    <CardDescription>Ada di profil, angkat ke Summary/Skills</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-1.5">
                    {result.gap_audit.hidden_quick_wins.map((s) => (
                      <Badge key={s} variant="secondary">
                        {s}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">True Skill Gaps</CardTitle>
                    <CardDescription>Jangan dikarang — jadikan ide project</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-1.5">
                    {result.gap_audit.true_skill_gaps.map((s) => (
                      <Badge key={s} variant="outline">
                        {s}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="company" className="mt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <Building2 className="size-4" />
                      Company Research Summary
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-muted-foreground">
                    <p>
                      {result.company_intel.company_summary ||
                        "Menggunakan profil industri & market benchmark karena tidak ada deskripsi publik langsung."}
                    </p>
                    {result.company_intel.detected_tech_stack.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {result.company_intel.detected_tech_stack.map((t) => (
                          <Badge key={t} variant="secondary">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <FolderGit2 className="size-4" />
                      Prioritized Projects Order
                    </CardTitle>
                    <CardDescription>
                      Diurutkan otomatis berdasarkan relevansi industri perusahaan target.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {result.tailored_cv.projects.slice(0, 3).map((p, idx) => (
                      <div
                        key={p.id}
                        className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"
                      >
                        <span className="font-medium">
                          #{idx + 1} {p.name}
                        </span>
                        <Badge variant="outline">{p.period}</Badge>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
