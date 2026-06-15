import { Plus } from "lucide-react";
import Link from "next/link";

import { SessionList } from "@/components/sessions/session-list";
import { Button } from "@/components/ui/button";

export default function SessionsPage() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-12">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-4xl font-extrabold tracking-tight">
            Sessions
          </h1>
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
