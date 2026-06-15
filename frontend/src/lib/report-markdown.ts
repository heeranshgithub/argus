/**
 * Client-side Markdown stringifier for a report — powers "Copy as Markdown"
 * with no backend round-trip. Mirrors the on-screen section order.
 */

import type { Report } from "@/types/report";

function bullets(items: string[]): string {
  return items.length ? items.map((i) => `- ${i}`).join("\n") : "_None._";
}

export function reportToMarkdown(report: Report): string {
  const lines: string[] = [];

  lines.push("# Research Report", "");
  lines.push("## Company Overview", "", report.companyOverview || "_None._", "");

  lines.push("## Products & Services", "", bullets(report.productsAndServices), "");
  lines.push("## Target Customers", "", bullets(report.targetCustomers), "");

  lines.push("## Business Signals", "");
  if (report.businessSignals.length) {
    for (const s of report.businessSignals) {
      lines.push(
        `### ${s.category} (confidence ${(s.confidence * 100).toFixed(0)}%)`,
        "",
        s.summary,
        "",
      );
      if (s.evidenceUrls.length) {
        lines.push(...s.evidenceUrls.map((u) => `- ${u}`), "");
      }
    }
  } else {
    lines.push("_None._", "");
  }

  lines.push("## Risks & Challenges", "", bullets(report.risksAndChallenges), "");

  lines.push("## Suggested Discovery Questions", "");
  if (report.suggestedDiscoveryQuestions.length) {
    report.suggestedDiscoveryQuestions.forEach((q, i) => {
      lines.push(`${i + 1}. ${q.question}`);
      if (q.rationale) lines.push(`   - _Why:_ ${q.rationale}`);
    });
    lines.push("");
  } else {
    lines.push("_None._", "");
  }

  lines.push(
    "## Suggested Outreach Strategy",
    "",
    report.suggestedOutreachStrategy || "_None._",
    "",
  );

  lines.push("## Unknowns", "", bullets(report.unknowns), "");

  lines.push("## Sources", "");
  if (report.sources.length) {
    report.sources.forEach((src, i) => {
      const usedIn = src.usedIn.length ? ` _(cited in: ${src.usedIn.join(", ")})_` : "";
      lines.push(`${i + 1}. [${src.title || src.url}](${src.url})${usedIn}`);
    });
    lines.push("");
  } else {
    lines.push("_None._", "");
  }

  return lines.join("\n").trimEnd() + "\n";
}
