"use client";

import { type ChangeEvent, useEffect, useState } from "react";

import { Award, Briefcase, FileUp, FolderGit2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  fetchDefaultProfile,
  type MasterProfile,
  parseUploadedCv,
} from "@/lib/cv-api";

export default function MasterProfilePage() {
  const [profile, setProfile] = useState<MasterProfile | null>(null);
  const [parsedPreview, setParsedPreview] = useState("");
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchDefaultProfile()
      .then(setProfile)
      .catch((err) => toast.error(err instanceof Error ? err.message : "Failed to load profile"));
  }, []);

  async function handleFileUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await parseUploadedCv(file);
      setParsedPreview(res.markdown);
      toast.success(`Parsed ${res.filename} cleanly!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Parse failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <ShieldCheck className="size-6 text-emerald-500" />
            Master Career Profile (Single Source of Truth)
          </h1>
          <p className="text-muted-foreground text-sm">
            Seluruh fakta pengalaman, proyek, dan sertifikasi terverifikasi dari `data/master_profile.yaml`.
          </p>
        </div>

        <label className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          <FileUp className="size-4" />
          <span>{uploading ? "Parsing..." : "Test Parse .PDF / .DOCX"}</span>
          <Input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            className="hidden"
          />
        </label>
      </div>

      {parsedPreview && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Extracted CV Markdown Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
              {parsedPreview}
            </pre>
          </CardContent>
        </Card>
      )}

      {profile && (
        <Tabs defaultValue="experience">
          <TabsList>
            <TabsTrigger value="experience">Experience ({profile.experiences.length})</TabsTrigger>
            <TabsTrigger value="projects">Projects ({profile.projects.length})</TabsTrigger>
            <TabsTrigger value="skills">Skills &amp; Certifications</TabsTrigger>
          </TabsList>

          <TabsContent value="experience" className="mt-4 space-y-4">
            {profile.experiences.map((exp) => (
              <Card key={exp.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Briefcase className="size-4 text-primary" />
                      {exp.role} — {exp.company}
                    </CardTitle>
                    <Badge variant="outline">
                      {exp.start_date} – {exp.end_date}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {exp.bullets.map((b) => (
                    <div key={b.id} className="rounded-md border p-3">
                      <p>{b.raw_fact}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {b.tools_used.map((t) => (
                          <Badge key={t} variant="secondary">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="projects" className="mt-4 grid gap-4 md:grid-cols-2">
            {profile.projects.map((proj) => (
              <Card key={proj.id}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FolderGit2 className="size-4 text-primary" />
                    {proj.name}
                  </CardTitle>
                  <CardDescription>{proj.period}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div className="flex flex-wrap gap-1">
                    {proj.domain_tags.map((tag) => (
                      <Badge key={tag} variant="outline">
                        #{tag}
                      </Badge>
                    ))}
                  </div>
                  <Separator />
                  <ul className="list-disc space-y-1.5 pl-4 text-muted-foreground">
                    {proj.bullets.map((b) => (
                      <li key={b.id}>{b.raw_fact}</li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="skills" className="mt-4 grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Verified Technical Skills</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(profile.skills_verified).map(([group, skills]) => (
                  <div key={group} className="space-y-1.5">
                    <div className="text-xs font-medium capitalize text-muted-foreground">
                      {group.replaceAll("_", " ")}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((s) => (
                        <Badge key={s} variant="secondary">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Award className="size-4 text-primary" />
                  Certifications &amp; Honors
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {profile.certifications.map((c) => (
                  <div key={c.name} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="font-medium">{c.name}</div>
                      <div className="text-xs text-muted-foreground">{c.issuer}</div>
                    </div>
                    <Badge variant="outline">{c.date}</Badge>
                  </div>
                ))}
                {profile.honors.map((h) => (
                  <div key={h.title} className="rounded-md bg-muted/40 p-2.5 text-xs">
                    <div className="font-medium">
                      {h.title} ({h.date})
                    </div>
                    <div className="text-muted-foreground">{h.summary}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
