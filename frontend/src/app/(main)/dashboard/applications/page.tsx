"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import {
  Briefcase,
  Download,
  ExternalLink,
  Kanban,
  MessageSquare,
  Plus,
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
import {
  API_URL,
  type ApplicationStatus,
  createApplication,
  deleteApplication,
  type JobApplication,
  listApplications,
  updateApplication,
} from "@/lib/cv-api";

const COLUMNS: Array<{ id: ApplicationStatus; label: string; tone: string }> = [
  { id: "wishlist", label: "Wishlist", tone: "border-slate-500/30" },
  { id: "applied", label: "Applied", tone: "border-sky-500/30" },
  { id: "interview", label: "Interview", tone: "border-amber-500/30" },
  { id: "offer", label: "Offer", tone: "border-emerald-500/30" },
  { id: "rejected", label: "Rejected", tone: "border-rose-500/30" },
];

export default function ApplicationsPage() {
  const [apps, setApps] = useState<JobApplication[]>([]);
  const [loading, setLoading] = useState(true);

  const [company, setCompany] = useState("");
  const [role, setRole] = useState("Data Engineer");
  const [status, setStatus] = useState<ApplicationStatus>("wishlist");
  const [jobUrl, setJobUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  async function reload() {
    try {
      const data = await listApplications();
      setApps(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal memuat data lamaran");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleAdd() {
    if (!company.trim() || !role.trim()) {
      toast.error("Isi nama perusahaan dan posisi terlebih dahulu.");
      return;
    }
    setSaving(true);
    try {
      const created = await createApplication({
        company,
        role,
        status,
        job_url: jobUrl,
        notes,
      });
      setApps((prev) => [created, ...prev]);
      setCompany("");
      setJobUrl("");
      setNotes("");
      toast.success(`${created.company} ditambahkan ke Application Tracker!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan");
    } finally {
      setSaving(false);
    }
  }

  async function handleMoveStatus(appId: string, nextStatus: ApplicationStatus) {
    try {
      const updated = await updateApplication(appId, { status: nextStatus });
      setApps((prev) => prev.map((a) => (a.id === appId ? updated : a)));
      toast.success(`Status dipindahkan ke ${nextStatus.toUpperCase()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal memperbarui status");
    }
  }

  async function handleDelete(appId: string) {
    try {
      await deleteApplication(appId);
      setApps((prev) => prev.filter((a) => a.id !== appId));
      toast.info("Lamaran dihapus.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menghapus");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary" className="gap-1.5">
            <Kanban className="size-3.5" />
            Persistent DuckDB Job Tracker
          </Badge>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Application Tracker
          </h1>
          <p className="text-muted-foreground text-sm">
            Pantau seluruh lamaran kerja kamu dari Wishlist hingga Offer — tersimpan permanen di DuckDB.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">Total: {apps.length}</Badge>
          <Badge variant="outline">
            Interview: {apps.filter((a) => a.status === "interview").length}
          </Badge>
          <Badge variant="outline">
            Offer: {apps.filter((a) => a.status === "offer").length}
          </Badge>
        </div>
      </div>

      {/* Quick Add Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Plus className="size-4 text-primary" />
            Tambah Lamaran Baru
          </CardTitle>
          <CardDescription>
            Kamu juga bisa menyimpan langsung lewat tombol &ldquo;Simpan ke Tracker&rdquo; dari halaman Company Deep-Dive atau CV Studio.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="space-y-1">
              <Label htmlFor="appCompany" className="text-xs">Perusahaan</Label>
              <Input
                id="appCompany"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="FIT HUB, Bank Jago..."
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="appRole" className="text-xs">Role</Label>
              <Input
                id="appRole"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Data Engineer"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="appStatus" className="text-xs">Status</Label>
              <Select
                value={status}
                onValueChange={(v) => setStatus(v as ApplicationStatus)}
              >
                <SelectTrigger id="appStatus" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COLUMNS.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="appUrl" className="text-xs">Link Lowongan (Opsional)</Label>
              <Input
                id="appUrl"
                value={jobUrl}
                onChange={(e) => setJobUrl(e.target.value)}
                placeholder="https://linkedin.com/jobs/..."
              />
            </div>
            <div className="flex items-end">
              <Button onClick={handleAdd} disabled={saving} className="w-full gap-1.5">
                <Plus className="size-4" />
                {saving ? "Menyimpan..." : "Tambah"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Kanban Columns */}
      {loading ? (
        <div className="text-sm text-muted-foreground">Memuat data dari DuckDB...</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {COLUMNS.map((col) => {
            const colItems = apps.filter((a) => a.status === col.id);
            return (
              <Card key={col.id} className={`flex flex-col ${col.tone}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">{col.label}</CardTitle>
                    <Badge variant="secondary">{colItems.length}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3">
                  {colItems.length === 0 ? (
                    <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                      Belum ada lamaran
                    </div>
                  ) : (
                    colItems.map((app) => (
                      <div
                        key={app.id}
                        className="flex flex-col gap-2.5 rounded-lg border bg-card p-3 shadow-xs"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate font-semibold text-sm">
                              {app.company}
                            </div>
                            <div className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Briefcase className="size-3 shrink-0" />
                              <span className="truncate">{app.role}</span>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-6 shrink-0 text-muted-foreground hover:text-destructive"
                            onClick={() => handleDelete(app.id)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>

                        {app.ats_score !== null && (
                          <Badge variant="outline" className="w-fit font-mono text-[11px]">
                            ATS Score: {app.ats_score}%
                          </Badge>
                        )}

                        {app.notes && (
                          <p className="line-clamp-2 text-xs text-muted-foreground">
                            {app.notes}
                          </p>
                        )}

                        <Select
                          value={app.status}
                          onValueChange={(v) =>
                            handleMoveStatus(app.id, v as ApplicationStatus)
                          }
                        >
                          <SelectTrigger className="h-7 w-full text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {COLUMNS.map((c) => (
                              <SelectItem key={c.id} value={c.id}>
                                Pindah ke: {c.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>

                        <div className="flex flex-wrap items-center gap-1.5 pt-1">
                          {app.job_url && (
                            <Button asChild size="sm" variant="outline" className="h-7 px-2 text-[11px]">
                              <a href={app.job_url} target="_blank" rel="noreferrer">
                                <ExternalLink className="mr-1 size-3" />
                                JD
                              </a>
                            </Button>
                          )}
                          {app.pdf_filename && (
                            <Button asChild size="sm" variant="outline" className="h-7 px-2 text-[11px]">
                              <a
                                href={`${API_URL}/api/cv/download/${encodeURIComponent(app.pdf_filename)}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <Download className="mr-1 size-3" />
                                PDF
                              </a>
                            </Button>
                          )}
                          <Button asChild size="sm" variant="secondary" className="h-7 px-2 text-[11px]">
                            <Link
                              href={`/dashboard/interview-prep?company=${encodeURIComponent(app.company)}&role=${encodeURIComponent(app.role)}`}
                            >
                              <MessageSquare className="mr-1 size-3" />
                              Latihan
                            </Link>
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
