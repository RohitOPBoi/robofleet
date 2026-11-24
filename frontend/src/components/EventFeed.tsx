import React from "react";
import { Clock } from "lucide-react";
import { useStore } from "../store/useStore";

export const EventFeed: React.FC = () => {
  const { recentEvents } = useStore();

  return (
    <div className="w-full h-full flex flex-col text-xs select-none overflow-hidden">
      {/* Events log */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 font-mono text-[11px] min-h-0">
        {recentEvents.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-500 py-8">
            Awaiting streaming events...
          </div>
        ) : (
          recentEvents.slice(0, 50).map((ev) => {
            let badgeBg = "bg-gray-800 text-gray-300";
            if (ev.event_type.startsWith("order")) badgeBg = "bg-blue-950 text-blue-400 border border-blue-800/60";
            else if (ev.event_type.startsWith("robot")) badgeBg = "bg-emerald-950 text-emerald-400 border border-emerald-800/60";
            else if (ev.event_type.startsWith("alert")) badgeBg = "bg-amber-950 text-amber-400 border border-amber-800/60";
            else if (ev.event_type.startsWith("command")) badgeBg = "bg-purple-950 text-purple-400 border border-purple-800/60";

            return (
              <div
                key={ev.event_id}
                className="p-1.5 rounded bg-gray-950/60 border border-gray-800/80 flex items-start gap-2 hover:bg-gray-950 transition"
              >
                <div className="flex items-center gap-1 text-gray-500 shrink-0 text-[10px] pt-0.5">
                  <Clock className="w-2.5 h-2.5" />
                  <span>T+{ev.tick}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={`px-1 py-0.2 rounded text-[10px] font-semibold ${badgeBg}`}>
                      {ev.event_type}
                    </span>
                    {ev.entity_id && <span className="text-gray-400 font-semibold">{ev.entity_id}</span>}
                  </div>
                  {ev.payload && Object.keys(ev.payload).length > 0 && (
                    <div className="text-gray-400 text-[10px] truncate">
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
