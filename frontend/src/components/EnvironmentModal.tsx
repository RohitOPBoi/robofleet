import React, { useEffect } from "react";
import { CheckCircle2, Cpu, Database, Info, Layers, ShieldCheck, X } from "lucide-react";
import { setStore, useStore } from "../store/useStore";

export const EnvironmentModal: React.FC = () => {
  const { isEnvironmentModalOpen, environmentDisclosure, staticWorld } = useStore();

  const handleClose = () => setStore({ isEnvironmentModalOpen: false });

  useEffect(() => {
    if (!isEnvironmentModalOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setStore({ isEnvironmentModalOpen: false });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isEnvironmentModalOpen]);

  if (!isEnvironmentModalOpen) return null;

  const mode = environmentDisclosure?.mode || "digital_twin";
  const dataSource = environmentDisclosure?.data_source || "Synthetic Demand Engine";
  const robotLayer = environmentDisclosure?.robot_layer || "simulated";
  const seed = environmentDisclosure?.seed ?? staticWorld?.meta.seed ?? 42;
  const schemaVersion = environmentDisclosure?.schema_version || "1.0.0";
  const scenario = environmentDisclosure?.scenario || staticWorld?.meta.scenario_name || "standard";
  const activeOverlays = environmentDisclosure?.active_overlays || [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191310]/65 backdrop-blur-md p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="environment-disclosure-title"
        className="studio-card-modal studio-enter rounded-[20px] border border-[var(--studio-border-strong)] max-w-lg w-full overflow-hidden"
        style={{
          background: "var(--studio-surface-elevated)",
          boxShadow: "var(--studio-shadow-hover)",
        }}
      >
        {/* Modal Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
          }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-studio-sage/15 border border-studio-sage/30 flex items-center justify-center text-[#1D6144] dark:text-emerald-300">
              <ShieldCheck className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div>
              <h2
                id="environment-disclosure-title"
                className="text-base font-semibold tracking-tight"
                style={{ color: "var(--studio-text-primary)" }}
              >
                Environment Disclosure
              </h2>
              <p className="text-xs" style={{ color: "var(--studio-text-muted)" }}>
                Runtime mode and simulation provenance
              </p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Dismiss modal"
            onClick={handleClose}
            className="studio-btn p-2 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
          >
            <X className="w-5 h-5" strokeWidth={1.5} />
          </button>
        </div>

        {/* Modal Body */}
        <div
          className="p-6 space-y-4 text-sm"
          style={{ color: "var(--studio-text-secondary)" }}
        >
          <div
            className={`p-3.5 rounded-2xl border flex items-start gap-3 ${
              mode === "recorded_run"
                ? "bg-studio-amber/10 border-studio-amber/25"
                : "bg-studio-sage/10 border-studio-sage/25"
            }`}
          >
            <Info
              className={`w-5 h-5 shrink-0 mt-0.5 ${
                mode === "recorded_run"
                  ? "text-[#8F4F0D] dark:text-amber-300"
                  : "text-[#1D6144] dark:text-emerald-300"
              }`}
              strokeWidth={1.5}
            />
            <div
              className="text-xs leading-relaxed"
              style={{ color: "var(--studio-text-primary)" }}
            >
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
            <div
              className="p-3.5 rounded-2xl border"
              style={{
                background: "var(--studio-surface-subtle)",
                borderColor: "var(--studio-border)",
              }}
            >
              <div
                className="flex items-center gap-1.5 mb-1.5"
                style={{ color: "var(--studio-text-muted)" }}
              >
                <Cpu className="w-3.5 h-3.5 text-[#1D6144] dark:text-emerald-300" strokeWidth={1.5} />
                <span className="font-medium">Execution Mode</span>
              </div>
              <div className="font-mono text-[#1D6144] dark:text-emerald-300 font-semibold capitalize">
                {mode.replace(/_/g, " ")}
              </div>
            </div>

            <div
              className="p-3.5 rounded-2xl border"
              style={{
                background: "var(--studio-surface-subtle)",
                borderColor: "var(--studio-border)",
              }}
            >
              <div
                className="flex items-center gap-1.5 mb-1.5"
                style={{ color: "var(--studio-text-muted)" }}
              >
                <Database className="w-3.5 h-3.5 text-[#A53420] dark:text-studio-coral" strokeWidth={1.5} />
                <span className="font-medium">Order Ingestion Adapter</span>
              </div>
              <div
                className="font-mono font-semibold"
                style={{ color: "var(--studio-text-primary)" }}
              >
                {dataSource}
              </div>
            </div>

            <div
              className="p-3.5 rounded-2xl border"
              style={{
                background: "var(--studio-surface-subtle)",
                borderColor: "var(--studio-border)",
              }}
            >
              <div
                className="flex items-center gap-1.5 mb-1.5"
                style={{ color: "var(--studio-text-muted)" }}
              >
                <Layers className="w-3.5 h-3.5 text-studio-ink-secondary dark:text-studio-sand-deep" strokeWidth={1.5} />
                <span className="font-medium">Robot Layer</span>
              </div>
              <div
                className="font-mono font-semibold capitalize"
                style={{ color: "var(--studio-text-primary)" }}
              >
                {robotLayer}
              </div>
            </div>

            <div
              className="p-3.5 rounded-2xl border"
              style={{
                background: "var(--studio-surface-subtle)",
                borderColor: "var(--studio-border)",
              }}
            >
              <div
                className="flex items-center gap-1.5 mb-1.5"
                style={{ color: "var(--studio-text-muted)" }}
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-[#8F4F0D] dark:text-amber-300" strokeWidth={1.5} />
                <span className="font-medium">Deterministic Seed</span>
              </div>
              <div className="font-mono text-[#8F4F0D] dark:text-amber-300 font-semibold tabular-nums">
                {seed}
              </div>
            </div>
          </div>

          <div
            className="border-t pt-3.5 text-xs space-y-2 font-mono tabular-nums"
            style={{ borderColor: "var(--studio-border)" }}
          >
            <div className="flex justify-between">
              <span style={{ color: "var(--studio-text-muted)" }}>Scenario Name:</span>
              <span style={{ color: "var(--studio-text-primary)" }}>{scenario}</span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: "var(--studio-text-muted)" }}>Contract Schema Version:</span>
              <span style={{ color: "var(--studio-text-primary)" }}>{schemaVersion}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="shrink-0" style={{ color: "var(--studio-text-muted)" }}>
                Active Demand Overlays:
              </span>
              <span className="text-right" style={{ color: "var(--studio-text-primary)" }}>
                {activeOverlays.length > 0 ? activeOverlays.join(", ") : "Standard Diurnal"}
              </span>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div
          className="px-6 py-3.5 border-t flex justify-end"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            className="studio-btn px-4 py-1.5 rounded-xl text-xs font-semibold border cursor-pointer"
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
