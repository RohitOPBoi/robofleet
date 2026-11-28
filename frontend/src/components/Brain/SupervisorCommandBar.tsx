import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CornerDownLeft,
  Loader2,
  MessageSquareText,
  Terminal,
  X,
} from "lucide-react";
import type { SupervisorQuery } from "../../types/generated";
import { sendSupervisorCommand } from "../../services/api";
import { setStore, useStore } from "../../store/useStore";

export const SupervisorCommandBar: React.FC = () => {
  const store = useStore();
  const { isSupervisorBarOpen, orders, robots, heldZones } = store;
  const [input, setInput] = useState<string>("");
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastQuery, setLastQuery] = useState<SupervisorQuery | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<SupervisorQuery | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isSupervisorBarOpen) {
      setErrorBanner(null);
      inputRef.current?.focus();
    }
  }, [isSupervisorBarOpen]);

  const quickActions = useMemo(() => {
    const orderList = Object.values(orders || {});
    const sampleOrderId = orderList.find((o) => o.at_risk)?.id || orderList[0]?.id || "ORD-001";
    const robotList = Object.values(robots || {});
    const sampleRobotId =
      robotList.find((r) => r.battery_percent < 40)?.id || robotList[0]?.id || "R-002";
    const sampleZoneId = heldZones?.[0] || "aisle_zone_1";

    return [
      "prioritise urgent orders",
      `hold zone ${sampleZoneId}`,
      `release zone ${sampleZoneId}`,
      `why is order ${sampleOrderId} late?`,
      "how many robots are moving?",
      `send robot ${sampleRobotId} to charge`,
    ];
  }, [orders, robots, heldZones]);

  if (!isSupervisorBarOpen) return null;

  const closeBar = () => setStore({ isSupervisorBarOpen: false });

  const handleSubmit = async (overrideText?: string, confirm = false) => {
    const textToSend = (overrideText ?? input).trim();
    if (!textToSend || loading) return;

    setLoading(true);
    setErrorBanner(null);
    try {
      const res: SupervisorQuery = await sendSupervisorCommand(textToSend, confirm);
      setLastQuery(res);
      if (res.requires_confirmation && !confirm && res.parsed_command) {
        setPendingConfirmation(res);
      } else {
        setPendingConfirmation(null);
      }
      setHistory((prev) => [textToSend, ...prev.filter((h) => h !== textToSend)].slice(0, 20));
      setHistoryIndex(-1);
      if (!confirm) {
        setInput("");
      }
    } catch (e: any) {
      console.error("Supervisor command failed:", e);
      setErrorBanner(e?.message || "Failed to process supervisor command.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSubmit();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (history.length > 0 && historyIndex < history.length - 1) {
        const nextIndex = historyIndex + 1;
        setHistoryIndex(nextIndex);
        setInput(history[nextIndex]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIndex > 0) {
        const nextIndex = historyIndex - 1;
        setHistoryIndex(nextIndex);
        setInput(history[nextIndex]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInput("");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-[#191310]/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) closeBar();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          closeBar();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="supervisor-command-bar-title"
        className="studio-card-modal bg-[#FFFBF8] dark:bg-[#241B16] border border-[var(--studio-border-strong)] shadow-[var(--studio-shadow)] text-[var(--studio-text-primary)] rounded-[20px] w-full max-w-2xl max-h-[85vh] overflow-y-auto flex flex-col select-text"
      >
        <h2 id="supervisor-command-bar-title" className="sr-only">
          Supervisor command bar
        </h2>

        {/* Input Bar */}
        <div className="flex items-center px-4 py-3 border-b border-[var(--studio-border)] bg-[var(--studio-surface-subtle)]/55 gap-3 shrink-0">
          <Terminal className="w-5 h-5 text-[#B83B24] dark:text-[#E87454] shrink-0" strokeWidth={1.5} />
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            aria-label="Supervisor command or query"
            placeholder="Type supervisor command or query (e.g. 'prioritise urgent orders', 'hold zone A')"
            className="flex-1 px-2 py-1 rounded-[8px] border border-transparent bg-transparent text-sm text-[var(--studio-text-primary)] placeholder:text-[var(--studio-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D9533B]/40 focus:border-[#D9533B] transition-colors duration-150 font-sans"
            disabled={loading}
          />
          {loading ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-[#B83B24] dark:text-[#E87454] font-mono tabular-nums">
              <Loader2 className="w-3.5 h-3.5 motion-safe:animate-spin" strokeWidth={1.5} />
              <span>Processing...</span>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={!input.trim()}
              className="p-2 rounded-[10px] bg-[#C2432D] hover:bg-[#A93521] disabled:opacity-40 text-[#FFFBF8] transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed"
              title="Submit command (Enter)"
              aria-label="Submit supervisor command"
            >
              <CornerDownLeft className="w-4 h-4" strokeWidth={1.5} />
            </button>
          )}
          <button
            type="button"
            onClick={closeBar}
            className="p-2 rounded-[10px] text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)] transition-colors duration-150 cursor-pointer"
            aria-label="Close supervisor bar"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="px-4 py-2.5 bg-[var(--studio-surface-subtle)]/35 border-b border-[var(--studio-border)] flex items-center gap-1.5 overflow-x-auto text-xs shrink-0">
          <span className="text-[var(--studio-text-muted)] text-[11px] shrink-0 font-medium">
            Quick suggestions
          </span>
          {quickActions.map((action) => (
            <button
              key={action}
              type="button"
              disabled={loading}
              onClick={() => handleSubmit(action)}
              className="px-2.5 py-1 rounded-[8px] bg-[var(--studio-surface-elevated)] hover:border-[#D9533B]/45 hover:text-[#B83B24] dark:hover:text-[#E87454] text-[var(--studio-text-secondary)] border border-[var(--studio-border)] text-[11px] shrink-0 transition-colors duration-150 cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed"
            >
              {action}
            </button>
          ))}
        </div>

        {/* Error Banner */}
        {errorBanner && (
          <div
            role="alert"
            className="px-4 py-3 bg-[#B93829]/12 border-b border-[#B93829]/30 text-[#A32D20] dark:text-[#F28B7D] flex items-center justify-between gap-2 text-xs shrink-0"
          >
            <div className="flex items-center gap-2 min-w-0">
              <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
              <span className="break-words">{errorBanner}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorBanner(null)}
              className="p-1 rounded-[6px] hover:bg-[#B93829]/15 transition-colors duration-150 cursor-pointer shrink-0"
              aria-label="Dismiss error"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </div>
        )}

        {/* Confirmation Modal Area */}
        {pendingConfirmation && (
          <div className="p-4 bg-[#B4691E]/10 border-b border-[#B4691E]/25 flex flex-col gap-2.5 shrink-0">
            <div className="flex items-center gap-2 text-[#85470D] dark:text-amber-300 font-semibold text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
              <span>State-changing command confirmation required</span>
            </div>
            <p className="text-sm text-[var(--studio-text-primary)]">
              {pendingConfirmation.response_text}
            </p>
            {pendingConfirmation.parsed_command && (
              <div className="p-3 rounded-[12px] bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] font-mono text-[11px] text-[var(--studio-text-primary)] overflow-x-auto">
                {JSON.stringify(pendingConfirmation.parsed_command, null, 2)}
              </div>
            )}
            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                disabled={loading}
                onClick={() => {
                  setPendingConfirmation(null);
                  setErrorBanner(null);
                }}
                className="px-3 py-1.5 rounded-[10px] bg-[var(--studio-surface-elevated)] hover:bg-[var(--studio-surface-subtle)] border border-[var(--studio-border-strong)] text-[var(--studio-text-secondary)] text-xs font-medium transition-colors duration-150 cursor-pointer disabled:opacity-45"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => handleSubmit(pendingConfirmation.raw_text, true)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-[10px] bg-[#C2432D] hover:bg-[#A93521] text-[#FFFBF8] font-semibold text-xs transition-colors duration-150 cursor-pointer disabled:opacity-45"
              >
                <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                <span>Confirm &amp; execute</span>
              </button>
            </div>
          </div>
        )}

        {/* Result Area */}
        {lastQuery && (
          <div className="p-4 bg-[var(--studio-surface-subtle)]/30 flex flex-col gap-2.5">
            <div className="flex items-center justify-between text-xs font-mono text-[var(--studio-text-muted)]">
              <span className="flex items-center gap-1.5 text-[#B83B24] dark:text-[#E87454] font-semibold">
                <MessageSquareText className="w-3.5 h-3.5" strokeWidth={1.5} />
                <span>Response ({lastQuery.query_type})</span>
              </span>
              <span className="tabular-nums">T+{lastQuery.tick}</span>
            </div>

            <p className="text-sm text-[var(--studio-text-primary)] leading-relaxed font-sans bg-[var(--studio-surface-elevated)] p-3.5 rounded-[12px] border border-[var(--studio-border)]">
              {lastQuery.response_text}
            </p>

            {lastQuery.evidence_citations && lastQuery.evidence_citations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 text-[11px] mt-0.5">
                <span className="text-[var(--studio-text-muted)] font-medium">
                  Cited evidence
                </span>
                {lastQuery.evidence_citations.map((cite, cIdx) => (
                  <span
                    key={cIdx}
                    className="px-2 py-0.5 rounded-[8px] bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] border border-[var(--studio-border)] font-mono text-[10px]"
                  >
                    {cite}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
