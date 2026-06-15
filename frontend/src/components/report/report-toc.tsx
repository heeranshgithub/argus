import { REPORT_SECTIONS } from "@/components/report/sections";

/** Sticky table of contents for the report (right rail on xl+). */
export function ReportToc() {
  return (
    <nav aria-label="Report sections" className="sticky top-24 hidden xl:block">
      <p className="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">
        On this page
      </p>
      <ul className="space-y-1 text-sm">
        {REPORT_SECTIONS.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className="text-muted-foreground hover:text-foreground block rounded px-2 py-1 transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              {s.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
