/* eslint-disable @next/next/no-img-element */
"use client";

import { useState } from "react";
import { ExternalLink, Globe } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { sourceAnchorId } from "@/lib/citations";
import { faviconUrl, hostOf } from "@/lib/url";
import type { ReportSource } from "@/types/report";

export function SourceCard({ source }: { source: ReportSource }) {
  const [imgError, setImgError] = useState(false);
  const favicon = faviconUrl(source.url);
  const host = hostOf(source.url);

  return (
    <a
      id={sourceAnchorId(source.url)}
      href={source.url}
      target="_blank"
      rel="noreferrer"
      className="group flex scroll-mt-24 items-start gap-3 rounded-lg border p-3 transition-[colors,box-shadow] hover:bg-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center overflow-hidden rounded">
        {favicon && !imgError ? (
          <img
            src={favicon}
            alt=""
            width={16}
            height={16}
            className="size-4"
            onError={() => setImgError(true)}
          />
        ) : (
          <Globe className="text-muted-foreground size-4" aria-hidden />
        )}
      </span>

      <div className="flex min-w-0 flex-col gap-1">
        <span className="flex items-center gap-1 text-sm font-medium">
          <span className="truncate">{source.title || host}</span>
          <ExternalLink
            className="text-muted-foreground size-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
            aria-hidden
          />
        </span>
        <span className="text-muted-foreground truncate text-xs">
          <span className="text-foreground/70 font-medium">{host}</span>
        </span>
        {source.usedIn.length > 0 && (
          <span className="mt-1 flex flex-wrap gap-1">
            {source.usedIn.map((section) => (
              <Badge key={section} variant="outline" className="text-[10px]">
                {section}
              </Badge>
            ))}
          </span>
        )}
      </div>
    </a>
  );
}
