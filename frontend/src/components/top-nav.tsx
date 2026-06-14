import { Eye } from "lucide-react";
import Link from "next/link";

export function TopNav() {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
      <nav className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Eye className="size-5" />
          Argus
        </Link>
        <Link
          href="/sessions"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          Sessions
        </Link>
      </nav>
    </header>
  );
}
