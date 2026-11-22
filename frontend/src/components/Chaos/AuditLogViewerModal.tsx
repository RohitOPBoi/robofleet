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
    if (isAuditLogOpen) {
      loadLogs();
    }
  }, [isAuditLogOpen, roleFilter]);

  if (!isAuditLogOpen) return null;

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl max-h-[90vh] bg-gray-950 border border-white/15 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-gray-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-gradient-to-r from-emerald-950/40 via-gray-900 to-gray-950">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">Immutable Audit Ledger</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  SQLITE APPEND-ONLY
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Cryptographically protected, trigger-enforced immutable record of all supervisor overrides & chaos actions
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleExportCsv}
              className="px-3 py-1.5 rounded-xl bg-gray-900 hover:bg-gray-800 border border-white/10 text-emerald-400 text-xs font-semibold flex items-center gap-1.5 transition active:scale-95 cursor-pointer"
              title="Download append-only audit trail as CSV"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
            <button
              type="button"
              onClick={() => setStore({ isAuditLogOpen: false })}
              className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="px-6 py-3 border-b border-white/5 bg-gray-900/40 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative w-full">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search audit actions, targets, reasons..."
                className="w-full bg-gray-950 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-gray-400 text-xs">Role:</span>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="bg-gray-950 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-emerald-500"
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
              className="p-2 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-300 border border-white/10 transition active:scale-95 cursor-pointer"
              title="Refresh Audit Logs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-20">
              <FileSpreadsheet className="w-10 h-10 text-gray-500 mx-auto mb-2 opacity-60" />
              <p className="text-sm font-semibold text-gray-400">No Audit Entries Recorded</p>
              <p className="text-xs text-gray-500 mt-1">Actions performed by supervisors or chaos injections will appear here.</p>
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead className="bg-gray-900/90 sticky top-0 border-b border-white/10 text-gray-400 text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">TIMESTAMP</th>
                  <th className="py-2.5 px-4 font-semibold">ROLE</th>
                  <th className="py-2.5 px-4 font-semibold">ACTION TYPE</th>
                  <th className="py-2.5 px-4 font-semibold">TARGET</th>
                  <th className="py-2.5 px-4 font-semibold">REASON / DETAILS</th>
                  <th className="py-2.5 px-4 font-semibold text-right">STATUS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredLogs.map((rawLog: any, idx: number) => {
                  const auditId = rawLog.audit_id || `AUD-${idx}`;
                  const timestampStr = rawLog.timestamp_iso || rawLog.timestamp || `Tick ${rawLog.tick ?? 0}`;
                  const actorRole = rawLog.role || rawLog.actor_role || "supervisor";
                  const actionType = rawLog.action || rawLog.action_type || "action";
                  const targetId = rawLog.entity_id || rawLog.target_id || "—";
                  const reasonStr = rawLog.reason || rawLog.rejection_reason || "Normal operation";
                  const isApproved = rawLog.result ? rawLog.result === "SUCCESS" : Boolean(rawLog.approved);

                  return (
                    <tr key={auditId} className="hover:bg-white/[0.02] transition">
                      <td className="py-2.5 px-4 text-gray-400 text-[11px] whitespace-nowrap">
                        {timestampStr.length > 19 ? timestampStr.substring(11, 19) : timestampStr}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-white/5 text-gray-200 border border-white/10 uppercase">
                          {actorRole}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-cyan-300 whitespace-nowrap">
                        {actionType}
                      </td>
                      <td className="py-2.5 px-4 text-gray-300 whitespace-nowrap">
                        {targetId}
                      </td>
                      <td className="py-2.5 px-4 text-gray-300 font-sans text-xs max-w-xs truncate" title={reasonStr}>
                        {reasonStr}
                      </td>
                      <td className="py-2.5 px-4 text-right whitespace-nowrap">
                        {isApproved ? (
                          <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px] font-bold">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Approved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-400 text-[11px] font-bold">
                            <XCircle className="w-3.5 h-3.5" /> Rejected
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
        <div className="px-6 py-3 border-t border-white/10 bg-gray-950/80 flex items-center justify-between text-xs text-gray-400 font-mono">
          <span>{filteredLogs.length} audit records in runs/audit.db (Trigger protected against UPDATE/DELETE)</span>
          <button
            type="button"
            onClick={() => setStore({ isAuditLogOpen: false })}
            className="px-4 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-200 border border-white/10 text-xs font-semibold cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
