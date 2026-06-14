import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { SessionCreateForm } from "@/components/sessions/session-create-form";

export default function NewSessionPage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-10">
      <Link
        href="/sessions"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to sessions
      </Link>
      <SessionCreateForm />
    </main>
  );
}
