import { FileSearch } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function SessionEmptyState() {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted">
        <FileSearch className="size-6 text-muted-foreground" />
      </div>
      <div className="flex flex-col gap-1">
        <p className="font-medium">No sessions yet</p>
        <p className="text-sm text-muted-foreground">
          Create your first research session to get started.
        </p>
      </div>
      <Button asChild>
        <Link href="/sessions/new">New session</Link>
      </Button>
    </div>
  );
}
