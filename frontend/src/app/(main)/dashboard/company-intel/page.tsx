"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";

import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  ExternalLink,
  HelpCircle,
  Search,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";

import {
  AgentProgressPanel,
  type ProgressStep,
} from "@/components/agent-progress-panel";
import { InlineMarkdown } from "@/components/inline-markdown";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type CompanyDeepDiveReport,
  createApplication,
  streamCompanyDeepDive,
} from "@/lib/cv-api";

const DEEP_DIVE_STEPS: ProgressStep[] = [
  { id: "research", label: "1. Riset Publik & JD", detail: "Wikipedia / ATS / LinkedIn" },
  { id: "profile_match", label: "2. Ekstrak Stack & Profil", detail: "Cocokkan Master Profile" },
  { id: "llm_analysis", label: "3. Analisis AI Lokal", detail: "Kelebihan, gap & kebutuhan" },
  { id: "finalize", label: "4. Laporan Siap", detail: "Validasi skema selesai" },
];

export default function CompanyIntelPage() {
  const [companyName, setCompanyName] = useState("FIT HUB");
  const [targetRole, setTargetRole] = useState("Data Engineer");
  const [jobUrl, setJobUrl] = useState("");
  const [pastedJd, setPastedJd] = useState("");
  const [language, setLanguage] = useState<"id" | "en">("id");
  const [useLlm, setUseLlm] = useState(true);

  const [loading, setLoading] = useState(false);
  const [activeStage, setActiveStage] = useState("research");
  const [progressPct, setProgressPct] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [elapsedSec, setElapsedSec] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const [report, setReport] = useState<CompanyDeepDiveReport | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!loading) return;
    const id = window.setInterval(() => {
      setElapsedSec((prev) => prev + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [loading]);

  function handleCancel() {
    abortRef.current?.abort();
    setLoading(false);
    toast.info("Analisis dibatalkan.");
  }

  async function handleAnalyze() {
    if (!companyName.trim() && !jobUrl.trim() && !pastedJd.trim()) {
      toast.error("Masukkan nama perusahaan atau link lowongan terlebih dahulu.");
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setErrorMsg("");
    setActiveStage("research");
    setProgressPct(8);
    setElapsedSec(0);
    setStatusMessage("Menghubungkan ke backend AI Agent...");

    try {
      const data = await streamCompanyDeepDive(
        {
          company_name: companyName,
          target_role: targetRole,
          job_url: jobUrl,
          pasted_jd: pastedJd,
          language,
          use_llm: useLlm,
        },
        (ev) => {
          if (ev.stage) setActiveStage(ev.stage);
          if (typeof ev.percent === "number") setProgressPct(ev.percent);
          if (ev.message) setStatusMessage(ev.message);
          if (typeof ev.elapsed_sec === "number") {
            setElapsedSec(Math.floor(ev.elapsed_sec));
          }
        },
        controller.signal
      );
      setReport(data);
      setProgressPct(100);
      toast.success(`Analisis ${data.company_name} selesai!`);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message = err instanceof Error ? err.message : "Gagal menganalisis perusahaan";
      setErrorMsg(message);
      toast.error(message);
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  async function handleSaveToTracker() {
    if (!report) return;
    try {
      await createApplication({
        company: report.company_name,
        role: report.target_role,
        status: "wishlist",
        job_url: report.job_url_found || jobUrl,
        notes: `${report.industry} — ${report.business_model}`.slice(0, 220),
      });
      toast.success(`${report.company_name} tersimpan ke Application Tracker!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan ke tracker");
    }
  }

  const studioHref = report
    ? `/dashboard/cv-studio?company=${encodeURIComponent(report.company_name)}&role=${encodeURIComponent(report.target_role)}&jobUrl=${encodeURIComponent(report.job_url_found || jobUrl)}`
    : "/dashboard/cv-studio";

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="gap-1.5">
              <Building2 className="size-3.5" />
              Company Deep-Dive Intelligence
            </Badge>
            <Badge variant="outline">LinkedIn URL + Public Intel + Master Profile Fit</Badge>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Riset Perusahaan: Kelebihan, Kekurangan &amp; Kebutuhan Mereka
          </h1>
          <p className="text-muted-foreground text-sm">
            Pahami bisnis, kekuatan, tantangan/pain points perusahaan target, dan bagaimana pengalamanmu bisa menjawab kebutuhan mereka.
          </p>
        </div>

        {report && (
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={handleSaveToTracker}>
              Simpan ke Tracker
            </Button>
            <Button asChild className="gap-2">
              <Link href={studioHref}>
                Lanjut Buat CV untuk {report.company_name}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        )}
      </div>

      {/* Input Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Search className="size-4 text-primary" />
            Masukkan Perusahaan atau Link Lowongan
          </CardTitle>
          <CardDescription>
            Bisa langsung paste link LinkedIn (`/jobs/search-results/?currentJobId=...`) tanpa mengetik nama perusahaan, atau ketik nama perusahaan saja.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="companyName">Nama Perusahaan</Label>
              <Input
                id="companyName"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="cth: FIT HUB, Bank Jago, Shopee..."
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="targetRole">Role Target</Label>
              <Select value={targetRole} onValueChange={setTargetRole}>
                <SelectTrigger id="targetRole">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Data Engineer">Data Engineer</SelectItem>
                  <SelectItem value="Data Quality Engineer">Data Quality Engineer</SelectItem>
                  <SelectItem value="Data Analyst">Data Analyst</SelectItem>
                  <SelectItem value="Analytics Engineer">Analytics Engineer</SelectItem>
                  <SelectItem value="AI Engineer">AI Engineer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="lang">Bahasa Laporan</Label>
              <Select
                value={language}
                onValueChange={(val) => setLanguage(val as "id" | "en")}
              >
                <SelectTrigger id="lang">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="id">Bahasa Indonesia</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="jobUrl">Link Lowongan LinkedIn / ATS (Opsional)</Label>
            <Input
              id="jobUrl"
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
              placeholder="https://www.linkedin.com/jobs/search-results/?currentJobId=..."
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pastedJd">Teks Job Description Tambahan (Opsional)</Label>
            <Textarea
              id="pastedJd"
              rows={3}
              value={pastedJd}
              onChange={(e) => setPastedJd(e.target.value)}
              placeholder="Jika link terkunci login, paste teks JD di sini untuk analisis lebih tajam..."
            />
          </div>

          <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Switch id="deepDiveLlm" checked={useLlm} onCheckedChange={setUseLlm} />
              <Label htmlFor="deepDiveLlm" className="cursor-pointer text-xs">
                Gunakan Local LLM (Ollama) untuk analisis strategis mendalam
              </Label>
            </div>

            <Button onClick={handleAnalyze} disabled={loading} className="gap-2">
              <Sparkles className="size-4" />
              {loading ? "Sedang Meriset Perusahaan..." : "Analisis Perusahaan"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <AgentProgressPanel
          title={`Menganalisis ${companyName || "Perusahaan Target"}`}
          steps={DEEP_DIVE_STEPS}
          activeStageId={activeStage}
          percent={progressPct}
          statusMessage={statusMessage}
          elapsedSec={elapsedSec}
          etaHint={
            useLlm
              ? "Est. ~25–60 detik (Local LLM Ollama)"
              : "Est. ~2–5 detik (Mode Cepat)"
          }
          onCancel={handleCancel}
        />
      )}

      {errorMsg && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>Gagal Menganalisis</AlertTitle>
          <AlertDescription>{errorMsg}</AlertDescription>
        </Alert>
      )}

      {/* Analysis Result */}
      {report && (
        <div className="space-y-6">
          {/* Overview Card */}
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Building2 className="size-5 text-primary" />
                    {report.company_name}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    {report.industry} • Target Role: {report.target_role}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">JD: {report.jd_source}</Badge>
                  <Badge variant="outline">
                    {report.used_llm ? "AI Deep Analysis" : "Fast Deterministic"}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-relaxed">
                <InlineMarkdown text={report.company_overview} />
              </p>
              <div className="rounded-lg bg-muted/50 p-3 text-sm">
                <span className="font-semibold">Model Bisnis: </span>
                <span className="text-muted-foreground">
                  <InlineMarkdown text={report.business_model} />
                </span>
              </div>

              {report.detected_tech_stack.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-xs font-medium text-muted-foreground">
                    Tech Stack / Skill Terdeteksi di Perusahaan &amp; JD
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {report.detected_tech_stack.map((tech) => (
                      <Badge key={tech} variant="default">
                        {tech}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {report.sources.length > 0 && (
                <div className="flex flex-wrap items-center gap-3 pt-1 text-xs text-muted-foreground">
                  <span>Sumber:</span>
                  {report.sources.map((src) => (
                    <a
                      key={src}
                      href={src}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 underline hover:text-foreground"
                    >
                      {src.replace(/^https?:\/\//, "").slice(0, 48)}
                      <ExternalLink className="size-3" />
                    </a>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Strengths vs Weaknesses / Challenges */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="border-emerald-500/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-emerald-500">
                  <TrendingUp className="size-4" />
                  Kelebihan &amp; Kekuatan Perusahaan
                </CardTitle>
                <CardDescription>
                  Keunggulan bisnis, skala, dan nilai positif perusahaan ini.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2.5 text-sm">
                  {report.strengths.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2.5">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-500" />
                      <span>
                        <InlineMarkdown text={item} />
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card className="border-amber-500/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-amber-500">
                  <AlertTriangle className="size-4" />
                  Kekurangan, Tantangan &amp; Pain Points
                </CardTitle>
                <CardDescription>
                  Bottleneck operasional/data &amp; tantangan bisnis yang mereka hadapi (berdasarkan sinyal JD &amp; industri).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2.5 text-sm">
                  {report.weaknesses_and_challenges.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2.5">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" />
                      <span>
                        <InlineMarkdown text={item} />
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          {/* What They Need & How You Fit */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Target className="size-4 text-primary" />
                  Apa yang Sebenarnya Mereka Butuhkan
                </CardTitle>
                <CardDescription>
                  Masalah inti yang ingin diselesaikan hiring manager lewat posisi {report.target_role}.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-2 pl-5 text-sm">
                  {report.inferred_team_needs.map((need, idx) => (
                    <li key={idx}>
                      <InlineMarkdown text={need} />
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="size-4 text-primary" />
                  Cara Profil Kamu Menjawab Kebutuhan Ini
                </CardTitle>
                <CardDescription>
                  Dipetakan langsung dari fakta terverifikasi di Master Profile kamu.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-2 pl-5 text-sm">
                  {report.how_candidate_fits.map((fit, idx) => (
                    <li key={idx}>
                      <InlineMarkdown text={fit} />
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          {/* Smart Interview Questions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <HelpCircle className="size-4 text-primary" />
                Pertanyaan Cerdas untuk Ditanyakan Saat Interview
              </CardTitle>
              <CardDescription>
                Menunjukkan bahwa kamu benar-benar memahami bisnis dan tantangan tim data mereka.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {report.smart_interview_questions.map((q, idx) => (
                <div key={idx} className="rounded-lg border px-4 py-3 text-sm">
                  <span className="font-semibold text-primary">Q{idx + 1}. </span>
                  <InlineMarkdown text={q} />
                </div>
              ))}
              <Separator />
              <div className="flex justify-end pt-1">
                <Button asChild className="gap-2">
                  <Link href={studioHref}>
                    Lanjut Buat CV Khusus {report.company_name}
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
