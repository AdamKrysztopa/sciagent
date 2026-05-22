import type { UserMessage } from "../../shared/contracts";

interface MessageBannerProps {
  messages: UserMessage[];
  onDismiss: (id: string) => void;
}

const TYPE_STYLES: Record<UserMessage["type"], string> = {
  info: "agt-message-banner agt-message-banner--info",
  warning: "agt-message-banner agt-message-banner--warning",
  critical: "agt-message-banner agt-message-banner--critical",
};

export function MessageBanner({ messages, onDismiss }: MessageBannerProps) {
  if (messages.length === 0) return null;

  return (
    <div className="agt-message-banners">
      {messages.map((msg) => (
        <div key={msg.id} className={TYPE_STYLES[msg.type]}>
          <span className="agt-message-banner__text">{msg.text}</span>
          <button
            type="button"
            className="agt-message-banner__dismiss"
            onClick={() => onDismiss(msg.id)}
            aria-label="Dismiss message"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
