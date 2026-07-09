interface Props {
  toolCalls: string[];
  thinking: boolean;
}

// Humanise raw MCP tool names for display.
function pretty(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("genie")) return "Genie (NEM data)";
  if (n.includes("search") || n.includes("vector") || n.includes("notice"))
    return "Vector Search (market notices)";
  return name.replace(/^workshop_au__aemo__/, "").replace(/_/g, " ");
}

export function ToolIndicator({ toolCalls, thinking }: Props) {
  if (toolCalls.length === 0 && !thinking) return null;
  return (
    <div className="tool-indicator" aria-live="polite">
      {thinking && toolCalls.length === 0 && (
        <span className="tool-thinking">
          <span className="dot" /> <span className="dot" /> <span className="dot" />
          <em>Thinking…</em>
        </span>
      )}
      {toolCalls.map((t) => (
        <span key={t} className="tool-chip" title={t}>
          <span className="tool-chip-icon" aria-hidden="true">⚙</span>
          {pretty(t)}
        </span>
      ))}
    </div>
  );
}
