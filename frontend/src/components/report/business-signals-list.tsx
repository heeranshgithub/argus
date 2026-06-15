"use client";

import { ChevronDown, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { hostOf } from "@/lib/url";
import type { BusinessSignal } from "@/types/report";

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <Badge
      variant="secondary"
      className={cn(
        "tabular-nums",
        pct >= 70
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          : pct >= 40
            ? "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
            : "bg-muted text-muted-foreground",
      )}
    >
      {pct}% confidence
    </Badge>
  );
}

export function BusinessSignalsList({ signals }: { signals: BusinessSignal[] }) {
  if (!signals.length) {
    return <p className="text-muted-foreground text-sm">No signals detected.</p>;
  }

  const groups = new Map<string, BusinessSignal[]>();
  for (const s of signals) {
    const key = s.category || "Other";
    groups.set(key, [...(groups.get(key) ?? []), s]);
  }

  return (
    <div className="flex flex-col gap-3">
      {[...groups.entries()].map(([category, items]) => (
        <SignalGroup key={category} category={category} items={items} />
      ))}
    </div>
  );
}

function SignalGroup({
  category,
  items,
}: {
  category: string;
  items: BusinessSignal[];
}) {
  return (
    <Collapsible defaultOpen className="rounded-lg border">
      <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
        <span className="flex items-center gap-2 font-medium">
          {category}
          <Badge variant="outline" className="text-xs">
            {items.length}
          </Badge>
        </span>
        <ChevronDown
          className="size-4 transition-transform group-data-[state=open]:rotate-180"
          aria-hidden
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 border-t px-4 py-3">
        {items.map((s, i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <ConfidenceBadge value={s.confidence} />
            <p className="text-sm">{s.summary}</p>
            {s.evidenceUrls.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {s.evidenceUrls.map((url) => (
                  <a
                    key={url}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs hover:underline"
                  >
                    {hostOf(url)}
                    <ExternalLink className="size-3" aria-hidden />
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
