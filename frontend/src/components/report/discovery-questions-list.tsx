import type { DiscoveryQuestion } from "@/types/report";

export function DiscoveryQuestionsList({
  questions,
}: {
  questions: DiscoveryQuestion[];
}) {
  if (!questions.length) {
    return (
      <p className="text-muted-foreground text-sm">No questions suggested.</p>
    );
  }

  return (
    <ol className="space-y-3">
      {questions.map((q, i) => (
        <li key={i} className="flex gap-3">
          <span className="text-muted-foreground mt-0.5 w-5 shrink-0 text-right text-sm font-medium tabular-nums">
            {i + 1}.
          </span>
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium">{q.question}</p>
            {q.rationale && (
              <p className="text-muted-foreground text-sm">{q.rationale}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
