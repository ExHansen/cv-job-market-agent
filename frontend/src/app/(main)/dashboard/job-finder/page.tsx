"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import {
  Banknote,
  BookmarkPlus,
  BriefcaseBusiness,
  Building2,
  Clock,
  ExternalLink,
  Globe,
  Loader2,
  MapPin,
  Search,
  Sparkles,
  Star,
  Users,
} from "lucide-react";
import { toast } from "sonner";

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
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createApplication,
  findMatchingJobs,
  getSavedMatchingJobs,
  type JobFinderResponse,
  type JobScope,
  type MatchedJobListing,
} from "@/lib/cv-api";

export default function JobFinderPage() {
  const [rolesInput, setRolesInput] = useState("Data Engineer, Data Quality Engineer");
  const [scope, setScope] = useState<JobScope>("both");
  const [hoursOld, setHoursOld] = useState("168");
  const [searching, setSearching] = useState(false);
  const [data, setData] = useState<JobFinderResponse | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [modeFilter, setModeFilter] = useState<"ALL" | "Remote" | "Indonesia">("ALL");

  useEffect(() => {
    getSavedMatchingJobs("both")
      .then(setData)
      .catch(() => null);
  }, []);

  async function handleLiveSearch() {
    const roles = rolesInput
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean);
    if (roles.length === 0) {
      toast.error("Masukkan minimal 1 target posisi (misal: Data Engineer).");
      return;
    }
    setSearching(true);
    try {
      const res = await findMatchingJobs({
        roles,
        scope,
        hours_old: Number(hoursOld) || 168,
        limit_per_source: 12,
        allow_live_fetch: true,
      });
      setData(res);
      toast.success(`Menemukan ${res.jobs.length} lowongan ter-ranking sesuai CV kamu!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal mencari lowongan live");
    } finally {
      setSearching(false);
    }
  }

  async function handleSaveJob(job: MatchedJobListing) {
    try {
      await createApplication({
        company: job.company,
        role: job.title,
        status: "wishlist",
        ats_score: job.match_score,
        job_url: job.job_url,
        notes: `${job.work_mode} • ${job.location} • Posted ${job.posted_age_label}`,
      });
      toast.success(`${job.company} (${job.title}) tersimpan ke Application Tracker!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan lamaran");
    }
  }

  const filteredJobs = (data?.jobs ?? []).filter((j) => {
    if (modeFilter === "Remote") return j.work_mode === "Remote";
    if (modeFilter === "Indonesia") {
      return (
        j.location.toLowerCase().includes("indonesia") ||
        j.location.toLowerCase().includes("jakarta") ||
        j.source === "linkedin" ||
        j.source === "indeed"
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="gap-1.5">
              <BriefcaseBusiness className="size-3.5" />
              CV-Matched Live Job Finder
            </Badge>
            <Badge variant="outline">
              Indonesia (LinkedIn / Indeed) + Global Remote (Remotive / Arbeitnow) + HR Radar
            </Badge>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Cari Lowongan Cocok dengan CV &amp; Radar Postingan HR
          </h1>
          <p className="text-muted-foreground text-sm">
            Otomatis tarik lowongan terbaru (Indonesia &amp; Remote), hitung <strong>Match Score %</strong> terhadap `master_profile.yaml`, lengkapi info perusahaan &amp; gaji IDR dari DuckDB.
          </p>
        </div>
      </div>

      {/* Search Controls */}
      <Card>
        <CardContent className="grid gap-4 pt-6 md:grid-cols-4">
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="rolesInput" className="text-xs">
              Target Posisi (pisah koma)
            </Label>
            <Input
              id="rolesInput"
              value={rolesInput}
              onChange={(e) => setRolesInput(e.target.value)}
              placeholder="Data Engineer, Data Quality Engineer, Analytics Engineer"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Cakupan Lokasi</Label>
            <Select value={scope} onValueChange={(v) => setScope(v as JobScope)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="both">Indonesia + Global Remote</SelectItem>
                <SelectItem value="indonesia">Indonesia Saja</SelectItem>
                <SelectItem value="remote">Remote Global Saja</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Umur Postingan</Label>
            <Select value={hoursOld} onValueChange={setHoursOld}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24">24 Jam Terakhir</SelectItem>
                <SelectItem value="72">3 Hari Terakhir</SelectItem>
                <SelectItem value="168">7 Hari Terakhir</SelectItem>
                <SelectItem value="336">14 Hari Terakhir</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 md:col-span-4">
            <div className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
              {data &&
                Object.entries(data.source_counts).map(([src, count]) => (
                  <Badge key={src} variant="outline">
                    {src}: {count}
                  </Badge>
                ))}
            </div>
            <Button onClick={handleLiveSearch} disabled={searching} className="gap-2">
              {searching ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Menarik Lowongan Live (10–25 dtk)...
                </>
              ) : (
                <>
                  <Search className="size-4" />
                  Cari Lowongan Live Sesuai CV
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {data?.warnings && data.warnings.length > 0 && (
        <Alert>
          <AlertTitle>Catatan Sumber Scraping</AlertTitle>
          <AlertDescription className="text-xs">
            {data.warnings.join(" | ")}
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="listings">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <TabsList>
            <TabsTrigger value="listings">
              Lowongan Cocok CV ({filteredJobs.length})
            </TabsTrigger>
            <TabsTrigger value="hr">
              Radar Postingan HR Indonesia &amp; Remote ({data?.hr_post_shortcuts.length ?? 0})
            </TabsTrigger>
          </TabsList>

          <div className="flex items-center gap-1.5">
            {(["ALL", "Indonesia", "Remote"] as const).map((f) => (
              <Button
                key={f}
                size="sm"
                variant={modeFilter === f ? "default" : "outline"}
                onClick={() => setModeFilter(f)}
                className="h-7 text-xs"
              >
                {f === "ALL" ? "Semua" : f}
              </Button>
            ))}
          </div>
        </div>

        {/* Tab 1: Ranked Job Listings */}
        <TabsContent value="listings" className="mt-4 space-y-4">
          {filteredJobs.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Belum ada lowongan tersimpan untuk filter ini. Klik{" "}
                <strong>&ldquo;Cari Lowongan Live Sesuai CV&rdquo;</strong> di atas untuk menarik lowongan terbaru dari LinkedIn, Indeed, Remotive, dan Arbeitnow!
              </CardContent>
            </Card>
          ) : (
            filteredJobs.map((job) => {
              const isExpanded = expandedId === job.job_id;
              return (
                <Card key={job.job_id}>
                  <CardHeader className="pb-3">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <CardTitle className="text-lg">{job.title}</CardTitle>
                          <Badge
                            variant={job.work_mode === "Remote" ? "default" : "secondary"}
                            className="gap-1"
                          >
                            {job.work_mode === "Remote" ? (
                              <Globe className="size-3" />
                            ) : (
                              <MapPin className="size-3" />
                            )}
                            {job.work_mode}
                          </Badge>
                          <Badge variant="outline" className="uppercase text-[10px]">
                            {job.source}
                          </Badge>
                        </div>

                        <CardDescription className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                          <span className="inline-flex items-center gap-1 font-medium text-foreground">
                            <Building2 className="size-3.5 text-primary" />
                            {job.company} ({job.company_industry})
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="size-3" />
                            {job.location || "Indonesia"}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Clock className="size-3" />
                            Diposting: {job.posted_age_label}
                          </span>
                        </CardDescription>
                      </div>

                      {/* Match Score Meter */}
                      <div className="flex min-w-36 flex-col items-end gap-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">CV Match</span>
                          <Badge
                            variant={job.match_score >= 70 ? "default" : "secondary"}
                            className="font-mono text-sm"
                          >
                            {job.match_score}%
                          </Badge>
                        </div>
                        <Progress value={job.match_score} className="h-1.5 w-32" />
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-3 text-xs">
                    {/* Enriched Company KB Badges if matched */}
                    {(job.company_rating || job.company_salary_idr || job.salary_info) && (
                      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/40 px-3 py-2">
                        {job.company_rating && (
                          <Badge variant="outline" className="gap-1">
                            <Star className="size-3 text-amber-500" />
                            {job.company_rating}/5 ({job.company_verdict})
                          </Badge>
                        )}
                        {(job.salary_info || job.company_salary_idr) && (
                          <span className="inline-flex items-center gap-1 font-medium text-emerald-500">
                            <Banknote className="size-3.5" />
                            {job.salary_info || `Est. ${job.company_salary_idr}`}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Company About */}
                    {job.company_about && (
                      <p className="text-muted-foreground">
                        <span className="font-semibold text-foreground">Tentang / Ringkasan: </span>
                        {job.company_about}
                      </p>
                    )}

                    {/* Matched vs Missing Skills */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      {job.matched_skills.map((s) => (
                        <Badge key={s} variant="default" className="text-[11px]">
                          ✓ {s}
                        </Badge>
                      ))}
                      {job.missing_skills.slice(0, 5).map((s) => (
                        <Badge key={s} variant="outline" className="text-[11px] text-muted-foreground">
                          Gap: {s}
                        </Badge>
                      ))}
                    </div>

                    {/* Expandable Full JD */}
                    {job.description && (
                      <div>
                        <button
                          type="button"
                          onClick={() => setExpandedId(isExpanded ? null : job.job_id)}
                          className="text-xs font-medium text-primary underline"
                        >
                          {isExpanded ? "Sembunyikan Job Description" : "Lihat Job Description Lengkap"}
                        </button>
                        {isExpanded && (
                          <div className="mt-2 max-h-64 overflow-y-auto rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground whitespace-pre-wrap">
                            {job.description}
                          </div>
                        )}
                      </div>
                    )}

                    <Separator />

                    {/* Actions */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-2">
                        {job.job_url && (
                          <Button asChild size="sm" variant="outline" className="h-8 gap-1.5 text-xs">
                            <a href={job.job_url} target="_blank" rel="noreferrer">
                              <ExternalLink className="size-3.5" />
                              Buka Link Post
                            </a>
                          </Button>
                        )}
                        <Button asChild size="sm" className="h-8 gap-1.5 text-xs">
                          <Link
                            href={`/dashboard/cv-studio?company=${encodeURIComponent(job.company)}&role=${encodeURIComponent(job.title)}&jobUrl=${encodeURIComponent(job.job_url)}`}
                          >
                            <Sparkles className="size-3.5" />
                            Buat CV Khusus Job Ini
                          </Link>
                        </Button>
                      </div>

                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleSaveJob(job)}
                        className="h-8 gap-1.5 text-xs"
                      >
                        <BookmarkPlus className="size-3.5" />
                        Simpan ke Tracker
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </TabsContent>

        {/* Tab 2: HR & Recruiter Posts Radar */}
        <TabsContent value="hr" className="mt-4 space-y-4">
          <Alert>
            <Users className="size-4" />
            <AlertTitle>Radar Postingan HR Indonesia &amp; Global Remote</AlertTitle>
            <AlertDescription className="text-xs">
              Postingan feed pribadi HR di LinkedIn memerlukan sesi login browser kamu sendiri (tidak bisa di-scrape tanpa login). Klik shortcut Boolean search di bawah — query-nya otomatis dibuat dari skill CV kamu! Kalau ketemu postingan HR yang menarik, tinggal copy teks/linknya ke <strong>CV Studio</strong> atau <strong>AI Copilot</strong>.
            </AlertDescription>
          </Alert>

          <div className="grid gap-4 md:grid-cols-2">
            {(data?.hr_post_shortcuts ?? []).map((item) => (
              <Card key={item.title}>
                <CardHeader className="pb-2">
                  <Badge variant="secondary" className="w-fit text-[11px]">
                    {item.platform}
                  </Badge>
                  <CardTitle className="mt-1 text-base">{item.title}</CardTitle>
                  <CardDescription className="text-xs">{item.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button asChild variant="outline" size="sm" className="gap-1.5">
                    <a href={item.search_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="size-3.5" />
                      Buka Pencarian HR Langsung
                    </a>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
