import React from "react";
import { CheckCircle2, Cpu, Database, Info, Layers, ShieldCheck, X } from "lucide-react";
import { setStore, useStore } from "../store/useStore";

export const EnvironmentModal: React.FC = () => {
  const { isEnvironmentModalOpen, environmentDisclosure, staticWorld } = useStore();

  if (!isEnvironmentModalOpen) return null;

  const mode = environmentDisclosure?.mode || "digital_twin";
  const dataSource = environmentDisclosure?.data_source || "Synthetic Demand Engine";
  const robotLayer = environmentDisclosure?.robot_layer || "simulated";
  const seed = environmentDisclosure?.seed ?? staticWorld?.meta.seed ?? 42;
  const schemaVersion = environmentDisclosure?.schema_version || "1.0.0";
  const scenario = environmentDisclosure?.scenario || staticWorld?.meta.scenario_name || "standard";
  const activeOverlays = environmentDisclosure?.active_overlays || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200 select-none">
      <div className="bg-gray-900 border border-gray-800 rounded-xl max-w-lg w-full shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between bg-gray-950/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-950 text-emerald-400 border border-emerald-800/80">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Environment Disclosure</h2>
              <p className="text-xs text-gray-400">Single disclosure surface (P2-A9 / SR-9)</p>
            </div>
          </div>
          <button
            onClick={() => setStore({ isEnvironmentModalOpen: false })}
            className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4 text-sm text-gray-300">
          <div className={`p-3 rounded-lg border flex items-start gap-3 ${
            mode === "recorded_run"
              ? "bg-cyan-950/40 border-cyan-800/60"
              : "bg-blue-950/30 border-blue-800/40"
          }`}>
            <Info className={`w-5 h-5 shrink-0 mt-0.5 ${mode === "recorded_run" ? "text-cyan-400" : "text-blue-400"}`} />
            <div className={`text-xs leading-relaxed ${mode === "recorded_run" ? "text-cyan-200" : "text-blue-200"}`}>
              {mode === "recorded_run" ? (
                <>
                  This deployment is running in <strong>Recorded Run</strong> (Historical Operations Replay) mode.
                  Simulation frames and decision timelines are being replayed bit-for-bit from an indexed artifact
                  without live non-deterministic execution.
                </>
              ) : (
                <>
                  This deployment is running in <strong>Digital Twin</strong> mode. All robotics kinetics, battery
                  discharge, warehouse layouts, and order arrivals are driven by mathematical models and simulated AMR
                  controllers.
                </>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-gray-950 border border-gray-800">
              <div className="flex items-center gap-1.5 text-gray-400 mb-1">
                <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-medium">Execution Mode</span>
              </div>
              <div className="font-mono text-emerald-400 font-semibold uppercase">{mode}</div>
            </div>

            <div className="p-3 rounded-lg bg-gray-950 border border-gray-800">
              <div className="flex items-center gap-1.5 text-gray-400 mb-1">
                <Database className="w-3.5 h-3.5 text-blue-400" />
                <span className="font-medium">Order Ingestion Adapter</span>
              </div>
              <div className="font-mono text-white font-semibold">{dataSource}</div>
            </div>

            <div className="p-3 rounded-lg bg-gray-950 border border-gray-800">
              <div className="flex items-center gap-1.5 text-gray-400 mb-1">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                <span className="font-medium">Robot Layer</span>
              </div>
              <div className="font-mono text-purple-400 font-semibold capitalize">{robotLayer}</div>
            </div>

            <div className="p-3 rounded-lg bg-gray-950 border border-gray-800">
              <div className="flex items-center gap-1.5 text-gray-400 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-medium">Deterministic Seed</span>
              </div>
              <div className="font-mono text-amber-400 font-semibold">{seed}</div>
            </div>
          </div>

          <div className="border-t border-gray-800 pt-3 text-xs space-y-2 font-mono">
            <div className="flex justify-between">
              <span className="text-gray-500">Scenario Name:</span>
              <span className="text-gray-200">{scenario}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Contract Schema Version:</span>
              <span className="text-gray-200">{schemaVersion}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Active Demand Overlays:</span>
              <span className="text-gray-200">
                {activeOverlays.length > 0 ? activeOverlays.join(", ") : "Standard Diurnal"}
              </span>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-gray-800 bg-gray-950/60 flex justify-end">
          <button
            onClick={() => setStore({ isEnvironmentModalOpen: false })}
            className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-white rounded-md text-xs font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
