import {
  ArrowLeft,
  FileText,
  Newspaper,
  Search,
  Users,
} from "lucide-react";
import Link from "next/link";

import { SessionCreateForm } from "@/components/sessions/session-create-form";

// What the research workflow does once a brief is submitted — gives the page
// substance and sets expectations before the run starts.
const STEPS = [
  {
    icon: Search,
    title: "Identify the company",
    body: "Entity, market, size, and what they actually sell.",
  },
  {
    icon: Users,
    title: "Map the people",
    body: "Who decides, who signs, and who you'll be in the room with.",
  },
  {
    icon: Newspaper,
    title: "Surface recent signals",
    body: "Funding, launches, hiring, and news worth mentioning.",
  },
  {
    icon: FileText,
    title: "Draft the briefing",
    body: "A structured, cited prep doc with talking points.",
  },
];

export default function NewSessionPage() {
  return (
    <main className="relative flex-1 overflow-hidden">
      {/* Decorative brand mark, echoing the wordmark slash. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-20 top-24 -z-10 select-none font-display text-[26rem] font-black leading-none text-primary/[0.05] dark:text-primary/[0.07]"
      >
        /
      </div>

      <div className="mx-auto w-full max-w-6xl px-6 py-12">
        <Link
          href="/sessions"
          className="mb-8 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to sessions
        </Link>

        <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:gap-14">
          {/* Left: the pitch + what happens next. */}
          <div className="flex flex-col gap-8 lg:sticky lg:top-24">
            <div className="flex flex-col gap-4">
              <span className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/30 bg-accent/60 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-widest text-accent-foreground">
                <span className="block h-3 w-1.5 -skew-x-12 bg-primary" />
                Before the call
              </span>
              <h1 className="font-display text-4xl font-extrabold leading-[1.02] tracking-tight sm:text-5xl">
                Brief Argus,
                <br />
                <span className="text-primary">then let it run.</span>
              </h1>
              <p className="max-w-md text-base leading-relaxed text-muted-foreground">
                Give it the company and your objective. Argus does the deep prep
                and hands back a structured briefing before you walk in.
              </p>
            </div>

            <ol className="flex flex-col gap-1">
              {STEPS.map((step, i) => (
                <li
                  key={step.title}
                  className="group relative flex gap-4 rounded-xl px-3 py-3 transition-colors hover:bg-accent/40"
                >
                  <div className="relative flex flex-col items-center">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                      <step.icon className="size-4.5" />
                    </span>
                    {i < STEPS.length - 1 && (
                      <span className="mt-1 w-px flex-1 bg-border" />
                    )}
                  </div>
                  <div className="flex flex-col gap-0.5 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-primary">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <h3 className="font-display text-sm font-bold tracking-tight">
                        {step.title}
                      </h3>
                    </div>
                    <p className="text-sm text-muted-foreground">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          {/* Right: the form. */}
          <SessionCreateForm />
        </div>
      </div>
    </main>
  );
}
