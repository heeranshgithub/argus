import { FileText } from "lucide-react";

export function ReportEmpty({ message }: { message?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-16 text-center">
      <FileText className="text-muted-foreground size-8" aria-hidden />
      <div className="flex flex-col gap-1">
        <p className="font-medium">No report yet</p>
        <p className="text-muted-foreground text-sm">
          {message ?? "Run research to generate a report."}
        </p>
      </div>
    </div>
  );
}
