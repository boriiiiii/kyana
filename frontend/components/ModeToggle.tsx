"use client";

import { useState } from "react";
import { patchConversationMode } from "@/lib/api";
import type { Conversation } from "@/lib/types";

interface ModeToggleProps {
  conversation: Conversation;
  onModeChange: (updated: Conversation) => void;
}

export default function ModeToggle({
  conversation,
  onModeChange,
}: ModeToggleProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAuto = conversation.mode === "auto";

  const handleToggle = async () => {
    const newMode = isAuto ? "manual" : "auto";
    setLoading(true);
    setError(null);
    try {
      const updated = await patchConversationMode(conversation.id, newMode);
      onModeChange(updated);
    } catch (err) {
      setError("Erreur lors du changement de mode. Réessaie.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {/* Status banner */}
      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
          ${isAuto
            ? "bg-green-900/30 border border-green-800/40 text-green-400"
            : "bg-orange-900/30 border border-orange-800/40 text-orange-400"
          }
        `}
      >
        <div
          className={`w-2 h-2 rounded-full flex-shrink-0 ${
            isAuto ? "bg-green-400 animate-pulse" : "bg-orange-400"
          }`}
        />
        {isAuto
          ? "L'IA gère cette conversation"
          : "Tu gères cette conversation manuellement"}
      </div>

      {/* Toggle button */}
      <button
        onClick={handleToggle}
        disabled={loading}
        className={`flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-lg text-sm font-semibold transition-all
          ${loading ? "opacity-60 cursor-not-allowed" : "cursor-pointer"}
          ${isAuto
            ? "bg-orange-600 hover:bg-orange-500 text-white"
            : "bg-green-600 hover:bg-green-500 text-white"
          }
        `}
      >
        {loading ? (
          <>
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
            Changement en cours...
          </>
        ) : isAuto ? (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
            Passer en MANUEL
          </>
        ) : (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
            Repasser en AUTO (IA)
          </>
        )}
      </button>

      {error && (
        <p className="text-xs text-red-400 text-center">{error}</p>
      )}
    </div>
  );
}
