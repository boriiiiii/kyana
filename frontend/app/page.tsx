"use client";

import { useState } from "react";
import useSWR from "swr";
import StatsBar from "@/components/StatsBar";
import ConversationList from "@/components/ConversationList";
import ConversationDetail from "@/components/ConversationDetail";
import { fetchStats, fetchConversations } from "@/lib/api";
import type { Conversation } from "@/lib/types";

export default function Home() {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: stats, error: statsError } = useSWR(
    "stats",
    fetchStats,
    { refreshInterval: 30_000 }
  );

  const { data: conversations, mutate: mutateConversations } = useSWR(
    "conversations",
    () => fetchConversations(0, 100),
    { refreshInterval: 10_000 }
  );

  const selectedConversation =
    conversations?.find((c) => c.id === selectedId) ?? null;

  const handleConversationModeChange = (updated: Conversation) => {
    if (!conversations) return;
    mutateConversations(
      conversations.map((c) => (c.id === updated.id ? updated : c)),
      false
    );
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#0d0d0d]">
      {/* Header */}
      <header className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-[#222222] bg-[#141414]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#e91e8c] flex items-center justify-center font-bold text-white text-sm">
            K
          </div>
          <div>
            <h1 className="text-white font-semibold text-base leading-tight">Kyana</h1>
            <p className="text-[#666666] text-xs leading-tight">Assistant IA — Instagram DMs</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs text-[#999999]">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            En ligne
          </span>
        </div>
      </header>

      {/* Stats bar */}
      <div className="flex-shrink-0">
        <StatsBar stats={stats ?? null} error={!!statsError} />
      </div>

      {/* Main split layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar: conversation list */}
        <aside className="w-full md:w-[340px] lg:w-[380px] flex-shrink-0 border-r border-[#222222] overflow-hidden flex flex-col">
          <ConversationList
            conversations={conversations ?? []}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </aside>

        {/* Right panel: conversation detail */}
        <main className="flex-1 overflow-hidden flex flex-col">
          <ConversationDetail
            conversation={selectedConversation}
            onModeChange={handleConversationModeChange}
          />
        </main>
      </div>
    </div>
  );
}
