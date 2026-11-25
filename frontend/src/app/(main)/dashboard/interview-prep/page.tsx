"use client";

import { useEffect, useRef, useState } from "react";

import {
  Bot,
  Loader2,
  MessageSquare,
  Play,
  RotateCcw,
  Send,
  Square,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { InlineMarkdown } from "@/components/inline-markdown";
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
import { Textarea } from "@/components/ui/textarea";
import {
  type InterviewMode,
  type InterviewTurn,
  streamInterviewChat,
} from "@/lib/cv-api";

export default function InterviewPrepPage() {
  const [companyName, setCompanyName] = useState("FIT HUB");
  const [targetRole, setTargetRole] = useState("Data Engineer");
  const [mode, setMode] = useState<InterviewMode>("technical");
  const [language, setLanguage] = useState<"id" | "en">("id");

  const [messages, setMessages] = useState<InterviewTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const qCompany = params.get("company");
    const qRole = params.get("role");
    if (qCompany) setCompanyName(qCompany);
    if (qRole) setTargetRole(qRole);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  async function runStream(history: InterviewTurn[]) {
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);

    // Append placeholder assistant turn that fills in token-by-token
    setMessages([...history, { role: "assistant", content: "" }]);

    try {
      await streamInterviewChat(
        {
          company_name: companyName || "Perusahaan Target",
          target_role: targetRole,
          mode,
          language,
          messages: history,
        },
        (token) => {
          setMessages((prev) => {
            if (prev.length === 0) return prev;
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = {
              ...last,
              content: last.content + token,
            };
            return updated;
          });
        },
        controller.signal
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        toast.error(err instanceof Error ? err.message : "Gagal menghubungi Ollama");
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function handleStartSession() {
    setMessages([]);
    runStream([]);
  }

  function handleSend() {
    const clean = draft.trim();
    if (!clean || streaming) return;
    const nextHistory: InterviewTurn[] = [...messages, { role: "user", content: clean }];
    setDraft("");
    runStream(nextHistory);
  }

  function handleStop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  function handleReset() {
    abortRef.current?.abort();
    setStreaming(false);
    setMessages([]);
    setDraft("");
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary" className="gap-1.5">
            <MessageSquare className="size-3.5" />
            Local Ollama Live Streaming Mock Interviewer
          </Badge>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Interview Prep Chat
          </h1>
          <p className="text-muted-foreground text-sm">
            Simulasi interview teknis, behavioral, &amp; system design berbasis pengalaman nyata di Master Profile kamu dengan penilaian langsung per jawaban.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleReset} className="gap-1.5">
            <RotateCcw className="size-3.5" />
            Reset Sesi
          </Button>
          <Button size="sm" onClick={handleStartSession} disabled={streaming} className="gap-1.5">
            <Play className="size-3.5" />
            Mulai Simulasi Interview
          </Button>
        </div>
      </div>

      {/* Session Settings */}
      <Card>
        <CardContent className="grid gap-3 pt-6 md:grid-cols-4">
          <div className="space-y-1">
            <Label htmlFor="ivCompany" className="text-xs">Perusahaan Target</Label>
            <Input
              id="ivCompany"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="FIT HUB, Bank Jago, Thales..."
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ivRole" className="text-xs">Role Target</Label>
            <Input
              id="ivRole"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              placeholder="Data Engineer"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ivMode" className="text-xs">Mode Interview</Label>
            <Select value={mode} onValueChange={(v) => setMode(v as InterviewMode)}>
              <SelectTrigger id="ivMode" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="technical">Technical Deep-Dive</SelectItem>
                <SelectItem value="system_design">Data System Design</SelectItem>
                <SelectItem value="behavioral">Behavioral (STAR)</SelectItem>
                <SelectItem value="hr">HR &amp; Culture Fit</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="ivLang" className="text-xs">Bahasa</Label>
            <Select value={language} onValueChange={(v) => setLanguage(v as "id" | "en")}>
              <SelectTrigger id="ivLang" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="id">Bahasa Indonesia</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Chat Transcript */}
      <Card className="flex min-h-[460px] flex-col justify-between">
        <CardHeader className="border-b pb-3">
          <CardTitle className="text-sm">
            Interviewer: Senior Hiring Manager — {companyName || "Target Company"} ({mode.replace("_", " ")})
          </CardTitle>
          <CardDescription>
            Jawabanmu akan dinilai 1–10 beserta saran perbaikan + pertanyaan lanjutan (real-time token streaming).
          </CardDescription>
        </CardHeader>

        <CardContent className="flex flex-1 flex-col gap-4 overflow-y-auto py-4 max-h-[520px]">
          {messages.length === 0 ? (
            <div className="m-auto max-w-md space-y-2 text-center text-sm text-muted-foreground">
              <Bot className="mx-auto size-8 opacity-60" />
              <p>
                Klik <strong>&ldquo;Mulai Simulasi Interview&rdquo;</strong> di atas agar AI Hiring Manager memulai pertanyaan pertama berdasarkan proyek &amp; pengalaman asli di CV kamu.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-3 ${
                  msg.role === "user" ? "flex-row-reverse" : ""
                }`}
              >
                <div
                  className={`flex size-8 shrink-0 items-center justify-center rounded-full border ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground"
                  }`}
                >
                  {msg.role === "user" ? (
                    <User className="size-4" />
                  ) : (
                    <Bot className="size-4" />
                  )}
                </div>
                <div
                  className={`max-w-[82%] space-y-1.5 rounded-xl border px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/40"
                  }`}
                >
                  {msg.content ? (
                    msg.role === "assistant" ? (
                      <InlineMarkdown text={msg.content} />
                    ) : (
                      msg.content
                    )
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Loader2 className="size-3.5 animate-spin" />
                      Mengetik...
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </CardContent>

        {/* Composer */}
        <div className="flex items-end gap-2 border-t p-4">
          <Textarea
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ketik jawaban interview kamu di sini (Enter untuk kirim, Shift+Enter baris baru)..."
            disabled={streaming}
          />
          {streaming ? (
            <Button variant="destructive" onClick={handleStop} className="shrink-0 gap-1.5">
              <Square className="size-3.5" />
              Stop
            </Button>
          ) : (
            <Button onClick={handleSend} disabled={!draft.trim()} className="shrink-0 gap-1.5">
              <Send className="size-3.5" />
              Kirim
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
