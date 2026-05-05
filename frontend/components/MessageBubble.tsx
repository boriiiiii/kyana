"use client";

import type { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

const SYSTEM_MESSAGE_PATTERNS = [
  /\[basculé en manuel/i,
  /\[switched to manual/i,
  /\[ia incertaine/i,
  /\[mode:/i,
];

function isSystemMessage(content: string): boolean {
  return SYSTEM_MESSAGE_PATTERNS.some((pattern) => pattern.test(content));
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const { direction, content, needs_human, created_at } = message;

  // System message (centered pill)
  if (isSystemMessage(content)) {
    return (
      <div className="flex justify-center my-3 px-4">
        <div className="inline-flex items-center gap-1.5 bg-[#1a1a1a] border border-[#2a2a2a] rounded-full px-3 py-1">
          <svg
            className="w-3 h-3 text-[#555555]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span className="text-xs italic text-[#555555]">{content}</span>
        </div>
      </div>
    );
  }

  const isInbound = direction === "inbound";

  return (
    <div
      className={`flex mb-3 px-4 ${
        isInbound ? "justify-start" : "justify-end"
      }`}
    >
      <div
        className={`max-w-[75%] md:max-w-[65%] ${
          isInbound ? "items-start" : "items-end"
        } flex flex-col gap-1`}
      >
        {/* Bubble */}
        <div
          className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed break-words
            ${
              isInbound
                ? needs_human
                  ? "bg-red-900/40 border border-red-700/50 text-white rounded-tl-sm"
                  : "bg-[#2a2a2a] text-[#e5e5e5] rounded-tl-sm"
                : "bg-[#e91e8c] text-white rounded-tr-sm"
            }
          `}
        >
          {needs_human && isInbound && (
            <div className="flex items-center gap-1 mb-1.5">
              <span className="text-xs">🚨</span>
              <span className="text-[10px] text-red-300 font-medium uppercase tracking-wide">
                Intervention requise
              </span>
            </div>
          )}
          <p>{content}</p>
        </div>

        {/* Meta */}
        <div
          className={`flex items-center gap-1.5 ${
            isInbound ? "pl-1" : "pr-1"
          }`}
        >
          <span className="text-[10px] text-[#444444]">
            {formatTime(created_at)}
          </span>
          {!isInbound && (
            <span className="text-[10px] text-[#e91e8c]/60">Hina ✦ IA</span>
          )}
          {isInbound && (
            <span className="text-[10px] text-[#444444]">Client</span>
          )}
        </div>
      </div>
    </div>
  );
}
