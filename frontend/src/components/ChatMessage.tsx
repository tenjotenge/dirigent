import { PolicyBadge } from "./PolicyBadge";
import { ToolExecutionCard } from "./ToolExecutionCard";
import type { ChatMessage as ChatMessageType } from "../types";
import { formatTimestamp } from "../utils/format";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`chat-message ${message.role}`}>
      <div className="chat-message-header">
        <span className="chat-message-role">{isUser ? "You" : "Assistant"}</span>
        <span className="chat-message-time">{formatTimestamp(message.timestamp)}</span>
      </div>

      {message.error ? (
        <div className="error-panel">
          <div className="error-panel-title">Error</div>
          <p>{message.error}</p>
        </div>
      ) : isUser ? (
        <div className="chat-message-content user-content">{message.content}</div>
      ) : (
        <div className="chat-message-content markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      )}

      {message.policyDecision && (
        <div className="policy-badges">
          {message.policyDecision.allowed_calls.map((call) => (
            <PolicyBadge
              key={call.call_id}
              toolName={call.tool_name}
              status="approved"
              reason={call.reason ?? undefined}
            />
          ))}
          {message.policyDecision.pending_confirmation_calls.map((call) => (
            <PolicyBadge
              key={call.call_id}
              toolName={call.tool_name}
              status="confirmation"
              reason={call.reason ?? undefined}
            />
          ))}
          {message.policyDecision.blocked_calls.map((call) => (
            <PolicyBadge
              key={call.call_id}
              toolName={call.tool_name}
              status="denied"
              reason={call.reason ?? undefined}
            />
          ))}
        </div>
      )}

      {message.toolResults && message.toolResults.length > 0 && (
        <div className="tool-cards">
          {message.toolResults.map((result) => (
            <ToolExecutionCard key={result.call_id} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}
