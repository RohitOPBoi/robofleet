import React from "react";

export interface PanelConfig {
  id: string;
  title: string;
  position: "left" | "right" | "bottom" | "modal";
  defaultOpen: boolean;
  order: number;
  component: React.ComponentType<any>;
}

export class PanelRegistry {
  private panels: Map<string, PanelConfig> = new Map();

  register(config: PanelConfig) {
    this.panels.set(config.id, config);
  }

  get(id: string): PanelConfig | undefined {
    return this.panels.get(id);
  }

  list(position?: "left" | "right" | "bottom" | "modal"): PanelConfig[] {
    const all = Array.from(this.panels.values());
    const filtered = position ? all.filter((p) => p.position === position) : all;
    return filtered.sort((a, b) => a.order - b.order);
  }
}

export const defaultPanelRegistry = new PanelRegistry();
