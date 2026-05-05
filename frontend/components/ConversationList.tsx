"use client";

import { useState, useMemo } from "react";
import type { Conversation } from "@/lib/types";
import ConversationItem from "./ConversationItem";

type Tab = "all" | "auto" | "manual" | "urgent";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "Toutes" },
  { id: "auto", label: "Auto" },
  { id: "manual", label: "Manuel" },
  { id: "urgent", label: "Urgentes" },
];

interface ConversationListProps {
  conversations: Conversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export default function ConversationList({
  conversations,
  selectedId,
  onSelect,
}: ConversationListProps) {
  const [activeTab, setActiveTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");

  // Derive needs_human per conversation: true if any message has needs_human=true
  // Since the API doesn't return needs_human on conversations directly,
  // we rely on the last_message_preview content or infer from available data.
  // We'll check if the conversation has needs_human field (might be set server-side)
  // or fall back to false. The "Urgentes" tab will rely on the needs_human field.

  const filtered = useMemo(() => {
    let list = [...conversations];

    // Filter by tab
    if (activeTab === "auto") {
      list = list.filter((c) => c.mode === "auto");
    } else if (activeTab === "manual") {
      list = list.filter((c) => c.mode === "manual");
    } else if (activeTab === "urgent") {
      list = list.filter((c) => c.needs_human === true);
    }

    // Filter by search
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((c) => c.sender_id.toLowerCase().includes(q));
    }

    // Sort: needs_human first, then by last_message_at desc
    list.sort((a, b) => {
      if (a.needs_human && !b.needs_human) return -1;
      if (!a.needs_human && b.needs_human) return 1;
      return (
        new Date(b.last_message_at).getTime() -
        new Date(a.last_message_at).getTime()
      );
    });

    return list;
  }, [conversations, activeTab, search]);

  const urgentCount = conversations.filter((c) => c.needs_human).length;

  return (
    <div className="flex flex-col h-full bg-[#141414]">
      {/* Search input */}
      <div className="px-3 pt-3 pb-2">
        <div className="relative">
          <svg
            className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#444444]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Rechercher un compte..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg text-sm text-white placeholder-[#444444] focus:outline-none focus:border-[#e91e8c]/50 focus:ring-1 focus:ring-[#e91e8c]/20 transition-colors"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-3 pb-2 border-b border-[#222222]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-[#e91e8c] text-white"
                : "text-[#666666] hover:text-white hover:bg-[#1a1a1a]"
            }`}
          >
            {tab.label}
            {tab.id === "urgent" && urgentCount > 0 && (
              <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold leading-none">
                {urgentCount > 9 ? "9+" : urgentCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Conversation count */}
      <div className="px-3 py-1.5">
        <p className="text-[10px] text-[#444444] uppercase tracking-wide">
          {filtered.length} conversation{filtered.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <div className="w-12 h-12 rounded-full bg-[#1a1a1a] flex items-center justify-center mb-3">
              <svg
                className="w-6 h-6 text-[#333333]"
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
            <p className="text-[#444444] text-sm">Aucune conversation</p>
            {search && (
              <p className="text-[#333333] text-xs mt-1">
                pour &ldquo;{search}&rdquo;
              </p>
            )}
          </div>
        ) : (
          filtered.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isSelected={conv.id === selectedId}
              onClick={() => onSelect(conv.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
