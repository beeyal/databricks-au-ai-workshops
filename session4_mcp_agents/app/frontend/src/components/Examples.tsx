interface Props {
  onPick: (q: string) => void;
  disabled: boolean;
}

export const EXAMPLE_QUESTIONS = [
  "What was the average spot price in VIC yesterday?",
  "Which generators dispatched the most in NSW last week?",
  "Were there any LOR1 or LOR2 events this week?",
  "Show me the five highest 5-minute dispatch prices this month.",
];

export function Examples({ onPick, disabled }: Props) {
  return (
    <div className="examples" role="group" aria-label="Example questions">
      {EXAMPLE_QUESTIONS.map((q) => (
        <button
          key={q}
          type="button"
          className="example-chip"
          disabled={disabled}
          onClick={() => onPick(q)}
        >
          {q}
        </button>
      ))}
    </div>
  );
}
