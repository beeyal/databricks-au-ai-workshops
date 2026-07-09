import { useCallback, useRef, useState } from "react";
import type { AgentEvent, ChatMessage } from "./types";

function uid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

// Parse a fetch ReadableStream of SSE ("data: {...}\n\n") into AgentEvents.
async function* readSSE(
  response: Response
): AsyncGenerator<AgentEvent, void, unknown> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const payload = line.slice("data:".length).trim();
      if (!payload) continue;
      try {
        yield JSON.parse(payload) as AgentEvent;
      } catch {
        // ignore malformed keepalive lines
      }
    }
  }
}

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  const patchAssistant = useCallback(
    (id: string, fn: (m: ChatMessage) => ChatMessage) => {
      setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
    },
    []
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busyRef.current) return;
      busyRef.current = true;
      setBusy(true);

      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content: trimmed,
        toolCalls: [],
        sources: [],
        streaming: false,
      };
      const assistantId = uid();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        sources: [],
        streaming: true,
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      try {
        const resp = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, session_id: sessionId }),
        });
        if (!resp.ok || !resp.body) {
          throw new Error(`Request failed: ${resp.status}`);
        }

        for await (const ev of readSSE(resp)) {
          if (ev.type === "tool_call") {
            patchAssistant(assistantId, (m) =>
              m.toolCalls.includes(ev.name)
                ? m
                : { ...m, toolCalls: [...m.toolCalls, ev.name] }
            );
          } else if (ev.type === "token") {
            patchAssistant(assistantId, (m) => ({
              ...m,
              content: m.content + ev.text,
            }));
          } else if (ev.type === "final") {
            patchAssistant(assistantId, (m) => ({
              ...m,
              content: ev.content || m.content,
              sources: ev.sources || [],
            }));
          } else if (ev.type === "done") {
            patchAssistant(assistantId, (m) => ({ ...m, streaming: false }));
          }
        }
      } catch (err) {
        patchAssistant(assistantId, (m) => ({
          ...m,
          content:
            m.content ||
            `Sorry, something went wrong contacting the agent: ${String(err)}`,
          streaming: false,
        }));
      } finally {
        patchAssistant(assistantId, (m) => ({ ...m, streaming: false }));
        busyRef.current = false;
        setBusy(false);
      }
    },
    [patchAssistant, sessionId]
  );

  return { messages, busy, send };
}
