import { FileText } from "lucide-react";

export function ReportEmpty({ message }: { message?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-16 text-center">
      <span className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
        <FileText className="size-6" aria-hidden />
      </span>
      <div className="flex flex-col gap-1">
        <p className="font-display font-bold tracking-tight">No report yet</p>
        <p className="text-muted-foreground text-sm">
          {message ?? "Run research to generate a report."}
        </p>
      </div>
    </div>
  );
}
