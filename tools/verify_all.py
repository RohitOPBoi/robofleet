import time
import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://127.0.0.1:8000')
    page.wait_for_timeout(4000)

    # 1. Capture initial running state
    page.screenshot(path='reports/screens/verify_1_running.png')
    print('Captured verify_1_running.png')

    # 2. Test Rush Mode
    rush_btn = page.locator('button:has-text("Rush Mode")')
    if rush_btn.count() > 0:
        rush_btn.click()
        print('Clicked Rush Mode')
        page.wait_for_timeout(2500)
        page.screenshot(path='reports/screens/verify_2_rush_mode.png')
        print('Captured verify_2_rush_mode.png')

    # 3. Test Chaos Studio
    chaos_btn = page.locator('button:has-text("Chaos")')
    if chaos_btn.count() > 0:
        chaos_btn.click()
        print('Opened Chaos Studio')
        page.wait_for_timeout(1500)
        page.screenshot(path='reports/screens/verify_3_chaos_modal.png')
        print('Captured verify_3_chaos_modal.png')

        # Inject breakdown fault
        inject_btn = page.locator('button:has-text("Inject Active Fault")')
        if inject_btn.count() > 0:
            inject_btn.click()
            print('Clicked Inject Active Fault')
            page.wait_for_timeout(2000)
            page.screenshot(path='reports/screens/verify_4_chaos_injected.png')
            print('Captured verify_4_chaos_injected.png')

        # Close chaos modal
        close_btn = page.locator('div.fixed.inset-0 button:has(svg.lucide-x)')
        if close_btn.count() > 0:
            close_btn.first.click()
            print('Closed Chaos Studio')
            page.wait_for_timeout(1500)

    # 4. Check Alert Banner and Highlighting
    page.screenshot(path='reports/screens/verify_5_alert_highlighting.png')
    print('Captured verify_5_alert_highlighting.png')

    # Locate button in alert banner
    locate_btn = page.locator('button:has-text("Locate")')
    if locate_btn.count() > 0:
        locate_btn.first.click()
        print('Clicked Locate in Alert Banner')
        page.wait_for_timeout(1500)
        page.screenshot(path='reports/screens/verify_6_alert_located.png')
        print('Captured verify_6_alert_located.png')

    # 5. Test Restart button (resets timer to 00:00:00)
    restart_btn = page.locator('button[title*="Restart simulation"]')
    if restart_btn.count() > 0:
        restart_btn.click()
        print('Clicked Restart Simulation')
        page.wait_for_timeout(1500)
        page.screenshot(path='reports/screens/verify_7_restarted_timer_0.png')
        print('Captured verify_7_restarted_timer_0.png')

    browser.close()
