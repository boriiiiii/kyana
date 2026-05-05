"use client";

import { useEffect, useRef } from "react";
import useSWR from "swr";
import { fetchMessages } from "@/lib/api";
import type { Conversation } from "@/lib/types";
import MessageBubble from "./MessageBubble";
import ModeToggle from "./ModeToggle";

interface ConversationDetailProps {
  conversation: Conversation | null;
  onModeChange: (updated: Conversation) => void;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function ConversationDetail({
  conversation,
  onModeChange,
}: ConversationDetailProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: messages, error: messagesError } = useSWR(
    conversation ? `messages-${conversation.id}` : null,
    () => fetchMessages(conversation!.id),
    { refreshInterval: 5_000 }
  );

  // Auto-scroll to bottom when messages load or update
  useEffect(() => {
    if (messages && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Empty state
  if (!conversation) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#0d0d0d] text-center px-8">
        <div className="w-20 h-20 rounded-full bg-[#141414] flex items-center justify-center mb-4">
          <svg
            className="w-10 h-10 text-[#2a2a2a]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </div>
        <h2 className="text-[#333333] text-lg font-medium mb-2">
          Sélectionne une conversation
        </h2>
        <p className="text-[#2a2a2a] text-sm max-w-xs">
          Clique sur une conversation dans la liste pour afficher les messages et gérer le mode IA.
        </p>
      </div>
    );
  }

  const hasUrgentMessages = messages?.some((m) => m.needs_human) ?? false;

  return (
    <div className="flex flex-col h-full bg-[#0d0d0d]">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-[#222222] bg-[#141414] px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          {/* Left: avatar + info */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-full bg-[#2a2a2a] flex items-center justify-center text-base font-bold text-[#999999] flex-shrink-0">
              {conversation.sender_id.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-white font-semibold text-base">
                  @{conversation.sender_id}
                </h2>
                {hasUrgentMessages && (
                  <span className="inline-flex items-center gap-1 text-xs bg-red-900/40 border border-red-700/40 text-red-400 px-2 py-0.5 rounded-full">
                    🚨 Intervention requise
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-xs text-[#555555]">
                  Depuis le {formatDate(conversation.created_at)}
                </span>
                {messages && (
                  <span className="text-xs text-[#444444]">
                    {messages.length} message{messages.length !== 1 ? "s" : ""}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Right: mode toggle */}
          <div className="flex-shrink-0 w-56">
            <ModeToggle
              conversation={conversation}
              onModeChange={onModeChange}
            />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto messages-container py-4">
        {messagesError && (
          <div className="flex justify-center px-4 mb-4">
            <div className="bg-red-900/30 border border-red-800/40 rounded-lg px-4 py-2 text-sm text-red-400">
              Impossible de charger les messages. Réessaie.
            </div>
          </div>
        )}

        {!messages && !messagesError && (
          <div className="flex items-center justify-center py-16">
            <div className="flex items-center gap-2 text-[#444444] text-sm">
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Chargement des messages...
            </div>
          </div>
        )}

        {messages && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center px-4">
            <p className="text-[#444444] text-sm">Aucun message dans cette conversation.</p>
          </div>
        )}

        {messages &&
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>

      {/* Footer: info bar */}
      <div className="flex-shrink-0 border-t border-[#1a1a1a] bg-[#0d0d0d] px-4 py-2">
        <p className="text-[10px] text-[#333333] text-center">
          {conversation.mode === "auto"
            ? "Kyana (IA) répond automatiquement aux messages de ce client"
            : "Tu réponds toi-même — Kyana est en pause pour ce client"}
          {" · "}
          Rafraîchissement automatique toutes les 5 secondes
        </p>
      </div>
    </div>
  );
}
