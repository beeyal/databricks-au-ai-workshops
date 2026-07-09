import type { ChatMessage } from "../types";
import { ToolIndicator } from "./ToolIndicator";
import { SourcesPanel } from "./SourcesPanel";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const showThinking =
    message.role === "assistant" && message.streaming && message.content === "";

  return (
    <div className={`bubble-row ${isUser ? "user" : "assistant"}`}>
      <div className="avatar" aria-hidden="true">
        {isUser ? "You" : "⚡"}
      </div>
      <div className={`bubble ${isUser ? "user" : "assistant"}`}>
        {message.role === "assistant" && (
          <ToolIndicator toolCalls={message.toolCalls} thinking={showThinking} />
        )}
        {message.content && (
          <div className="bubble-content">
            {message.content}
            {message.streaming && message.content !== "" && (
              <span className="cursor" aria-hidden="true">▍</span>
            )}
          </div>
        )}
        {message.role === "assistant" && !message.streaming && (
          <SourcesPanel sources={message.sources} />
        )}
      </div>
    </div>
  );
}
