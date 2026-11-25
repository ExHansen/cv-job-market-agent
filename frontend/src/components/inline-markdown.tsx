"use client";

import type { ReactNode } from "react";

const TOKEN_RE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;

/**
 * Lightweight inline Markdown renderer for LLM strings (**bold**, *italic*, `code`).
 */
export function InlineMarkdown({ text }: { text: string }) {
  const parts = (text || "").split(TOKEN_RE);
  const nodes: ReactNode[] = parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={idx} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code
          key={idx}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return (
        <em key={idx} className="italic">
          {part.slice(1, -1)}
        </em>
      );
    }
    return <span key={idx}>{part}</span>;
  });

  return <>{nodes}</>;
}
