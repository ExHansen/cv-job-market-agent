"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";

import {
  Bot,
  Database,
  Loader2,
  RotateCcw,
  Send,
  Sparkles,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { type InterviewTurn, streamCopilotChat } from "@/lib/cv-api";

interface CopilotMessage extends InterviewTurn {
  sources?: string[];
}

const QUICK_PROMPTS = [
  "Bagaimana cara kerja seluruh sistem CareerOS ini, dan fitur apa saja yang bisa saya pakai?",
  "Bandingkan Shopee Indonesia vs Bank Jago vs Kredivo: mana yang bagus, keluh kesahnya apa, dan estimasi gaji IDR-nya?",
  "Dari semua perusahaan di Company Knowledge DB, mana 3 perusahaan yang paling cocok dengan profil & proyek saya?",
  "FIT HUB itu perusahaan seperti apa, cocok nggak dengan skill saya, dan langkah apa yang harus saya lakukan di aplikasi ini?",
  "Skill Data Engineer apa yang paling dicari market sekarang tapi masih jadi gap di CV saya?",
];

export default function AssistantCopilotPage() {
  const [language, setLanguage] = useState<"id" | "en">("id");
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  async function sendQuestion(questionText: string) {
    const clean = questionText.trim();
    if (!clean || streaming) return;

    const history: CopilotMessage[] = [...messages, { role: "user", content: clean }];
    const apiTurns: InterviewTurn[] = history.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setDraft("");
    setMessages([...history, { role: "assistant", content: "", sources: [] }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamCopilotChat(
        { language, messages: apiTurns },
        {
          onContext: (sources) => {
            setMessages((prev) => {
              if (prev.length === 0) return prev;
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], sources };
              return next;
            });
          },
          onToken: (token) => {
            setMessages((prev) => {
              if (prev.length === 0) return prev;
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, content: last.content + token };
              return next;
            });
          },
        },
        controller.signal
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        toast.error(err instanceof Error ? err.message : "Gagal terhubung ke Copilot");
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
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
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="gap-1.5">
              <Bot className="size-3.5" />
              CareerOS AI Copilot (System + DuckDB RAG)
            </Badge>
            <Badge variant="outline">
              Tahu Sistem • Master Profile • Company KB (IDR &amp; Review) • Market Radar
            </Badge>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            CareerOS AI Copilot Chatbot
          </h1>
          <p className="text-muted-foreground text-sm">
            Tanya apa saja: cara pakai sistem, review perusahaan (positif, keluh kesah &amp; gaji IDR), kecocokan CV, atau tempel langsung link lowongan LinkedIn!
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Select value={language} onValueChange={(v) => setLanguage(v as "id" | "en")}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="id">Bahasa Indonesia</SelectItem>
              <SelectItem value="en">English</SelectItem>
            </SelectContent>
          </Select>
          <Button asChild variant="outline" size="sm" className="gap-1.5">
            <Link href="/dashboard/company-database">
              <Database className="size-3.5" />
              Lihat Company DB
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={handleReset} className="gap-1.5">
            <RotateCcw className="size-3.5" />
            Reset
          </Button>
        </div>
      </div>

      {/* Chat Card */}
      <Card className="flex min-h-[540px] flex-col justify-between">
        <CardHeader className="border-b pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Sparkles className="size-4 text-primary" />
            Asisten Pribadi CareerOS (Local Ollama Streaming)
          </CardTitle>
          <CardDescription>
            Setiap jawaban otomatis mengambil konteks dari DuckDB (`company_profiles`, `market_snapshots`, `job_applications`) dan `master_profile.yaml`.
          </CardDescription>
        </CardHeader>

        <CardContent className="flex max-h-[560px] flex-1 flex-col gap-4 overflow-y-auto py-5">
          {messages.length === 0 ? (
            <div className="m-auto flex max-w-2xl flex-col items-center gap-4 text-center">
              <Bot className="size-10 text-primary/70" />
              <div className="space-y-1">
                <h2 className="font-semibold text-base">
                  Halo! Mau riset perusahaan, cek gaji IDR, atau tanya cara pakai CareerOS?
                </h2>
                <p className="text-xs text-muted-foreground">
                  Pilih salah satu contoh pertanyaan di bawah atau ketik pertanyaan bebas (boleh paste link LinkedIn langsung juga!).
                </p>
              </div>
              <div className="grid w-full gap-2 pt-2 sm:grid-cols-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => sendQuestion(prompt)}
                    className="rounded-lg border bg-card p-3 text-left text-xs leading-relaxed transition hover:border-primary/50 hover:bg-accent/40"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
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

                <div className="flex max-w-[84%] flex-col gap-1.5">
                  {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {msg.sources.map((src) => (
                        <Badge
                          key={src}
                          variant="outline"
                          className="px-1.5 py-0 text-[10px] font-normal text-muted-foreground"
                        >
                          ✓ {src}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <div
                    className={`rounded-xl border px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
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
                        Membaca DuckDB &amp; menyusun jawaban...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </CardContent>

        {/* Input Composer */}
        <div className="flex items-end gap-2 border-t p-4">
          <Textarea
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendQuestion(draft);
              }
            }}
            placeholder="Tanya soal perusahaan (Bank Jago, Shopee, Thales...), gaji IDR, keluh kesah, atau cara pakai fitur CareerOS..."
            disabled={streaming}
          />
          {streaming ? (
            <Button variant="destructive" onClick={handleStop} className="shrink-0 gap-1.5">
              <Square className="size-3.5" />
              Stop
            </Button>
          ) : (
            <Button
              onClick={() => sendQuestion(draft)}
              disabled={!draft.trim()}
              className="shrink-0 gap-1.5"
            >
              <Send className="size-3.5" />
              Kirim
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
