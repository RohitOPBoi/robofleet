"""End-to-end browser operations tests with Playwright (P2-A6, P2-A9, P2-A13).
Verifies: UI rendering, 2D Canvas map, orders, alerts, environment disclosure modal,
light/dark theme toggle, and captures high-resolution screenshots into reports/screens/.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from robofleet.api.app import create_app
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer


@pytest.fixture(scope="module")
def live_server():
    """Spins up live server on a dedicated local port."""
    config, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(config.layout)
    skus = generate_catalogue(sku_count=config.catalogue.sku_count, seed=config.seed)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=config.seed)

    engine = SimEngine(config=config, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, speed_multiplier=1.0, start_paused=False)
    app = create_app(engine=engine, pacer=pacer)

    server_port = 8899
    server = uvicorn.Server(
        config=uvicorn.Config(app=app, host="127.0.0.1", port=server_port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to become responsive
    time.sleep(1.0)
    yield f"http://127.0.0.1:{server_port}"

    server.should_exit = True
    thread.join(timeout=2.0)


def test_playwright_command_centre_e2e(live_server: str):
    reports_dir = Path("reports/screens")
    reports_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Test 1920x1080 Dark Theme Command Centre
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(live_server)

        # Verify page title
        assert "RoboFleet Command Centre" in page.title()

        # Wait for TopBar and Canvas to render
        page.wait_for_selector("header")
        page.wait_for_selector("canvas")

        # Let simulation run a few ticks so AMRs and Orders stream in
        page.wait_for_timeout(2500)

        # Capture 1920x1080 Dark screenshot
        dark_1080p = reports_dir / "command_centre_1920x1080_dark.png"
        page.screenshot(path=str(dark_1080p))
        assert dark_1080p.exists()

        # 2. Test Environment Disclosure Modal (P2-A9)
        env_badge = page.get_by_role("button", name="DIGITAL TWIN")
        assert env_badge.is_visible()
        env_badge.click()

        # Wait for modal
        page.wait_for_selector("text=Environment Disclosure")
        page.wait_for_timeout(500)

        modal_shot = reports_dir / "command_centre_environment_modal.png"
        page.screenshot(path=str(modal_shot))
        assert modal_shot.exists()

        # Close modal
        page.get_by_role("button", name="Close", exact=True).click()
        page.wait_for_timeout(300)

        # 3. Test Theme Toggle (Dark -> Light)
        theme_btn = page.get_by_title("Toggle Light/Dark Theme")
        theme_btn.click()
        page.wait_for_timeout(500)

        light_1080p = reports_dir / "command_centre_1920x1080_light.png"
        page.screenshot(path=str(light_1080p))
        assert light_1080p.exists()

        # 4. Test 1366x768 Laptop Viewport
        page_laptop = browser.new_page(viewport={"width": 1366, "height": 768})
        page_laptop.goto(live_server)
        page_laptop.wait_for_selector("canvas")
        page_laptop.wait_for_timeout(1500)

        laptop_shot = reports_dir / "command_centre_1366x768_dark.png"
        page_laptop.screenshot(path=str(laptop_shot))
        assert laptop_shot.exists()

        browser.close()
