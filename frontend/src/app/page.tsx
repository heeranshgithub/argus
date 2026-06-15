import { ArrowRight, MoveDown } from "lucide-react";
import Link from "next/link";

import { HealthCard } from "@/components/health-card";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="relative flex-1 overflow-hidden">
      {/* Oversized brand mark, echoing the slash in the wordmark. Decorative. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -left-24 top-10 -z-10 select-none font-display text-[28rem] font-black leading-none text-primary/[0.06] sm:-left-16 dark:text-primary/[0.08]"
      >
        /
      </div>

      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-6 py-20 lg:grid-cols-[1.15fr_0.85fr] lg:py-28">
        {/* Left: the pitch. */}
        <div className="flex flex-col items-start gap-7">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-accent/60 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-widest text-accent-foreground">
            <span className="block h-3 w-1.5 -skew-x-12 bg-primary" />
            AI research copilot for B2B meetings
          </span>

          <h1 className="font-display text-5xl font-extrabold leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
            Walk in already
            <br />
            <span className="text-primary">knowing everything.</span>
          </h1>

          <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
            Behind every meeting is a stack of prep nobody has time to do well:
            who the company really is, what they just shipped, who decides, and
            the one angle that lands. Argus runs all of it — and hands you a
            structured briefing before the call.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button asChild size="lg" className="group">
              <Link href="/sessions/new">
                Start a research session
                <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
              </Link>
            </Button>
            <Button asChild variant="ghost" size="lg" className="text-primary">
              <Link href="/sessions">
                Browse sessions
                <MoveDown className="size-4" />
              </Link>
            </Button>
          </div>
        </div>

        {/* Right: a live "system status" panel — the health card, reframed. */}
        <div className="relative w-full">
          <div
            aria-hidden
            className="absolute -right-3 -top-3 -z-10 h-full w-full -skew-x-6 rounded-2xl bg-primary/10"
          />
          <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card/80 p-6 shadow-sm backdrop-blur">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-sm font-bold uppercase tracking-widest text-muted-foreground">
                System status
              </h2>
              <span className="size-2 animate-pulse rounded-full bg-primary" />
            </div>
            <HealthCard />
          </div>
        </div>
      </div>
    </main>
  );
}
