"use client";

import { Link2 } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

/**
 * Generic report section: an anchored heading with a copy-link affordance and a
 * consistent content slot. `id` doubles as the in-page anchor used by the TOC.
 */
export function ReportSection({
  id,
  title,
  children,
  className,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  function copyLink() {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}${window.location.pathname}${window.location.search}#${id}`;
    void navigator.clipboard?.writeText(url).then(
      () => toast.success("Section link copied"),
      () => toast.error("Couldn't copy link"),
    );
  }

  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className={cn("scroll-mt-24 border-b pb-8 last:border-b-0", className)}
    >
      <div className="group mb-3 flex items-center gap-2">
        <h2 id={`${id}-heading`} className="text-lg font-semibold tracking-tight">
          {title}
        </h2>
        <button
          type="button"
          onClick={copyLink}
          aria-label={`Copy link to ${title}`}
          className="text-muted-foreground hover:text-foreground rounded p-1 opacity-0 transition-opacity focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 group-hover:opacity-100 print:hidden"
        >
          <Link2 className="size-4" aria-hidden />
        </button>
      </div>
      {children}
    </section>
  );
}

/** A simple bulleted list with an empty fallback. */
export function BulletList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="text-muted-foreground text-sm">None identified.</p>;
  }
  return (
    <ul className="ml-5 list-disc space-y-1.5 text-sm marker:text-muted-foreground">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}
