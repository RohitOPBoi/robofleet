import React, { useCallback, useEffect, useRef, useState } from "react";
import { ChevronUp, History, Pause, Play, RotateCcw, StepForward } from "lucide-react";
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
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [scrubTick, setScrubTick] = useState<number | null>(null);

  const timerRef = useRef<any>(null);
  const menuContainerRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const lastSeekTimeRef = useRef<number>(0);

  useEffect(() => {
    fetchReplayRecordings()
      .then((recs) => setAvailableRecordings(recs))
      .catch((err) => console.error("Failed to fetch recordings:", err));
  }, [isReplayMode]);

  useEffect(() => {
    if (!isRecordingsMenuOpen) return;
    const onPointerDown = (e: PointerEvent) => {
      if (menuContainerRef.current && !menuContainerRef.current.contains(e.target as Node)) {
        setIsRecordingsMenuOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setIsRecordingsMenuOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isRecordingsMenuOpen]);

  useEffect(() => {
    if (!tooltipBookmark) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setTooltipBookmark(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [tooltipBookmark]);

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

  const handleSeek = useCallback(async (targetTick: number) => {
    const clamped = Math.max(0, Math.min(replayTotalTicks, targetTick));
    try {
      const res = await seekReplayRecording(clamped);
      if (res && res.state) {
        applyReplayState(res.state);
      }
    } catch (err) {
      console.error("Seek error:", err);
    }
  }, [replayTotalTicks]);

  const getTickFromClientX = useCallback(
    (clientX: number): number => {
      if (!trackRef.current || replayTotalTicks <= 0) return 0;
      const rect = trackRef.current.getBoundingClientRect();
      if (rect.width <= 0) return 0;
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.round(ratio * replayTotalTicks);
    },
    [replayTotalTicks]
  );

  useEffect(() => {
    if (!isScrubbing) return;
    const onPointerMove = (e: PointerEvent) => {
      const targetTick = getTickFromClientX(e.clientX);
      setScrubTick(targetTick);
      const now = performance.now();
      if (now - lastSeekTimeRef.current > 60) {
        lastSeekTimeRef.current = now;
        handleSeek(targetTick);
      }
    };
    const onPointerUp = (e: PointerEvent) => {
      const finalTick = getTickFromClientX(e.clientX);
      setIsScrubbing(false);
      setScrubTick(null);
      handleSeek(finalTick);
    };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    };
  }, [isScrubbing, getTickFromClientX, handleSeek]);

  const handleStepOne = async () => {
    try {
      const res = await stepReplayRecording();
      if (res && res.state) {
        applyReplayState(res.state);
      }
    } catch (err) {
      console.error("Replay step error:", err);
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
      <div className="absolute bottom-3 right-3 z-30 flex items-center gap-2">
        <div ref={menuContainerRef} className="relative">
          <button
            type="button"
            aria-expanded={isRecordingsMenuOpen}
            aria-haspopup="menu"
            onClick={() => setIsRecordingsMenuOpen(!isRecordingsMenuOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--studio-surface-elevated)] hover:border-studio-terracotta/40 text-[var(--studio-text-primary)] border border-[var(--studio-border-strong)] backdrop-blur-xl text-xs font-medium cursor-pointer studio-btn"
            style={{ boxShadow: "var(--studio-shadow)" }}
            title="Load an archived operations recording for timeline inspection"
          >
            <History className="w-3.5 h-3.5 text-[#A53420] dark:text-studio-coral" strokeWidth={1.5} />
            <span>Replay Run</span>
            <ChevronUp
              className={`w-3.5 h-3.5 text-[var(--studio-text-muted)] transition-transform duration-200 ease-[var(--ease-out)] ${
                isRecordingsMenuOpen ? "rotate-180" : ""
              }`}
              strokeWidth={1.5}
            />
          </button>

          {isRecordingsMenuOpen && (
            <div
              className="absolute bottom-full mb-2 right-0 w-64 z-40"
              style={{ transformOrigin: "bottom right" }}
            >
              <div
                role="menu"
                className="studio-enter bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] rounded-2xl p-2 backdrop-blur-xl"
                style={{ boxShadow: "var(--studio-shadow-hover)" }}
              >
                <div className="text-[11px] font-medium text-[var(--studio-text-secondary)] px-2.5 py-1.5 border-b border-[var(--studio-border)] flex items-center justify-between">
                  <span>Select recording</span>
                  <span className="text-[10.5px] font-medium text-[#1D6144] dark:text-emerald-300">
                    Offline safe
                  </span>
                </div>
                <div className="max-h-48 overflow-y-auto mt-1.5 space-y-1">
                  {availableRecordings.length === 0 ? (
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => handleStartGoldenDemo("demo_golden_run")}
                      className="w-full text-left p-2 rounded-xl hover:bg-stone-900/[0.05] dark:hover:bg-white/[0.08] text-xs text-[var(--studio-text-primary)] flex flex-col cursor-pointer transition-colors duration-150"
                    >
                      <span className="font-semibold text-[#A53420] dark:text-studio-coral">
                        demo_golden_run
                      </span>
                      <span className="text-[11px] text-[var(--studio-text-muted)]">
                        Default stage golden run
                      </span>
                    </button>
                  ) : (
                    availableRecordings.map((rec) => (
                      <button
                        key={rec.id}
                        type="button"
                        role="menuitem"
                        onClick={() => handleStartGoldenDemo(rec.id)}
                        className="w-full text-left p-2 rounded-xl hover:bg-stone-900/[0.05] dark:hover:bg-white/[0.08] text-xs text-[var(--studio-text-primary)] flex flex-col cursor-pointer transition-colors duration-150"
                      >
                        <span className="font-semibold">{rec.id}</span>
                        <span className="text-[11px] text-[var(--studio-text-muted)] tabular-nums">
                          {rec.total_ticks || 250} ticks · {rec.bookmarks_count || 5} bookmarks
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  const displayTick = scrubTick ?? tick;
  const progressRatio =
    replayTotalTicks > 0 ? Math.min(1, Math.max(0, displayTick / replayTotalTicks)) : 0;
  const progressPct = progressRatio * 100;
  const currentSec = Math.floor(displayTick / 10);
  const totalSec = Math.floor(replayTotalTicks / 10);
  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const handleSliderKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    let nextTick: number | null = null;
    const step = e.shiftKey ? 10 : 1;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      nextTick = Math.max(0, displayTick - step);
    } else if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      nextTick = Math.min(replayTotalTicks, displayTick + step);
    } else if (e.key === "PageDown") {
      nextTick = Math.max(0, displayTick - 25);
    } else if (e.key === "PageUp") {
      nextTick = Math.min(replayTotalTicks, displayTick + 25);
    } else if (e.key === "Home") {
      nextTick = 0;
    } else if (e.key === "End") {
      nextTick = replayTotalTicks;
    }
    if (nextTick !== null) {
      e.preventDefault();
      handleSeek(nextTick);
    }
  };

  return (
    <div className="absolute bottom-4 left-6 right-6 z-30 studio-enter">
      <div
        className="bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] rounded-2xl backdrop-blur-xl p-3.5 px-5 flex flex-col gap-3 text-[var(--studio-text-primary)]"
        style={{ boxShadow: "var(--studio-shadow-hover)" }}
      >
        {/* Top Header Row of Replay Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <span className="px-2 py-0.5 rounded-full bg-studio-terracotta/12 text-[#A53420] dark:bg-studio-terracotta/20 dark:text-studio-coral font-medium text-[11px] border border-studio-terracotta/25 flex items-center gap-1.5 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--studio-accent-solid)]" />
              <span>Recorded run</span>
            </span>
            <span className="font-semibold text-[var(--studio-text-primary)] truncate">
              {replayRecordingId}
            </span>
            <span className="text-[var(--studio-text-muted)]">·</span>
            <span className="text-[var(--studio-text-secondary)] font-mono text-[11px] tabular-nums shrink-0">
              {formatTime(currentSec)} / {formatTime(totalSec)} (Tick {displayTick}/{replayTotalTicks})
            </span>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {/* Speed Multiplier Pill */}
            <div className="flex items-center bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] rounded-xl p-0.5 text-[11px] font-mono tabular-nums">
              {[0.5, 1.0, 2.0, 5.0].map((spd) => (
                <button
                  key={spd}
                  type="button"
                  onClick={() => setStore({ replaySpeedMultiplier: spd })}
                  className={`px-2 py-1 rounded-lg cursor-pointer transition-colors duration-150 ${
                    replaySpeedMultiplier === spd
                      ? "bg-[#1C1917] text-white dark:bg-[#FFFBF8] dark:text-[#1C1917] font-semibold shadow-sm"
                      : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
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
              className="px-3 py-1.5 rounded-xl bg-stone-900/[0.05] hover:bg-red-600/12 dark:bg-white/[0.08] dark:hover:bg-red-500/20 text-[var(--studio-text-primary)] hover:text-[#9E2418] dark:hover:text-red-300 border border-[var(--studio-border)] hover:border-red-700/25 text-xs font-medium cursor-pointer studio-btn"
            >
              Exit Replay
            </button>
          </div>
        </div>

        {/* Timeline Track with Scrub Handle and Bookmarks */}
        <div className="relative w-full h-7 flex items-center">
          {/* Background Bar */}
          <div
            ref={trackRef}
            role="slider"
            tabIndex={0}
            aria-label="Replay timeline scrubber"
            aria-valuemin={0}
            aria-valuemax={replayTotalTicks}
            aria-valuenow={displayTick}
            aria-valuetext={`Tick ${displayTick} of ${replayTotalTicks}`}
            onKeyDown={handleSliderKeyDown}
            onPointerDown={(e) => {
              if (e.button !== 0 && e.pointerType === "mouse") return;
              e.currentTarget.focus();
              const targetTick = getTickFromClientX(e.clientX);
              setIsScrubbing(true);
              setScrubTick(targetTick);
              lastSeekTimeRef.current = performance.now();
              handleSeek(targetTick);
            }}
            className="w-full h-2.5 bg-stone-900/10 dark:bg-white/10 rounded-full relative cursor-pointer overflow-visible touch-none"
          >
            {/* Progress Fill */}
            <div className="w-full h-full rounded-full overflow-hidden">
              <div
                style={{
                  transform: `scaleX(${progressRatio})`,
                  transition: isScrubbing ? "none" : undefined,
                }}
                className="w-full h-full rounded-full origin-left transform transition-transform duration-300 ease-[var(--ease-out)] bg-[var(--studio-accent-solid)]"
              />
            </div>

            {/* Draggable Scrubber Head */}
            <div
              style={{ left: `${progressPct}%` }}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-2 border-[#D9533B] shadow-md cursor-grab active:cursor-grabbing [@media(hover:hover)_and_(pointer:fine)]:motion-safe:hover:scale-110 transition-transform duration-150 ease-[var(--ease-out)] pointer-events-none"
            />

            {/* Bookmarks Overlay */}
            {replayBookmarks.map((bm, idx) => {
              const bmPct = replayTotalTicks > 0 ? (bm.tick / replayTotalTicks) * 100 : 0;
              const isAlertOrFault = bm.type === "alert" || bm.type === "fault";
              return (
                <button
                  key={`${bm.tick}-${idx}`}
                  type="button"
                  style={{ left: `${bmPct}%` }}
                  onPointerDown={(e) => e.stopPropagation()}
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
                  className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-studio-porcelain dark:border-studio-espresso shadow-sm transition-transform duration-150 ease-[var(--ease-out)] [@media(hover:hover)_and_(pointer:fine)]:motion-safe:hover:scale-125 cursor-pointer z-10 ${
                    isAlertOrFault
                      ? "bg-[#B4691E] dark:bg-amber-400"
                      : "bg-[#2E7D5B] dark:bg-emerald-400"
                  }`}
                  title={`${bm.title} (Tick ${bm.tick})`}
                  aria-label={`Jump to bookmark: ${bm.title} at tick ${bm.tick}`}
                />
              );
            })}
          </div>
        </div>

        {/* Bottom Playback Transport Controls */}
        <div className="flex items-center justify-between text-xs text-[var(--studio-text-secondary)]">
          <div className="flex items-center gap-2">
            {/* Play/Pause Button */}
            <button
              type="button"
              onClick={() => setStore({ isReplaying: !isReplaying })}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[var(--studio-accent-solid)] hover:bg-[var(--studio-accent-hover)] text-white font-semibold shadow-sm cursor-pointer studio-btn"
            >
              {isReplaying ? (
                <>
                  <Pause className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>Play</span>
                </>
              )}
            </button>

            {/* Step 1 Tick Button */}
            <button
              type="button"
              onClick={handleStepOne}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-stone-900/[0.05] hover:bg-stone-900/[0.09] dark:bg-white/[0.08] dark:hover:bg-white/[0.14] text-[var(--studio-text-primary)] border border-[var(--studio-border)] cursor-pointer font-medium studio-btn"
              title="Advance exactly 1 tick"
            >
              <StepForward className="w-3.5 h-3.5 text-[var(--studio-text-secondary)]" strokeWidth={1.5} />
              <span>Step +1</span>
            </button>

            {/* Jump to Start */}
            <button
              type="button"
              onClick={() => handleSeek(0)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-stone-900/[0.05] hover:bg-stone-900/[0.09] dark:bg-white/[0.08] dark:hover:bg-white/[0.14] text-[var(--studio-text-primary)] border border-[var(--studio-border)] cursor-pointer font-medium studio-btn"
              title="Jump to beginning"
            >
              <RotateCcw className="w-3.5 h-3.5 text-[var(--studio-text-secondary)]" strokeWidth={1.5} />
              <span>Rewind</span>
            </button>
          </div>

          <div className="flex items-center gap-3 text-[11px] text-[var(--studio-text-secondary)]">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#B4691E] dark:bg-amber-400 inline-block" />
              <span>Fault / Alert</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#2E7D5B] dark:bg-emerald-400 inline-block" />
              <span>AI Decision</span>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Hover Tooltip for Bookmarks */}
      {tooltipBookmark && (
        <div
          style={{ left: `${tooltipBookmark.x}px` }}
          className="fixed bottom-28 -translate-x-1/2 pointer-events-none z-50"
        >
          <div
            style={{ boxShadow: "var(--studio-shadow-hover)" }}
            className="studio-enter bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] rounded-xl p-2.5 max-w-xs text-xs backdrop-blur-xl"
          >
            <div className="font-semibold text-[#A53420] dark:text-studio-coral flex items-center justify-between gap-2">
              <span>{tooltipBookmark.title}</span>
              <span className="font-mono text-[10.5px] text-[var(--studio-text-muted)] tabular-nums shrink-0">
                Tick {tooltipBookmark.tick}
              </span>
            </div>
            {tooltipBookmark.description && (
              <p className="text-[11px] text-[var(--studio-text-secondary)] mt-1 line-clamp-3 leading-snug">
                {tooltipBookmark.description}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
