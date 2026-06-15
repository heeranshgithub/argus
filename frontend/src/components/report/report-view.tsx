"use client";

import { Copy, Printer } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { BusinessSignalsList } from "@/components/report/business-signals-list";
import { DiscoveryQuestionsList } from "@/components/report/discovery-questions-list";
import { ReportSection, BulletList } from "@/components/report/report-section";
import { ReportToc } from "@/components/report/report-toc";
import { SourceCard } from "@/components/report/source-card";
import { reportToMarkdown } from "@/lib/report-markdown";
import { formatRelative } from "@/lib/format";
import type { Report } from "@/types/report";

export function ReportView({ report }: { report: Report }) {
  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(reportToMarkdown(report));
      toast.success("Report copied as Markdown");
    } catch {
      toast.error("Couldn't copy report");
    }
  }

  function print() {
    if (typeof window !== "undefined") window.print();
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_13rem]">
      <article className="flex max-w-2xl flex-col gap-8">
        <header className="flex flex-wrap items-center justify-between gap-3 print:hidden">
          <p className="text-muted-foreground text-xs">
            Generated {formatRelative(report.createdAt)}
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={copyMarkdown}>
              <Copy className="size-4" aria-hidden />
              Copy as Markdown
            </Button>
            <Button size="sm" variant="outline" onClick={print}>
              <Printer className="size-4" aria-hidden />
              Print / Save PDF
            </Button>
          </div>
        </header>

        <ReportSection id="overview" title="Company Overview">
          <p className="text-sm whitespace-pre-wrap">
            {report.companyOverview || "No overview available."}
          </p>
        </ReportSection>

        <ReportSection id="products" title="Products & Services">
          <BulletList items={report.productsAndServices} />
        </ReportSection>

        <ReportSection id="customers" title="Target Customers">
          <BulletList items={report.targetCustomers} />
        </ReportSection>

        <ReportSection id="signals" title="Business Signals">
          <BusinessSignalsList signals={report.businessSignals} />
        </ReportSection>

        <ReportSection id="risks" title="Risks & Challenges">
          <BulletList items={report.risksAndChallenges} />
        </ReportSection>

        <ReportSection id="questions" title="Suggested Discovery Questions">
          <DiscoveryQuestionsList questions={report.suggestedDiscoveryQuestions} />
        </ReportSection>

        <ReportSection id="outreach" title="Suggested Outreach Strategy">
          <p className="text-sm whitespace-pre-wrap">
            {report.suggestedOutreachStrategy || "No strategy available."}
          </p>
        </ReportSection>

        <ReportSection id="unknowns" title="Unknowns">
          <BulletList items={report.unknowns} />
        </ReportSection>

        <ReportSection id="sources" title="Sources">
          {report.sources.length ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {report.sources.map((source, i) => (
                <SourceCard key={`${source.url}-${i}`} source={source} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No sources cited.</p>
          )}
        </ReportSection>
      </article>

      <ReportToc />
    </div>
  );
}
