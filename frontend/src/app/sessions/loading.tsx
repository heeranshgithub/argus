import { Skeleton } from "@/components/ui/skeleton";

export default function SessionsLoading() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-12">
      <div className="mb-8 flex items-end justify-between">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-4 w-56" />
        </div>
        <Skeleton className="h-11 w-36" />
      </div>
      <Skeleton className="mb-6 h-16 w-full rounded-xl" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-36 w-full rounded-xl" />
        ))}
      </div>
    </main>
  );
}
