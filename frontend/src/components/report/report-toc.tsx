"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen } from "lucide-react";

import { REPORT_SECTIONS } from "@/components/report/sections";
import { cn } from "@/lib/utils";

export function ReportToc() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [readProgress, setReadProgress] = useState(0);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const sectionIds = REPORT_SECTIONS.map((s) => s.id);

    // Track which section is in view.
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 },
    );

    sectionIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observerRef.current?.observe(el);
    });

    // Track overall scroll progress through the report.
    function onScroll() {
      const article = document.querySelector("article");
      if (!article) return;
      const { top, height } = article.getBoundingClientRect();
      const viewH = window.innerHeight;
      const scrolled = Math.max(0, viewH - top);
      setReadProgress(Math.min(1, scrolled / height));
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    return () => {
      observerRef.current?.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  const activeIndex = REPORT_SECTIONS.findIndex((s) => s.id === activeId);

  return (
    <nav
      aria-label="Report sections"
      className="sticky top-20 hidden lg:block self-start"
    >
      {/* Card container */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
          <BookOpen className="size-3.5 text-primary shrink-0" />
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            On this page
          </p>
        </div>

        {/* Progress bar */}
        <div className="h-0.5 bg-muted">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${readProgress * 100}%` }}
          />
        </div>

        {/* Section links */}
        <ul className="py-2">
          {REPORT_SECTIONS.map((s, i) => {
            const isActive = s.id === activeId;
            const isPast = activeIndex > i;
            return (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-1.5 text-xs transition-all duration-150 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    isActive
                      ? "bg-primary/8 text-primary font-semibold"
                      : isPast
                        ? "text-muted-foreground/60 hover:text-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
                  )}
                  onClick={(e) => {
                    e.preventDefault();
                    document
                      .getElementById(s.id)
                      ?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                >
                  {/* Step dot */}
                  <span
                    className={cn(
                      "flex size-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : isPast
                          ? "bg-primary/20 text-primary/60"
                          : "bg-muted text-muted-foreground",
                    )}
                  >
                    {isPast ? "✓" : i + 1}
                  </span>
                  <span className="leading-tight">{s.title}</span>

                  {/* Active indicator bar */}
                  {isActive && (
                    <span className="ml-auto block h-4 w-0.5 rounded-full bg-primary" />
                  )}
                </a>
              </li>
            );
          })}
        </ul>

        {/* Footer: progress label */}
        <div className="border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
          {activeIndex >= 0 ? (
            <span>
              {activeIndex + 1} / {REPORT_SECTIONS.length} sections
            </span>
          ) : (
            <span>Scroll to navigate</span>
          )}
        </div>
      </div>
    </nav>
  );
}
