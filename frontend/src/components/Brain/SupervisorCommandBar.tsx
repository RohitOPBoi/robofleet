import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  CornerDownLeft,
  HelpCircle,
  MessageSquare,
  ShieldAlert,
  Sparkles,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import type { SupervisorQuery } from "../../types/generated";
import { sendSupervisorCommand } from "../../services/api";
import { setStore, useStore } from "../../store/useStore";

const QUICK_ACTIONS = [
  "prioritise urgent orders",
  "hold zone aisle_zone_1",
  "release zone aisle_zone_1",
  "why is order ORD-001 late?",
  "how many robots are moving?",
  "send robot R-002 to charge",
];

export const SupervisorCommandBar: React.FC = () => {
  const store = useStore();
  const { isSupervisorBarOpen } = store;
  const [input, setInput] = useState<string>("");
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastQuery, setLastQuery] = useState<SupervisorQuery | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<SupervisorQuery | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isSupervisorBarOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isSupervisorBarOpen]);

  if (!isSupervisorBarOpen) return null;

  const handleSubmit = async (overrideText?: string, confirm = false) => {
    const textToSend = (overrideText ?? input).trim();
    if (!textToSend || loading) return;

    setLoading(true);
    setPendingConfirmation(null);
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
      setInput("");
    } catch (e: any) {
      console.error("Supervisor command failed:", e);
      setLastQuery({
        query_id: "err",
        tick: store.tick,
        raw_text: textToSend,
        query_type: "command",
        requires_confirmation: false,
        response_text: `Error processing supervisor query: ${e.message || e}`,
        evidence_citations: ["System error"],
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSubmit();
    } else if (e.key === "ArrowUp") {
      if (history.length > 0 && historyIndex < history.length - 1) {
        const nextIndex = historyIndex + 1;
        setHistoryIndex(nextIndex);
        setInput(history[nextIndex]);
      }
    } else if (e.key === "ArrowDown") {
      if (historyIndex > 0) {
        const nextIndex = historyIndex - 1;
        setHistoryIndex(nextIndex);
        setInput(history[nextIndex]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInput("");
      }
    } else if (e.key === "Escape") {
      setStore({ isSupervisorBarOpen: false });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-gray-950 border border-gray-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Input Bar */}
        <div className="flex items-center px-4 py-3 border-b border-gray-800 bg-gray-900/80 gap-3">
          <Terminal className="w-5 h-5 text-indigo-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type supervisor command or query (e.g. 'prioritise urgent orders', 'hold zone A')..."
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 focus:outline-none font-sans"
            disabled={loading}
          />
          {loading ? (
            <span className="text-xs text-indigo-400 animate-pulse font-mono">Processing...</span>
          ) : (
            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={!input.trim()}
              className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white transition cursor-pointer active:scale-95"
              title="Submit command (Enter)"
            >
              <CornerDownLeft className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setStore({ isSupervisorBarOpen: false })}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="px-4 py-2 bg-gray-900/40 border-b border-gray-800/60 flex items-center gap-1.5 overflow-x-auto text-xs shrink-0">
          <span className="text-gray-500 text-[11px] shrink-0 font-medium">Quick Suggestions:</span>
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              onClick={() => handleSubmit(action)}
              className="px-2.5 py-1 rounded-full bg-gray-800/70 hover:bg-indigo-950/60 hover:text-indigo-300 text-gray-300 border border-gray-700/60 text-[11px] transition shrink-0 cursor-pointer active:scale-95"
            >
              {action}
            </button>
          ))}
        </div>

        {/* Confirmation Modal Area */}
        {pendingConfirmation && (
          <div className="p-4 bg-amber-950/40 border-b border-amber-800/80 flex flex-col gap-2.5 animate-in slide-in-from-top-2">
            <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-wider">
              <AlertCircle className="w-4 h-4 text-amber-400" />
              State-Changing Command Confirmation Required
            </div>
            <p className="text-sm text-gray-200">
              {pendingConfirmation.response_text}
            </p>
            {pendingConfirmation.parsed_command && (
              <div className="p-2 rounded bg-black/60 border border-amber-800/50 font-mono text-[11px] text-cyan-300 overflow-x-auto">
                {JSON.stringify(pendingConfirmation.parsed_command, null, 2)}
              </div>
            )}
            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setPendingConfirmation(null)}
                className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleSubmit(pendingConfirmation.raw_text, true)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs shadow-md shadow-amber-500/20 cursor-pointer active:scale-95"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Confirm & Execute</span>
              </button>
            </div>
          </div>
        )}

        {/* Result Area */}
        {lastQuery && (
          <div className="p-4 bg-gray-900/30 flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs font-mono text-gray-400">
              <span className="flex items-center gap-1.5 text-indigo-400 font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                Response ({lastQuery.query_type}):
              </span>
              <span>T+{lastQuery.tick}</span>
            </div>

            <p className="text-sm text-gray-100 leading-relaxed font-sans bg-gray-950 p-3 rounded-xl border border-gray-800">
              {lastQuery.response_text}
            </p>

            {lastQuery.evidence_citations && lastQuery.evidence_citations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 text-[11px] mt-1">
                <span className="text-gray-500 font-medium">Cited Evidence:</span>
                {lastQuery.evidence_citations.map((cite, cIdx) => (
                  <span
                    key={cIdx}
                    className="px-2 py-0.5 rounded bg-gray-800/90 text-gray-300 border border-gray-700/60 font-mono text-[10px]"
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
