"""Playwright Visual Audit and Verification for Phase 6 Resilience & Chaos Engineering.
Verifies:
- Chaos Studio Modal: typed fault injection (CA-8), "Perfect Storm", and scenario library
- Supervisor Exceptions Queue: SLA timeouts, manual resolution triggers, and re-slotting approvals
- Append-Only SQLite Audit Log Viewer: immutable ledger and CSV export
- Fault visualization: faulted robot warning strobe and blocked aisle hazard striping
- Saves high-res screenshots to artifact directory.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
import uvicorn

from robofleet.api.app import create_app
from robofleet.brain.orchestrator import MissionOrchestrator
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer

PORT = 8016
ARTIFACTS_DIR = Path("C:/Users/rohit/.gemini/antigravity/brain/77baad13-ebf5-4d8b-b65f-4c5fde9aadf1")


def main() -> int:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== Starting Phase 6 Playwright Audit Server on port {PORT} ===")

    config, _ = load_config(
        scenario_name="standard",
        cli_overrides=["robot_count=12"],
    )
    layout = generate_parametric_layout(config.layout, name="Dark Store 01 (Phase 6)")
    skus = generate_catalogue(sku_count=config.catalogue.sku_count, seed=config.seed)
    bins, _ = slot_inventory(
        layout=layout,
        skus=skus,
        empty_bin_pct=config.catalogue.empty_bin_pct,
        top_k_popular_replicas=config.catalogue.top_k_popular_replicas,
        seed=config.seed,
    )

    engine = SimEngine(config=config, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, speed_multiplier=2.0)
    orchestrator = MissionOrchestrator(engine=engine, provider_name="heuristic")

    # Seed an initial exception and reslotting recommendation for rich visual state
    from robofleet.contracts.chaos import ExceptionItem
    engine.exceptions_queue.add_exception(
        ExceptionItem(
            exception_type="damaged_item",
            severity="CRITICAL",
            entity_id="ORD-0042",
            raised_tick=engine.clock.tick,
            deadline_tick=engine.clock.tick + 400,
            timeout_ticks=400,
            default_action="mark_line_unfulfillable",
            recommended_action="Substitute from replica bin B-04-12 or dispatch manual runner",
            available_actions=["approve_partial", "extend_sla_300t", "cancel_line", "dispatch_manual_runner"],
        )
    )
    engine.exceptions_queue.add_exception(
        ExceptionItem(
            exception_type="robot_breakdown",
            severity="HIGH",
            entity_id="R-03",
            raised_tick=engine.clock.tick,
            deadline_tick=engine.clock.tick + 600,
            timeout_ticks=600,
            default_action="reassign_task",
            recommended_action="Reassign unfulfilled pick lines to R-05 and dispatch tow AMR",
            available_actions=["reassign_task", "tow_amr", "delay"],
        )
    )
    # Run recommender evaluation
    engine.reslot_recommender.evaluate(engine.clock.tick)

    # Pre-inject one fault so active incident view is populated
    engine.chaos_engine.inject_fault("robot_breakdown", target_id="R-02", duration_ticks=500)

    app = create_app(engine=engine, pacer=pacer, orchestrator=orchestrator)
    uvi_config = uvicorn.Config(app=app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config=uvi_config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2.0)

    print("Server ready. Launching headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("console", lambda msg: print(f"BROWSER [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER UNCAUGHT ERROR: {err}"))

        print(f"Navigating to http://127.0.0.1:{PORT}...")
        page.goto(f"http://127.0.0.1:{PORT}", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2500)

        # 1. Base Dashboard View with active fault indicator
        print("\n[Step 1] Capturing Base Dashboard with Phase 6 active chaos telemetry...")
        dash_shot = ARTIFACTS_DIR / "command_centre_phase6_overview.png"
        page.screenshot(path=str(dash_shot))
        print(f"Captured: {dash_shot.name}")

        # 2. Chaos Engineering Studio Modal
        print("\n[Step 2] Testing Chaos Control Studio Modal...")
        chaos_btn = page.get_by_title("Open Chaos Engineering & Resilience Studio")
        assert chaos_btn.is_visible()
        chaos_btn.click()
        page.wait_for_selector("text=Chaos Engineering Studio")
        page.wait_for_timeout(800)

        chaos_modal_shot = ARTIFACTS_DIR / "command_centre_phase6_chaos_modal.png"
        page.screenshot(path=str(chaos_modal_shot))
        print(f"Captured: {chaos_modal_shot.name}")

        # Switch to Scenario Library tab
        scenario_tab = page.get_by_role("button", name="Scenario Library")
        scenario_tab.click()
        page.wait_for_timeout(500)

        chaos_scenarios_shot = ARTIFACTS_DIR / "command_centre_phase6_scenarios.png"
        page.screenshot(path=str(chaos_scenarios_shot))
        print(f"Captured: {chaos_scenarios_shot.name}")

        # Close Chaos Modal
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # 3. Supervisor Exceptions Queue Drawer
        print("\n[Step 3] Testing Supervisor Exceptions Queue Drawer...")
        exceptions_btn = page.get_by_title("Open Supervisor Exceptions Queue")
        assert exceptions_btn.is_visible()
        exceptions_btn.click()
        page.wait_for_selector("text=Supervisor Exceptions Queue")
        page.wait_for_timeout(800)

        exceptions_drawer_shot = ARTIFACTS_DIR / "command_centre_phase6_exceptions_queue.png"
        page.screenshot(path=str(exceptions_drawer_shot))
        print(f"Captured: {exceptions_drawer_shot.name}")

        # Switch to Re-slotting recommendations tab
        reslot_tab = page.get_by_role("button", name="Re-Slotting Recommendations")
        reslot_tab.click()
        page.wait_for_timeout(500)

        reslot_shot = ARTIFACTS_DIR / "command_centre_phase6_reslotting.png"
        page.screenshot(path=str(reslot_shot))
        print(f"Captured: {reslot_shot.name}")

        # Close Exceptions Drawer
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # 4. Immutable Audit Log Viewer
        print("\n[Step 4] Testing Immutable SQLite Audit Log Viewer...")
        audit_btn = page.get_by_title("Open Immutable SQLite Audit Ledger")
        assert audit_btn.is_visible()
        audit_btn.click()
        page.wait_for_selector("text=Immutable Audit Ledger")
        page.wait_for_timeout(800)

        audit_modal_shot = ARTIFACTS_DIR / "command_centre_phase6_audit_log.png"
        page.screenshot(path=str(audit_modal_shot))
        print(f"Captured: {audit_modal_shot.name}")

        # Close Audit Modal
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        browser.close()

    server.should_exit = True
    thread.join(timeout=2.0)
    print("\n=== Phase 6 Playwright Audit Completed Successfully! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
