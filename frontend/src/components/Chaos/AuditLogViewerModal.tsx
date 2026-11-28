import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Filter,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { fetchAuditLogs } from "../../services/api";
import { setStore, useStore } from "../../store/useStore";
import type { AuditEntry } from "../../types/generated";

export const AuditLogViewerModal: React.FC = () => {
  const store = useStore();
  const { isAuditLogOpen } = store;

  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await fetchAuditLogs(roleFilter || undefined, undefined, undefined, 200);
      setLogs(data);
    } catch (e) {
      console.warn("Failed to load audit logs:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAuditLogOpen) return;
    loadLogs();
  }, [isAuditLogOpen, roleFilter]);

  useEffect(() => {
    if (!isAuditLogOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setStore({ isAuditLogOpen: false });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isAuditLogOpen]);

  if (!isAuditLogOpen) return null;

  const handleClose = () => setStore({ isAuditLogOpen: false });

  const filteredLogs = logs.filter((rawLog: any) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    const action = String(rawLog.action || rawLog.action_type || "").toLowerCase();
    const role = String(rawLog.role || rawLog.actor_role || "").toLowerCase();
    const target = String(rawLog.entity_id || rawLog.target_id || "").toLowerCase();
    const reason = String(rawLog.reason || "").toLowerCase();
    return action.includes(q) || role.includes(q) || target.includes(q) || reason.includes(q);
  });

  const handleExportCsv = () => {
    window.open("/api/audit/export.csv", "_blank");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#191310]/65 backdrop-blur-md"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="audit-log-modal-title"
        className="studio-card-modal studio-enter relative w-full max-w-5xl max-h-[90vh] rounded-[20px] border border-[var(--studio-border-strong)] flex flex-col overflow-hidden"
        style={{
          background: "var(--studio-surface-elevated)",
          boxShadow: "var(--studio-shadow-hover)",
        }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between bg-studio-sage/[0.06]"
          style={{ borderColor: "var(--studio-border)" }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-studio-sage/15 border border-studio-sage/30 flex items-center justify-center text-[#1D6144] dark:text-emerald-300">
              <ShieldCheck className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2
                  id="audit-log-modal-title"
                  className="text-lg font-semibold tracking-tight"
                  style={{ color: "var(--studio-text-primary)" }}
                >
                  Immutable Audit Ledger
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-studio-sage/15 text-[#1D6144] dark:text-emerald-300 border border-studio-sage/30">
                  Append-only
                </span>
              </div>
              <p className="text-xs" style={{ color: "var(--studio-text-muted)" }}>
                Cryptographically protected, immutable record of all supervisor overrides & chaos actions
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleExportCsv}
              className="studio-btn px-3.5 py-1.5 rounded-xl bg-studio-sage/15 hover:bg-studio-sage/25 border border-studio-sage/30 text-[#1D6144] dark:text-emerald-300 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
              title="Download append-only audit trail as CSV"
            >
              <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span>Export CSV</span>
            </button>
            <button
              type="button"
              aria-label="Close audit log"
              onClick={handleClose}
              className="studio-btn p-2 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
            >
              <X className="w-5 h-5" strokeWidth={1.5} />
            </button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div
          className="px-6 py-3 border-b flex flex-wrap items-center justify-between gap-3 text-xs"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
          }}
        >
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative w-full">
              <Search
                className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                style={{ color: "var(--studio-text-muted)" }}
                strokeWidth={1.5}
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search audit actions, targets, reasons"
                aria-label="Search audit logs"
                className="w-full rounded-xl border pl-9 pr-8 py-2 text-xs focus:outline-none focus:border-studio-sage"
                style={{
                  background: "var(--studio-surface-elevated)",
                  borderColor: "var(--studio-border-strong)",
                  color: "var(--studio-text-primary)",
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  aria-label="Clear search"
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" strokeWidth={1.5} />
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5" style={{ color: "var(--studio-text-muted)" }} strokeWidth={1.5} />
            <label htmlFor="audit-role-filter" className="text-xs" style={{ color: "var(--studio-text-muted)" }}>
              Role:
            </label>
            <select
              id="audit-role-filter"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded-xl border px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:border-studio-sage"
              style={{
                background: "var(--studio-surface-elevated)",
                borderColor: "var(--studio-border-strong)",
                color: "var(--studio-text-primary)",
              }}
            >
              <option value="">All Roles</option>
              <option value="supervisor">Supervisor</option>
              <option value="admin">Admin</option>
              <option value="system">System / Engine</option>
            </select>

            <button
              type="button"
              onClick={loadLogs}
              disabled={loading}
              aria-label="Refresh audit logs"
              className="studio-btn p-2 rounded-xl border cursor-pointer disabled:opacity-50"
              style={{
                background: "var(--studio-surface-elevated)",
                borderColor: "var(--studio-border-strong)",
                color: "var(--studio-text-secondary)",
              }}
              title="Refresh Audit Logs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} strokeWidth={1.5} />
            </button>
          </div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-20">
              <FileSpreadsheet
                className="w-10 h-10 mx-auto mb-2 opacity-60"
                style={{ color: "var(--studio-text-muted)" }}
                strokeWidth={1.5}
              />
              <p className="text-sm font-semibold" style={{ color: "var(--studio-text-secondary)" }}>
                No Audit Entries Recorded
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--studio-text-muted)" }}>
                Actions performed by supervisors or chaos injections will appear here.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse font-mono tabular-nums">
              <thead
                className="sticky top-0 border-b text-[11px]"
                style={{
                  background: "var(--studio-surface-elevated)",
                  borderColor: "var(--studio-border)",
                  color: "var(--studio-text-muted)",
                }}
              >
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Timestamp</th>
                  <th className="py-2.5 px-4 font-semibold">Role</th>
                  <th className="py-2.5 px-4 font-semibold">Action type</th>
                  <th className="py-2.5 px-4 font-semibold">Target</th>
                  <th className="py-2.5 px-4 font-semibold">Reason / details</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--studio-border)]">
                {filteredLogs.map((rawLog: any, idx: number) => {
                  const auditId = rawLog.audit_id || `AUD-${idx}`;
                  const timestampStr = rawLog.timestamp_iso || rawLog.timestamp || `Tick ${rawLog.tick ?? 0}`;
                  const actorRole = rawLog.role || rawLog.actor_role || "supervisor";
                  const actionType = rawLog.action || rawLog.action_type || "action";
                  const targetId = rawLog.entity_id || rawLog.target_id || "—";
                  const reasonStr = rawLog.reason || rawLog.rejection_reason || "Normal operation";
                  const isApproved = rawLog.result ? rawLog.result === "SUCCESS" : Boolean(rawLog.approved);

                  return (
                    <tr
                      key={auditId}
                      className="transition-colors duration-150 hover:bg-studio-sand-deep/15 dark:hover:bg-white/[0.03]"
                    >
                      <td
                        className="py-2.5 px-4 text-[11px] whitespace-nowrap"
                        style={{ color: "var(--studio-text-muted)" }}
                      >
                        {timestampStr.length > 19 ? timestampStr.substring(11, 19) : timestampStr}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span
                          className="px-2 py-0.5 rounded-md text-[10px] font-semibold border capitalize"
                          style={{
                            background: "var(--studio-surface-subtle)",
                            borderColor: "var(--studio-border)",
                            color: "var(--studio-text-secondary)",
                          }}
                        >
                          {actorRole}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-[#A53420] dark:text-studio-coral whitespace-nowrap">
                        {actionType}
                      </td>
                      <td
                        className="py-2.5 px-4 whitespace-nowrap"
                        style={{ color: "var(--studio-text-primary)" }}
                      >
                        {targetId}
                      </td>
                      <td
                        className="py-2.5 px-4 font-sans text-xs max-w-xs truncate"
                        style={{ color: "var(--studio-text-secondary)" }}
                        title={reasonStr}
                      >
                        {reasonStr}
                      </td>
                      <td className="py-2.5 px-4 text-right whitespace-nowrap">
                        {isApproved ? (
                          <span className="inline-flex items-center gap-1 text-[#1D6144] dark:text-emerald-300 text-[11px] font-semibold">
                            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} /> Approved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[#9E2418] dark:text-red-400 text-[11px] font-semibold">
                            <XCircle className="w-3.5 h-3.5" strokeWidth={1.5} /> Rejected
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 py-3 border-t flex items-center justify-between text-xs font-mono tabular-nums"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
            color: "var(--studio-text-muted)",
          }}
        >
          <span>{filteredLogs.length} immutable audit records</span>
          <button
            type="button"
            onClick={handleClose}
            className="studio-btn px-4 py-1.5 rounded-xl border text-xs font-semibold font-sans cursor-pointer"
            style={{
              background: "var(--studio-surface-elevated)",
              borderColor: "var(--studio-border-strong)",
              color: "var(--studio-text-primary)",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
