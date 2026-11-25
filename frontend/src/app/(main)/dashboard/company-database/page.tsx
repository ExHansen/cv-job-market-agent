"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import {
  AlertTriangle,
  Banknote,
  Building2,
  CheckCircle2,
  Database,
  Plus,
  Search,
  Sparkles,
  Star,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

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
import { Textarea } from "@/components/ui/textarea";
import {
  type CompanyKnowledgeRecord,
  type CompanyVerdict,
  deleteCompanyKnowledge,
  listCompanyKnowledge,
  upsertCompanyKnowledge,
} from "@/lib/cv-api";

export default function CompanyDatabasePage() {
  const [records, setRecords] = useState<CompanyKnowledgeRecord[]>([]);
  const [query, setQuery] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);

  // Add / enrich company form state (e.g. from user's Glassdoor / JobStreet notes)
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("Technology");
  const [stage, setStage] = useState("Growth Startup");
  const [verdict, setVerdict] = useState<CompanyVerdict>("Recommended");
  const [rating, setRating] = useState("4.0");
  const [wlb, setWlb] = useState("3.8");
  const [summary, setSummary] = useState("");
  const [positivesText, setPositivesText] = useState("");
  const [consText, setConsText] = useState("");
  const [positionsText, setPositionsText] = useState("Data Engineer, Data Analyst");
  const [stackText, setStackText] = useState("Python, SQL, dbt, Airflow");
  const [jdSummary, setJdSummary] = useState("");
  const [salaryJunior, setSalaryJunior] = useState("Rp 9.000.000 – Rp 14.000.000 / bulan");
  const [salaryMid, setSalaryMid] = useState("Rp 15.000.000 – Rp 25.000.000 / bulan");
  const [salarySenior, setSalarySenior] = useState("Rp 26.000.000 – Rp 42.000.000 / bulan");
  const [saving, setSaving] = useState(false);

  async function reload(search = query) {
    try {
      const data = await listCompanyKnowledge(search);
      setRecords(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal memuat Company Knowledge DB");
    }
  }

  useEffect(() => {
    reload("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSaveCompany() {
    if (!companyName.trim()) {
      toast.error("Nama perusahaan wajib diisi.");
      return;
    }
    setSaving(true);
    try {
      const splitLines = (v: string) =>
        v
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean);
      const splitComma = (v: string) =>
        v
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

      await upsertCompanyKnowledge({
        company_name: companyName.trim(),
        aliases: [],
        industry,
        company_stage: stage,
        headquarters: "Indonesia",
        overall_rating: Math.min(5, Math.max(1, Number(rating) || 3.8)),
        work_life_balance: Math.min(5, Math.max(1, Number(wlb) || 3.5)),
        culture_score: 3.8,
        career_growth: 3.8,
        verdict,
        condition_summary: summary,
        positives: splitLines(positivesText),
        kesah_kesuh: splitLines(consText),
        common_positions: splitComma(positionsText),
        typical_tech_stack: splitComma(stackText),
        typical_jd_summary: jdSummary,
        salary_idr_junior: salaryJunior,
        salary_idr_mid: salaryMid,
        salary_idr_senior: salarySenior,
        source_notes: "Manual user enrichment (Glassdoor / JobStreet / Community notes)",
      });
      toast.success(`${companyName} tersimpan di DuckDB & langsung dipelajari AI Copilot!`);
      setCompanyName("");
      setSummary("");
      setPositivesText("");
      setConsText("");
      setJdSummary("");
      setShowAddForm(false);
      await reload(query);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan data perusahaan");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(name: string) {
    try {
      await deleteCompanyKnowledge(name);
      setRecords((prev) => prev.filter((r) => r.company_name !== name));
      toast.info(`${name} dihapus dari database lokal.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menghapus");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary" className="gap-1.5">
            <Database className="size-3.5" />
            DuckDB Company Knowledge Base ({records.length} perusahaan)
          </Badge>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Database Kondisi Perusahaan, Positives, Keluh Kesah &amp; Gaji IDR
          </h1>
          <p className="text-muted-foreground text-sm">
            Pengetahuan terstruktur yang dibaca langsung oleh <strong>AI Copilot</strong> &amp; <strong>Company Deep-Dive</strong> untuk menilai apakah perusahaan bagus atau tidak.
          </p>
        </div>

        <Button onClick={() => setShowAddForm((v) => !v)} className="gap-1.5">
          <Plus className="size-4" />
          {showAddForm ? "Tutup Form" : "Tambah / Ajari AI Perusahaan Baru"}
        </Button>
      </div>

      {/* Add / Enrich Form */}
      {showAddForm && (
        <Card className="border-primary/40">
          <CardHeader>
            <CardTitle className="text-base">
              Tambah / Update Data Perusahaan ke DuckDB
            </CardTitle>
            <CardDescription>
              Kamu bisa memasukkan catatan dari review Glassdoor, JobStreet, atau komunitas agar AI Copilot langsung mempelajarinya.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-4">
              <div className="space-y-1">
                <Label className="text-xs">Nama Perusahaan *</Label>
                <Input
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="cth: Flip, Bibit, Telkomsel..."
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Industri</Label>
                <Input value={industry} onChange={(e) => setIndustry(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Verdict</Label>
                <Select value={verdict} onValueChange={(v) => setVerdict(v as CompanyVerdict)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Recommended">Recommended</SelectItem>
                    <SelectItem value="Mixed - Selective">Mixed - Selective</SelectItem>
                    <SelectItem value="Caution">Caution</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-xs">Rating (1-5)</Label>
                  <Input value={rating} onChange={(e) => setRating(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">WLB (1-5)</Label>
                  <Input value={wlb} onChange={(e) => setWlb(e.target.value)} />
                </div>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">Kondisi Perusahaan (Ringkasan)</Label>
                <Textarea
                  rows={2}
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="Skala bisnis, stabilitas, fase pertumbuhan..."
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Ringkasan Jobdesc Umum</Label>
                <Textarea
                  rows={2}
                  value={jdSummary}
                  onChange={(e) => setJdSummary(e.target.value)}
                  placeholder="Tanggung jawab utama posisi data di perusahaan ini..."
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">The Positives (1 poin per baris)</Label>
                <Textarea
                  rows={3}
                  value={positivesText}
                  onChange={(e) => setPositivesText(e.target.value)}
                  placeholder="Tech stack modern&#10;WLB sehat & hybrid&#10;Bonus kompetitif"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Keluh Kesah / Cons (1 poin per baris)</Label>
                <Textarea
                  rows={3}
                  value={consText}
                  onChange={(e) => setConsText(e.target.value)}
                  placeholder="Birokrasi approval lambat&#10;Ad-hoc request tinggi"
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-1">
                <Label className="text-xs">Estimasi Gaji Junior (IDR)</Label>
                <Input value={salaryJunior} onChange={(e) => setSalaryJunior(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Estimasi Gaji Mid (IDR)</Label>
                <Input value={salaryMid} onChange={(e) => setSalaryMid(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Estimasi Gaji Senior (IDR)</Label>
                <Input value={salarySenior} onChange={(e) => setSalarySenior(e.target.value)} />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-1">
                <Label className="text-xs">Stage Perusahaan</Label>
                <Input value={stage} onChange={(e) => setStage(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Posisi Umum (pisah koma)</Label>
                <Input value={positionsText} onChange={(e) => setPositionsText(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tech Stack (pisah koma)</Label>
                <Input value={stackText} onChange={(e) => setStackText(e.target.value)} />
              </div>
            </div>

            <div className="flex justify-end">
              <Button onClick={handleSaveCompany} disabled={saving}>
                {saving ? "Menyimpan..." : "Simpan ke DuckDB"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search Bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              reload(e.target.value);
            }}
            placeholder="Cari perusahaan atau industri (cth: Bank Jago, Fintech, E-Commerce, Shopee...)"
            className="pl-9"
          />
        </div>
      </div>

      {/* Company Cards Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {records.map((rec) => (
          <Card key={rec.company_name} className="flex flex-col justify-between">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Building2 className="size-4 text-primary" />
                    {rec.company_name}
                  </CardTitle>
                  <CardDescription>
                    {rec.industry} {rec.company_stage ? `• ${rec.company_stage}` : ""}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-1.5">
                  <Badge
                    variant={
                      rec.verdict === "Recommended"
                        ? "default"
                        : rec.verdict === "Caution"
                          ? "destructive"
                          : "secondary"
                    }
                  >
                    {rec.verdict}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 text-muted-foreground hover:text-destructive"
                    onClick={() => handleDelete(rec.company_name)}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-2 text-xs">
                <Badge variant="outline" className="gap-1">
                  <Star className="size-3 text-amber-500" />
                  Rating {rec.overall_rating}/5
                </Badge>
                <Badge variant="outline">WLB {rec.work_life_balance}/5</Badge>
                <Badge variant="outline">Culture {rec.culture_score}/5</Badge>
                <Badge variant="outline">Growth {rec.career_growth}/5</Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-4 text-xs">
              <p className="text-sm text-muted-foreground">{rec.condition_summary}</p>

              {/* IDR Salary Box */}
              <div className="rounded-lg border bg-muted/40 p-3 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                  <Banknote className="size-3.5 text-emerald-500" />
                  Estimasi Range Gaji (IDR / Bulan)
                </div>
                <div className="grid gap-1 sm:grid-cols-3 text-[11px] text-muted-foreground">
                  <div>
                    <span className="font-medium text-foreground">Junior:</span>{" "}
                    {rec.salary_idr_junior || "-"}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Mid:</span>{" "}
                    {rec.salary_idr_mid || "-"}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Senior:</span>{" "}
                    {rec.salary_idr_senior || "-"}
                  </div>
                </div>
              </div>

              {/* Positives & Keluh Kesah */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <div className="font-semibold text-emerald-500">The Positives</div>
                  <ul className="space-y-1 text-muted-foreground">
                    {rec.positives.map((p, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-emerald-500" />
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="space-y-1.5">
                  <div className="font-semibold text-amber-500">Keluh Kesah (Cons)</div>
                  <ul className="space-y-1 text-muted-foreground">
                    {rec.kesah_kesuh.map((c, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <AlertTriangle className="mt-0.5 size-3 shrink-0 text-amber-500" />
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {rec.typical_jd_summary && (
                <div>
                  <span className="font-semibold">Pola JD Umum: </span>
                  <span className="text-muted-foreground">{rec.typical_jd_summary}</span>
                </div>
              )}

              <div className="flex flex-wrap gap-1">
                {rec.typical_tech_stack.map((tech) => (
                  <Badge key={tech} variant="secondary" className="text-[10px]">
                    {tech}
                  </Badge>
                ))}
              </div>

              <Separator />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[10px] text-muted-foreground">{rec.source_notes}</span>
                <div className="flex gap-1.5">
                  <Button asChild size="sm" variant="outline" className="h-7 text-xs">
                    <Link
                      href={`/dashboard/cv-studio?company=${encodeURIComponent(rec.company_name)}&role=Data%20Engineer`}
                    >
                      <Sparkles className="mr-1 size-3" />
                      Buat CV
                    </Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
