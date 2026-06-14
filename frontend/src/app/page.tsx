import { HealthCard } from "@/components/health-card";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Argus</h1>
        <p className="max-w-md text-muted-foreground">
          AI Research Copilot — research a company and generate a structured
          meeting briefing.
        </p>
      </div>
      <HealthCard />
    </main>
  );
}
