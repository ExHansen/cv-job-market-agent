"use client";

import { CheckCircle2, Circle, Clock, Loader2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export interface ProgressStep {
  id: string;
  label: string;
  detail?: string;
}

interface AgentProgressPanelProps {
  title: string;
  steps: ProgressStep[];
  activeStageId: string;
  percent: number;
  statusMessage: string;
  elapsedSec: number;
  etaHint: string;
  onCancel?: () => void;
}

function formatDuration(sec: number): string {
  const total = Math.max(0, Math.floor(sec));
  const mins = Math.floor(total / 60);
  const rem = total % 60;
  return `${String(mins).padStart(2, "0")}:${String(rem).padStart(2, "0")}`;
}

export function AgentProgressPanel({
  title,
  steps,
  activeStageId,
  percent,
  statusMessage,
  elapsedSec,
  etaHint,
  onCancel,
}: AgentProgressPanelProps) {
  const activeIdx = steps.findIndex((s) => s.id === activeStageId);

  return (
    <Card className="border-primary/30 bg-primary/[0.02]">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin text-primary" />
            {title}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="gap-1 font-mono text-xs">
              <Clock className="size-3" />
              {formatDuration(elapsedSec)}
            </Badge>
            <Badge variant="outline" className="font-mono text-xs">
              {Math.min(100, Math.max(0, Math.round(percent)))}%
            </Badge>
            {onCancel && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onCancel}
                className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-destructive"
              >
                <X className="size-3.5" />
                Batalkan
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Progress value={percent} className="h-2.5" />
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{statusMessage}</span>
            <span className="font-medium">{etaHint}</span>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, idx) => {
            const isDone = activeIdx > idx || percent >= 100;
            const isCurrent = activeIdx === idx && percent < 100;
            return (
              <div
                key={step.id}
                className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs transition-colors ${
                  isCurrent
                    ? "border-primary/50 bg-primary/5 text-foreground"
                    : isDone
                      ? "border-emerald-500/30 bg-emerald-500/5 text-foreground"
                      : "border-border/60 text-muted-foreground"
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-500" />
                ) : isCurrent ? (
                  <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-primary" />
                ) : (
                  <Circle className="mt-0.5 size-3.5 shrink-0 opacity-40" />
                )}
                <div className="min-w-0">
                  <div className="font-medium">{step.label}</div>
                  {step.detail && (
                    <div className="truncate text-[11px] text-muted-foreground">
                      {step.detail}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
