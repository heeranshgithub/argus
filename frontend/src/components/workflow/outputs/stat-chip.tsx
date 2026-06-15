import { cn } from "@/lib/utils";

/** A small labelled metric chip used inside node output panels. */
export function StatChip({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "warn" | "good";
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-0.5 rounded-md border px-3 py-2",
        tone === "warn" && "border-amber-500/30 bg-amber-500/5",
        tone === "good" && "border-emerald-500/30 bg-emerald-500/5",
      )}
    >
      <span className="text-base font-semibold tabular-nums leading-none">
        {value}
      </span>
      <span className="text-muted-foreground text-xs">{label}</span>
    </div>
  );
}
