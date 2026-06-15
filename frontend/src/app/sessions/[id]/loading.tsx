import { Skeleton } from "@/components/ui/skeleton";

export default function SessionDetailLoading() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
      <Skeleton className="mb-6 h-9 w-36 rounded-full" />
      <Skeleton className="mb-8 h-44 w-full rounded-2xl" />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[20rem_1fr]">
        <Skeleton className="h-44 w-full rounded-2xl" />
        <div className="flex flex-col gap-4">
          <Skeleton className="h-11 w-72 rounded-xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </div>
    </main>
  );
}
