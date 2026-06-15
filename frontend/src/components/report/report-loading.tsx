import { Skeleton } from "@/components/ui/skeleton";

/** Skeleton roughly matching the report section layout. */
export function ReportLoading() {
  return (
    <div className="flex flex-col gap-8">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex flex-col gap-3 border-b pb-8">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ))}
    </div>
  );
}
