"use client";

import type { Conversation } from "@/lib/types";

interface ConversationItemProps {
  conversation: Conversation;
  isSelected: boolean;
  onClick: () => void;
}

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  const diffH = Math.floor(diffMs / 3_600_000);
  const diffD = Math.floor(diffMs / 86_400_000);

  if (diffMin < 1) return "à l'instant";
  if (diffMin < 60) return `il y a ${diffMin} min`;
  if (diffH < 24) return `il y a ${diffH}h`;
  if (diffD === 1) return "hier";
  if (diffD < 7) return `il y a ${diffD}j`;
  return new Date(dateStr).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
  });
}

export default function ConversationItem({
  conversation,
  isSelected,
  onClick,
}: ConversationItemProps) {
  const { sender_id, mode, last_message_at, last_message_preview, needs_human } =
    conversation;

  const isUrgent = needs_human === true;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-3 border-b border-[#1a1a1a] transition-colors relative
        ${isSelected
          ? "bg-[#e91e8c]/10 border-l-2 border-l-[#e91e8c]"
          : isUrgent
          ? "bg-red-950/20 border-l-2 border-l-red-600 hover:bg-red-950/30"
          : "border-l-2 border-l-transparent hover:bg-[#1a1a1a]"
        }
      `}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Avatar + info */}
        <div className="flex items-start gap-2.5 min-w-0 flex-1">
          {/* Avatar */}
          <div
            className={`w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold
              ${isUrgent
                ? "bg-red-900/60 text-red-300 ring-2 ring-red-600/50"
                : "bg-[#2a2a2a] text-[#999999]"
              }
            `}
          >
            {sender_id.charAt(0).toUpperCase()}
          </div>

          {/* Text content */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-sm font-medium text-white truncate max-w-[140px]">
                @{sender_id}
              </span>
              {isUrgent && (
                <span className="flex-shrink-0 text-xs" title="Intervention humaine requise">
                  🚨
                </span>
              )}
            </div>
            <p className="text-xs text-[#666666] truncate">
              {last_message_preview ?? "Aucun message"}
            </p>
          </div>
        </div>

        {/* Right: time + badge */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="text-[10px] text-[#444444] whitespace-nowrap">
            {relativeTime(last_message_at)}
          </span>
          <span
            className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide
              ${mode === "auto"
                ? "bg-green-900/40 text-green-400 border border-green-800/40"
                : "bg-orange-900/40 text-orange-400 border border-orange-800/40"
              }
            `}
          >
            {mode === "auto" ? "Auto" : "Manuel"}
          </span>
        </div>
      </div>
    </button>
  );
}
