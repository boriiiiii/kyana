"use client";

import type { Stats } from "@/lib/types";

interface StatsBarProps {
  stats: Stats | null;
  error: boolean;
}

interface StatCardProps {
  label: string;
  value: number | string;
  color: string;
  bgColor: string;
  dot?: string;
}

function StatCard({ label, value, color, bgColor, dot }: StatCardProps) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${bgColor}`}>
      {dot && <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />}
      <div>
        <div className={`text-lg font-bold leading-tight ${color}`}>
          {value}
        </div>
        <div className="text-[10px] text-[#666666] uppercase tracking-wide leading-tight">
          {label}
        </div>
      </div>
    </div>
  );
}

export default function StatsBar({ stats, error }: StatsBarProps) {
  if (error) {
    return (
      <div className="bg-[#141414] border-b border-[#222222] px-4 py-2">
        <p className="text-red-400 text-xs">
          Impossible de charger les statistiques. Vérifier que le backend est en ligne.
        </p>
      </div>
    );
  }

  const loading = stats === null;

  const placeholder = "—";

  return (
    <div className="bg-[#141414] border-b border-[#222222] px-4 py-2.5">
      <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
        <StatCard
          label="Total convs"
          value={loading ? placeholder : stats.total_conversations}
          color="text-white"
          bgColor="bg-[#1a1a1a]"
          dot="bg-[#666666]"
        />
        <div className="w-px h-8 bg-[#222222] flex-shrink-0" />
        <StatCard
          label="Auto (IA)"
          value={loading ? placeholder : stats.auto_conversations}
          color="text-green-400"
          bgColor="bg-green-900/20"
          dot="bg-green-400"
        />
        <StatCard
          label="Manuel"
          value={loading ? placeholder : stats.manual_conversations}
          color="text-orange-400"
          bgColor="bg-orange-900/20"
          dot="bg-orange-400"
        />
        <div className="w-px h-8 bg-[#222222] flex-shrink-0" />
        <StatCard
          label="Messages"
          value={loading ? placeholder : stats.total_messages}
          color="text-[#e91e8c]"
          bgColor="bg-[#e91e8c]/10"
        />
        <div className="w-px h-8 bg-[#222222] flex-shrink-0" />
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
          !loading && stats.needs_human_count > 0
            ? "bg-red-900/30 border border-red-800/40"
            : "bg-[#1a1a1a]"
        }`}>
          {!loading && stats.needs_human_count > 0 && (
            <span className="text-base animate-pulse">🚨</span>
          )}
          <div>
            <div className={`text-lg font-bold leading-tight ${
              !loading && stats.needs_human_count > 0 ? "text-red-400" : "text-[#666666]"
            }`}>
              {loading ? placeholder : stats.needs_human_count}
            </div>
            <div className="text-[10px] text-[#666666] uppercase tracking-wide leading-tight">
              Urgentes
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
