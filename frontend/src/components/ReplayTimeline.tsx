import React, { useEffect, useRef, useState } from "react";
import {
  exitReplayMode,
  fetchReplayRecordings,
  loadReplayRecording,
  seekReplayRecording,
  stepReplayRecording,
} from "../services/api";
import { setStore, useStore } from "../store/useStore";

export const ReplayTimeline: React.FC = () => {
  const {
    isReplayMode,
    replayRecordingId,
    replayTotalTicks,
    replayBookmarks,
    isReplaying,
    replaySpeedMultiplier,
    tick,
  } = useStore();

  const [availableRecordings, setAvailableRecordings] = useState<any[]>([]);
  const [isRecordingsMenuOpen, setIsRecordingsMenuOpen] = useState(false);
  const [tooltipBookmark, setTooltipBookmark] = useState<{
    title: string;
    description: string;
    tick: number;
    x: number;
  } | null>(null);

  const timerRef = useRef<any>(null);

  useEffect(() => {
    fetchReplayRecordings()
      .then((recs) => setAvailableRecordings(recs))
      .catch((err) => console.error("Failed to fetch recordings:", err));
  }, [isReplayMode]);

  // Playback timer when isReplaying is true
  useEffect(() => {
    if (!isReplayMode || !isReplaying) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    const intervalMs = Math.max(20, Math.floor(100 / replaySpeedMultiplier));
    timerRef.current = setInterval(async () => {
      if (tick >= replayTotalTicks) {
        setStore({ isReplaying: false });
        if (timerRef.current) clearInterval(timerRef.current);
        return;
      }
      try {
        const res = await stepReplayRecording();
        if (res && res.state) {
          applyReplayState(res.state);
        }
      } catch (err) {
        console.error("Replay step error:", err);
      }
    }, intervalMs);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isReplayMode, isReplaying, tick, replayTotalTicks, replaySpeedMultiplier]);

  const applyReplayState = (state: any) => {
    const robotsMap: Record<string, any> = {};
    (state.robots || []).forEach((r: any) => {
      robotsMap[r.robot_id] = r;
    });

    const ordersMap: Record<string, any> = {};
    (state.orders || []).forEach((o: any) => {
      ordersMap[o.order_id] = o;
    });

    setStore({
      tick: state.tick,
      simTimeMs: state.sim_time_ms,
      robots: robotsMap,
      orders: ordersMap,
      alerts: state.alerts || [],
      kpis: state.kpis || {},
    });
  };

  const handleStartGoldenDemo = async (recId = "demo_golden_run") => {
    try {
      const res = await loadReplayRecording(recId);
      if (res && res.info) {
        setStore({
          isReplayMode: true,
          replayRecordingId: res.info.recording_id,
          replayTotalTicks: res.info.total_ticks,
          replayBookmarks: res.info.bookmarks || [],
          isReplaying: false,
          isPaused: true,
        });
        if (res.initial_state) {
          applyReplayState(res.initial_state);
        }
      }
      setIsRecordingsMenuOpen(false);
    } catch (err) {
      console.error("Failed to load golden run:", err);
    }
  };

  const handleSeek = async (targetTick: number) => {
    try {
      const res = await seekReplayRecording(targetTick);
      if (res && res.state) {
        applyReplayState(res.state);
      }
    } catch (err) {
      console.error("Seek error:", err);
    }
  };

  const handleExitReplay = async () => {
    try {
      await exitReplayMode();
      setStore({
        isReplayMode: false,
        replayRecordingId: null,
        isReplaying: false,
        isPaused: false,
      });
    } catch (err) {
      console.error("Exit replay error:", err);
    }
  };

  if (!isReplayMode) {
    return (
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2">
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsRecordingsMenuOpen(!isRecordingsMenuOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-900/90 hover:bg-gray-800 text-gray-300 hover:text-cyan-400 border border-gray-700/80 shadow-lg backdrop-blur-md text-xs font-semibold tracking-wide transition cursor-pointer"
            title="Load an offline recorded run for stage-safe demo"
          >
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>Replay Stage Demo</span>
            <span className="text-[10px] text-gray-500 font-mono">P7-A3</span>
          </button>

          {isRecordingsMenuOpen && (
            <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 w-64 bg-gray-900/95 border border-gray-700 rounded-xl shadow-2xl p-2 z-40 backdrop-blur-md">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2 py-1 border-b border-gray-800 flex justify-between">
                <span>Select Recording</span>
                <span className="text-cyan-400">Offline Safe</span>
              </div>
              <div className="max-h-48 overflow-y-auto mt-1 space-y-1">
                {availableRecordings.length === 0 ? (
                  <button
                    type="button"
                    onClick={() => handleStartGoldenDemo("demo_golden_run")}
                    className="w-full text-left p-2 rounded-lg hover:bg-gray-800 text-xs text-cyan-300 flex flex-col cursor-pointer"
                  >
                    <span className="font-semibold">demo_golden_run</span>
                    <span className="text-[10px] text-gray-400">Default Stage Golden Run</span>
                  </button>
                ) : (
                  availableRecordings.map((rec) => (
                    <button
                      key={rec.id}
                      type="button"
                      onClick={() => handleStartGoldenDemo(rec.id)}
                      className="w-full text-left p-2 rounded-lg hover:bg-gray-800 text-xs text-gray-200 hover:text-cyan-300 flex flex-col cursor-pointer transition"
                    >
                      <span className="font-semibold">{rec.id}</span>
                      <span className="text-[10px] text-gray-400">
                        {rec.total_ticks || 250} ticks • {rec.bookmarks_count || 5} bookmarks
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  const progressPct = replayTotalTicks > 0 ? Math.min(100, Math.max(0, (tick / replayTotalTicks) * 100)) : 0;
  const currentSec = Math.floor(tick / 10);
  const totalSec = Math.floor(replayTotalTicks / 10);
  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  return (
    <div className="absolute bottom-4 left-6 right-6 z-30">
      <div className="bg-gray-950/90 border border-cyan-500/40 rounded-2xl shadow-2xl backdrop-blur-xl p-3 px-5 flex flex-col gap-2.5">
        {/* Top Header Row of Replay Bar */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 font-mono text-[10px] border border-cyan-700/60 font-bold uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
              Recorded Run
            </span>
            <span className="font-semibold text-gray-200">{replayRecordingId}</span>
            <span className="text-gray-500">•</span>
            <span className="text-gray-400 font-mono text-[11px]">
              {formatTime(currentSec)} / {formatTime(totalSec)} (Tick {tick}/{replayTotalTicks})
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Speed Multiplier Pill */}
            <div className="flex items-center bg-gray-900 border border-gray-800 rounded-lg p-0.5 text-[11px] font-mono">
              {[0.5, 1.0, 2.0, 5.0].map((spd) => (
                <button
                  key={spd}
                  type="button"
                  onClick={() => setStore({ replaySpeedMultiplier: spd })}
                  className={`px-2 py-0.5 rounded-md transition cursor-pointer ${
                    replaySpeedMultiplier === spd
                      ? "bg-cyan-500 text-gray-950 font-bold shadow-sm"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>

            {/* Exit Replay Button */}
            <button
              type="button"
              onClick={handleExitReplay}
              className="px-2.5 py-1 rounded-lg bg-gray-800 hover:bg-rose-950 text-gray-300 hover:text-rose-300 border border-gray-700 hover:border-rose-700/60 text-xs font-medium transition cursor-pointer"
            >
              Exit Replay
            </button>
          </div>
        </div>

        {/* Timeline Track with Scrub Handle and Bookmarks */}
        <div className="relative w-full h-8 flex items-center">
          {/* Background Bar */}
          <div
            className="w-full h-2.5 bg-gray-800/80 rounded-full relative cursor-pointer overflow-visible"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              const ratio = Math.max(0, Math.min(1, clickX / rect.width));
              handleSeek(Math.round(ratio * replayTotalTicks));
            }}
          >
            {/* Progress Fill */}
            <div
              style={{ width: `${progressPct}%` }}
              className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 rounded-full relative"
            >
              {/* Draggable Scrubber Head */}
              <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-4 h-4 rounded-full bg-white border-2 border-cyan-400 shadow-md cursor-grab active:cursor-grabbing hover:scale-125 transition-transform" />
            </div>

            {/* Bookmarks Overlay */}
            {replayBookmarks.map((bm, idx) => {
              const bmPct = replayTotalTicks > 0 ? (bm.tick / replayTotalTicks) * 100 : 0;
              const isAlertOrFault = bm.type === "alert" || bm.type === "fault";
              return (
                <button
                  key={`${bm.tick}-${idx}`}
                  type="button"
                  style={{ left: `${bmPct}%` }}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSeek(bm.tick);
                  }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setTooltipBookmark({
                      title: bm.title,
                      description: bm.description,
                      tick: bm.tick,
                      x: rect.left + rect.width / 2,
                    });
                  }}
                  onMouseLeave={() => setTooltipBookmark(null)}
                  className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 transition-transform hover:scale-150 cursor-pointer z-10 ${
                    isAlertOrFault
                      ? "bg-amber-400 border-gray-950 shadow-amber-400/50 shadow-sm"
                      : "bg-purple-400 border-gray-950 shadow-purple-400/50 shadow-sm"
                  }`}
                  title={`${bm.title} (Tick ${bm.tick})`}
                />
              );
            })}
          </div>
        </div>

        {/* Bottom Playback Transport Controls */}
        <div className="flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-2">
            {/* Play/Pause Button */}
            <button
              type="button"
              onClick={() => setStore({ isReplaying: !isReplaying })}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-gray-950 font-bold transition shadow-sm cursor-pointer"
            >
              {isReplaying ? (
                <>
                  <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                    <rect x="6" y="4" width="4" height="16" />
                    <rect x="14" y="4" width="4" height="16" />
                  </svg>
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  <span>Play</span>
                </>
              )}
            </button>

            {/* Step 1 Tick Button */}
            <button
              type="button"
              onClick={() => stepReplayRecording()}
              className="px-2.5 py-1 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-300 border border-gray-800 transition cursor-pointer"
              title="Advance exactly 1 tick"
            >
              Step +1
            </button>

            {/* Jump to Start */}
            <button
              type="button"
              onClick={() => handleSeek(0)}
              className="px-2.5 py-1 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-300 border border-gray-800 transition cursor-pointer"
              title="Jump to beginning"
            >
              Rewind
            </button>
          </div>

          <div className="flex items-center gap-3 text-[11px]">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
              <span>Fault/Alert</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-400 inline-block" />
              <span>AI Decision</span>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Hover Tooltip for Bookmarks */}
      {tooltipBookmark && (
        <div
          style={{ left: `${tooltipBookmark.x}px` }}
          className="fixed bottom-28 -translate-x-1/2 bg-gray-900 border border-cyan-500/60 rounded-xl shadow-2xl p-2.5 max-w-xs text-xs pointer-events-none z-50 animate-fade-in"
        >
          <div className="font-bold text-cyan-300 flex items-center justify-between gap-2">
            <span>{tooltipBookmark.title}</span>
            <span className="font-mono text-[10px] text-gray-400">Tick {tooltipBookmark.tick}</span>
          </div>
          {tooltipBookmark.description && (
            <p className="text-[11px] text-gray-300 mt-1 line-clamp-3 leading-snug">
              {tooltipBookmark.description}
            </p>
          )}
        </div>
      )}
    </div>
  );
};
