import { Eye } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

export function TopNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/70 backdrop-blur-md">
      <nav className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-6">
        <Link
          href="/"
          className="group flex items-center gap-2.5"
          aria-label="Argus home"
        >
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm transition-transform group-hover:-rotate-6">
            <Eye className="size-4.5" />
          </span>
          <span className="font-display text-xl font-extrabold tracking-tight">
            <span className="text-primary">/</span>argus
          </span>
        </Link>

        <div className="flex items-center gap-1 sm:gap-2">
          <Link
            href="/sessions"
            className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            Sessions
          </Link>
          <div className="mx-1 hidden h-5 w-px bg-border sm:block" />
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
