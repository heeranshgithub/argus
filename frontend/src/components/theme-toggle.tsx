"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { cn } from "@/lib/utils";

/**
 * A pill switch between light and dark.
 *
 * Visuals are driven entirely by the `.dark` class that next-themes puts on
 * <html> (via `dark:` variants), so there's no mount flag, no hydration flash,
 * and no setState-in-effect. The click reads the live DOM class to decide the
 * next theme, and we add a short `theme-transition` class so the cream↔charcoal
 * swap crossfades instead of snapping (see globals.css).
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { setTheme } = useTheme();

  function toggle() {
    const root = document.documentElement;
    const next = root.classList.contains("dark") ? "light" : "dark";
    root.classList.add("theme-transition");
    window.setTimeout(() => root.classList.remove("theme-transition"), 350);
    setTheme(next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle dark mode"
      title="Toggle dark mode"
      className={cn(
        "relative inline-flex h-8 w-[3.75rem] items-center rounded-full border border-border bg-secondary/70 px-0.5 transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
        className,
      )}
    >
      <span className="pointer-events-none flex size-6 translate-x-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition-transform duration-300 ease-out dark:translate-x-[1.75rem]">
        <Sun className="size-3.5 dark:hidden" />
        <Moon className="hidden size-3.5 dark:block" />
      </span>
    </button>
  );
}
