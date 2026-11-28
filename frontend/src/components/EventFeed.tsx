import React from "react";
import { Clock } from "lucide-react";
import { useStore } from "../store/useStore";

export const EventFeed: React.FC = () => {
  const { recentEvents } = useStore();

  return (
    <div className="w-full h-full flex flex-col text-xs overflow-hidden bg-[var(--studio-surface)] text-[var(--studio-text-primary)]">
      {/* Events log */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2 font-mono text-[11px] min-h-0">
        {recentEvents.length === 0 ? (
          <div className="h-full flex items-center justify-center text-[var(--studio-text-muted)] font-sans py-8">
            Awaiting streaming events
          </div>
        ) : (
          recentEvents.slice(0, 50).map((ev) => {
            let badgeBg =
              "bg-stone-900/[0.06] text-[var(--studio-text-secondary)] border border-[var(--studio-border)] dark:bg-white/[0.08]";
            if (ev.event_type.startsWith("order")) {
              badgeBg =
                "bg-[#D9533B]/12 text-[#A53420] border border-[#D9533B]/25 dark:bg-[#D9533B]/18 dark:text-[#FF9D8A] dark:border-[#D9533B]/35";
            } else if (ev.event_type.startsWith("robot")) {
              badgeBg =
                "bg-emerald-600/12 text-[#1D6144] border border-emerald-700/25 dark:bg-emerald-500/18 dark:text-emerald-300 dark:border-emerald-500/35";
            } else if (ev.event_type.startsWith("alert")) {
              badgeBg =
                "bg-amber-600/12 text-[#8F4F0D] border border-amber-700/25 dark:bg-amber-500/16 dark:text-amber-300 dark:border-amber-500/35";
            } else if (ev.event_type.startsWith("command")) {
              badgeBg =
                "bg-amber-900/10 text-[#4F3B30] border border-stone-500/25 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-700/40";
            }

            return (
              <div
                key={ev.event_id}
                className="p-2 rounded-xl bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] hover:border-[var(--studio-border-strong)] flex items-start gap-2.5 transition-[background-color,border-color] duration-150"
              >
                <div className="flex items-center gap-1 text-[var(--studio-text-muted)] shrink-0 text-[10.5px] pt-0.5 tabular-nums">
                  <Clock className="w-3 h-3" strokeWidth={1.5} />
                  <span>T+{ev.tick}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                    <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-medium ${badgeBg}`}>
                      {ev.event_type}
                    </span>
                    {ev.entity_id && (
                      <span className="text-[var(--studio-text-primary)] font-semibold text-[10.5px]">
                        {ev.entity_id}
                      </span>
                    )}
                  </div>
                  {ev.payload && Object.keys(ev.payload).length > 0 && (
                    <div className="text-[var(--studio-text-secondary)] text-[10.5px] truncate">
                      {JSON.stringify(ev.payload)}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
