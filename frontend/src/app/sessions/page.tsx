import { Plus } from "lucide-react";
import Link from "next/link";

import { SessionList } from "@/components/sessions/session-list";
import { Button } from "@/components/ui/button";

export default function SessionsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Sessions</h1>
          <p className="text-sm text-muted-foreground">
            Your research sessions, newest first.
          </p>
        </div>
        <Button asChild>
          <Link href="/sessions/new">
            <Plus className="size-4" />
            New session
          </Link>
        </Button>
      </div>

      <SessionList />
    </main>
  );
}
