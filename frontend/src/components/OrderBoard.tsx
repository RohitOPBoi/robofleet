import React, { useMemo, useState } from "react";
import { AlertCircle, CheckCircle, Clock, Package, Search } from "lucide-react";
import { setStore, useStore } from "../store/useStore";

export const OrderBoard: React.FC = () => {
  const { orders, tick, selectedOrderId } = useStore();
  const [activeTab, setActiveTab] = useState<"incoming" | "at_risk" | "all">("incoming");
  const [search, setSearch] = useState("");

  const orderList = useMemo(() => Object.values(orders), [orders]);

  const filteredOrders = useMemo(() => {
    let list = orderList;

    if (activeTab === "incoming") {
      list = list.filter((o) => o.status === "RECEIVED" || o.status === "QUEUED");
    } else if (activeTab === "at_risk") {
      list = list.filter((o) => o.at_risk);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((o) => o.id.toLowerCase().includes(q) || o.sla_tier.toLowerCase().includes(q));
    }

    // Sort: at-risk first, then by priority descending, then deadline ascending
    return list.sort((a, b) => {
      if (a.at_risk !== b.at_risk) return a.at_risk ? -1 : 1;
      if (b.priority !== a.priority) return b.priority - a.priority;
      return a.deadline_tick - b.deadline_tick;
    });
  }, [orderList, activeTab, search]);

  const atRiskCount = useMemo(() => orderList.filter((o) => o.at_risk).length, [orderList]);
  const incomingCount = useMemo(
    () => orderList.filter((o) => o.status === "RECEIVED" || o.status === "QUEUED").length,
    [orderList]
  );

  return (
    <div className="w-full h-full flex flex-col text-xs select-none overflow-hidden">
      {/* Board Header */}
      <div className="p-3 border-b border-gray-800 bg-gray-950/60 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 font-semibold text-white text-xs">
            <Package className="w-3.5 h-3.5 text-blue-400" />
            <span>Order board</span>
          </div>
          <span className="font-mono text-gray-400 text-[11px]">{filteredOrders.length} orders</span>
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ID or tier..."
            className="w-full bg-gray-900 border border-gray-800 rounded-md pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition"
          />
        </div>

        {/* Filter Tabs */}
        <div className="flex bg-gray-900 p-0.5 rounded-lg border border-gray-800 font-medium text-[11px]">
          <button
            type="button"
            onClick={() => setActiveTab("incoming")}
            className={`flex-1 py-1 rounded text-center transition flex items-center justify-center gap-1 cursor-pointer ${
              activeTab === "incoming" ? "bg-gray-800 text-white font-semibold shadow-sm" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <span>Incoming</span>
            <span className="px-1.5 py-0.2 rounded-full bg-gray-700 text-gray-300 text-[10px]">
              {incomingCount}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("at_risk")}
            className={`flex-1 py-1 rounded text-center transition flex items-center justify-center gap-1 cursor-pointer ${
              activeTab === "at_risk" ? "bg-red-950 text-red-300 font-semibold shadow-sm" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <span>At risk</span>
            {atRiskCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-red-800 text-white text-[10px]">
                {atRiskCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`flex-1 py-1 rounded text-center transition cursor-pointer ${
              activeTab === "all" ? "bg-gray-800 text-white font-semibold shadow-sm" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Orders List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        {filteredOrders.length === 0 ? (
          <div className="h-40 flex flex-col items-center justify-center text-gray-500 text-center px-4">
            <CheckCircle className="w-6 h-6 text-gray-600 mb-1" />
            <p className="font-medium text-gray-400 text-xs">No active orders</p>
            <p className="text-[10px] text-gray-500">Orders will appear as demand generates.</p>
          </div>
        ) : (
          filteredOrders.map((order) => {
            const isSelected = selectedOrderId === order.id;
            const remainingTicks = order.deadline_tick - tick;
            const remainingSecs = Math.max(0, Math.floor(remainingTicks / 10));
            const mins = Math.floor(remainingSecs / 60);
            const secs = remainingSecs % 60;
            const countdownStr = `${mins}m ${String(secs).padStart(2, "0")}s`;

            const totalDurationTicks = Math.max(1, order.deadline_tick - order.received_tick);
            const progressFraction = Math.max(0, Math.min(1, remainingTicks / totalDurationTicks));

            return (
              <div
                key={order.id}
                onClick={() => setStore({ selectedOrderId: isSelected ? null : order.id })}
                className={`p-2.5 rounded-lg border transition cursor-pointer select-none ${
                  isSelected
                    ? "bg-blue-950/40 border-blue-600 shadow-sm"
                    : order.at_risk
                    ? "bg-red-950/20 border-red-800/70 hover:border-red-600"
                    : "bg-gray-950/60 border-gray-800 hover:border-gray-700"
                }`}
              >
                {/* Order Top Line */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5 font-mono font-semibold text-gray-200 text-xs">
                    <span>{order.id}</span>
                    {order.at_risk && (
                      <span className="flex items-center gap-0.5 px-1 py-0.2 rounded bg-red-950 text-red-400 border border-red-800 text-[10px] font-bold">
                        <AlertCircle className="w-2.5 h-2.5" />
                        AT RISK
                      </span>
                    )}
                  </div>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                      order.sla_tier === "express"
                        ? "bg-purple-950 text-purple-400 border border-purple-800"
                        : "bg-gray-800 text-gray-400"
                    }`}
                  >
                    {order.sla_tier}
                  </span>
                </div>

                {/* SLA Deadline Bar */}
                <div className="mt-1.5 mb-1">
                  <div className="flex justify-between items-center text-[10px] text-gray-400 mb-0.5">
                    <span className="flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" /> SLA deadline:
                    </span>
                    <span
                      className={`font-mono font-semibold ${
                        order.at_risk ? "text-red-400" : "text-gray-300"
                      }`}
                    >
                      {countdownStr}
                    </span>
                  </div>
                  <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        order.at_risk ? "bg-red-500" : "bg-blue-500"
                      }`}
                      style={{ width: `${progressFraction * 100}%` }}
                    />
                  </div>
                </div>

                {/* SKU count & Status */}
                <div className="flex items-center justify-between text-[10px] text-gray-500 pt-1 border-t border-gray-900">
                  <span>{order.lines?.length || 0} line items</span>
                  <span className="font-mono text-gray-400 capitalize">{order.status.toLowerCase()}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
