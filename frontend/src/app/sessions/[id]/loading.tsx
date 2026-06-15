import { Skeleton } from "@/components/ui/skeleton";

export default function SessionDetailLoading() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
      <Skeleton className="mb-2 h-4 w-24" />
      <Skeleton className="mb-8 h-8 w-72" />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[20rem_1fr]">
        <Skeleton className="h-40 w-full rounded-lg" />
        <div className="flex flex-col gap-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </div>
    </main>
  );
}
