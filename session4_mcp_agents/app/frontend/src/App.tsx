import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Header } from "./components/Header";
import { MessageBubble } from "./components/MessageBubble";
import { Examples } from "./components/Examples";
import { useChat } from "./useChat";
import type { HealthInfo } from "./types";

function newSessionId(): string {
  return "sess-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export default function App() {
  const sessionId = useMemo(newSessionId, []);
  const { messages, busy, send } = useChat(sessionId);
  const [input, setInput] = useState("");
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => setHealth(h))
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const submit = () => {
    const text = input;
    setInput("");
    void send(text);
    inputRef.current?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const pickExample = (q: string) => {
    if (busy) return;
    void send(q);
  };

  const empty = messages.length === 0;

  return (
    <div className="app">
      <Header health={health} />

      <main className="chat-area" ref={scrollRef} aria-live="polite">
        {empty ? (
          <div className="welcome">
            <h2>Ask about the National Electricity Market</h2>
            <p>
              Grounded in Australia East, in-region data via a
              provisioned-throughput endpoint. Dispatch intervals, spot prices,
              market notices, settlements and generation units.
            </p>
            <Examples onPick={pickExample} disabled={busy} />
          </div>
        ) : (
          <div className="messages">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        )}
      </main>

      <footer className="composer">
        {!empty && (
          <div className="composer-examples">
            <Examples onPick={pickExample} disabled={busy} />
          </div>
        )}
        <form
          className="composer-row"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label htmlFor="chat-input" className="visually-hidden">
            Ask the AEMO NEM Operations Agent a question
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            className="chat-input"
            placeholder="Ask about NEM dispatch, spot prices, or market notices…"
            value={input}
            rows={1}
            disabled={busy}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            type="submit"
            className="send-btn"
            disabled={busy || input.trim() === ""}
            aria-label="Send message"
          >
            {busy ? "…" : "Send"}
          </button>
        </form>
        <p className="disclaimer">
          Workshop dataset · not live NEM conditions · data residency: Australia East
        </p>
      </footer>
    </div>
  );
}
