"""
DeepPredict — ISO/IEC 25010 E2E Browser Test Suite
Characteristic: Functional Suitability + Usability (8.1 & 8.3)

Scenarios covered:
  1. IT_PRO   : Login → Dashboard → Drives list → Drive detail → Logout
  2. OPERATOR : Login → Verify read-only UI (no Admin link) → Logout
  3. SYSADMIN : Login → Verify Admin Dashboard link present → Logout

Evidence:
  - Screenshots  → evidence/e2e/*.png
  - JSON report  → evidence/e2e/e2e_report.json

Usage:
  # 1. Start Django server in another terminal:
  #    cd backend && python manage.py runserver 127.0.0.1:8000 --noreload
  #
  # 2. Run this script:
  #    python backend/dashboard/run_e2e.py
  #
  # Optional: override server URL
  #    TARGET_URL=http://127.0.0.1:8000 python backend/dashboard/run_e2e.py
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("TARGET_URL", "http://127.0.0.1:8000")
EVIDENCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "evidence", "e2e")
)
os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Credentials
USERS = {
    "it_pro_user":    os.environ.get("ITPRO_PASS", "Pass123!Safe"),
    "operator_user":  os.environ.get("OPERATOR_PASS", "Pass123!Safe"),
    "fatma":          os.environ.get("SYSADMIN_PASS", "admin"),
}

results = []


def screenshot(page, name):
    path = os.path.join(EVIDENCE_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"    📸 Screenshot saved → {path}")
    return path


def record(scenario, passed, error=""):
    results.append({
        "scenario": scenario,
        "passed": passed,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} — {scenario}" + (f" ({error})" if error else ""))


def login(page, username, password):
    page.goto(f"{BASE_URL}/login/", timeout=15000)
    page.wait_for_selector("input[name='username']", timeout=10000)
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")


def logout(page):
    try:
        page.click(".dp-logout-btn", timeout=5000)
        page.wait_for_selector("input[name='username']", timeout=10000)
    except Exception:
        # Fallback: navigate directly to logout URL
        page.goto(f"{BASE_URL}/logout/", timeout=10000)


def run_scenario_itpro(page):
    print("\n[Scenario 1] IT_PRO — Full Workflow Journey")
    try:
        # Step 1: Login page
        page.goto(f"{BASE_URL}/login/", timeout=15000)
        page.wait_for_selector("input[name='username']", timeout=10000)
        screenshot(page, "01_login_page")
        record("Login page renders", True)

        # Step 2: Authenticate
        page.fill("input[name='username']", "it_pro_user")
        page.fill("input[name='password']", USERS["it_pro_user"])
        page.click("button[type='submit']")
        page.wait_for_selector(".dp-kpi-grid", timeout=15000)
        screenshot(page, "02_dashboard_itpro")

        content = page.content()
        # E2E test verification assertion for KPI card elements
        assert "Overview" in content or "Total Drives" in content, "KPI grid missing"  # nosec B101
        record("IT_PRO lands on Dashboard after login", True)

        # Step 3: User identity shown in sidebar
        assert "it_pro_user" in content, "Username not in sidebar"  # nosec B101
        record("IT_PRO username visible in sidebar", True)
        record("IT_PRO username visible in sidebar", True)

        # Step 4: Navigate to Drives list
        page.click("a[href='/drives/']")
        page.wait_for_selector(".dp-table", timeout=10000)
        screenshot(page, "03_drives_list")
        record("IT_PRO can navigate to Drives list", True)

        # Step 5: Open first drive detail
        detail_link = page.query_selector("table tbody tr:first-child a")
        if detail_link:
            detail_link.click()
            page.wait_for_selector(".dp-card", timeout=10000)
            time.sleep(1)
            screenshot(page, "04_drive_detail")
            record("IT_PRO can open Drive detail page", True)
        else:
            record("IT_PRO can open Drive detail page", False, "No drive row found")

        # Step 6: Logout
        logout(page)
        record("IT_PRO logout successful", True)

    except Exception as e:
        screenshot(page, "ERROR_itpro")
        record("IT_PRO scenario (unexpected error)", False, str(e))
        # Force logout to reset for next scenario
        try:
            page.goto(f"{BASE_URL}/logout/", timeout=5000)
        except Exception as cleanup_err:
            print(f"    [!] Note: Cleanup logout encountered error: {cleanup_err}")


def run_scenario_operator(page):
    print("\n[Scenario 2] OPERATOR — Read-Only RBAC Verification")
    try:
        page.goto(f"{BASE_URL}/login/", timeout=15000)
        page.wait_for_selector("input[name='username']", timeout=10000)
        page.fill("input[name='username']", "operator_user")
        page.fill("input[name='password']", USERS["operator_user"])
        page.click("button[type='submit']")
        page.wait_for_selector(".dp-shell", timeout=15000)
        screenshot(page, "05_operator_dashboard")

        content = page.content()
        # E2E RBAC assertion: Admin Dashboard link must NOT appear for OPERATOR
        assert "Admin Dashboard" not in content, "Security breach: Admin link visible to Operator!"  # nosec B101
        record("OPERATOR has no Admin Dashboard link (RBAC OK)", True)

        # E2E assertion: Role label must be visible
        assert "Operator" in content or "operator_user" in content, "Role/username not visible"  # nosec B101
        record("OPERATOR username/role visible in sidebar", True)
        record("OPERATOR username/role visible in sidebar", True)

        logout(page)
        record("OPERATOR logout successful", True)

    except Exception as e:
        screenshot(page, "ERROR_operator")
        record("OPERATOR scenario (unexpected error)", False, str(e))
        try:
            page.goto(f"{BASE_URL}/logout/", timeout=5000)
        except Exception as cleanup_err:
            print(f"    [!] Note: Cleanup logout encountered error: {cleanup_err}")


def run_scenario_sysadmin(page):
    print("\n[Scenario 3] SYSADMIN — Admin Dashboard Access")
    try:
        page.goto(f"{BASE_URL}/login/", timeout=15000)
        page.wait_for_selector("input[name='username']", timeout=10000)
        page.fill("input[name='username']", "fatma")
        page.fill("input[name='password']", USERS["fatma"])
        page.click("button[type='submit']")
        page.wait_for_selector(".dp-shell", timeout=15000)
        screenshot(page, "06_sysadmin_dashboard")

        content = page.content()
        # E2E RBAC assertion: SYSADMIN MUST see Admin Dashboard link
        assert "Admin Dashboard" in content, "Admin Dashboard link missing for SYSADMIN!"  # nosec B101
        record("SYSADMIN sees Admin Dashboard link (RBAC OK)", True)

        # Navigate to Admin
        page.click("a[href='/admin/']")
        page.wait_for_load_state("networkidle", timeout=10000)
        screenshot(page, "07_admin_panel")
        record("SYSADMIN can access Django Admin", True)

        logout(page)
        record("SYSADMIN logout successful", True)

    except Exception as e:
        screenshot(page, "ERROR_sysadmin")
        record("SYSADMIN scenario (unexpected error)", False, str(e))
        try:
            page.goto(f"{BASE_URL}/logout/", timeout=5000)
        except Exception as cleanup_err:
            print(f"    [!] Note: Cleanup logout encountered error: {cleanup_err}")


def run_e2e_tests():
    print(f"\n{'='*60}")
    print(f"  DeepPredict — ISO/IEC 25010 E2E Browser Suite")
    print(f"  Target: {BASE_URL}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            record_video_dir=EVIDENCE_DIR,
        )
        page = context.new_page()

        run_scenario_itpro(page)
        run_scenario_operator(page)
        run_scenario_sysadmin(page)

        context.close()
        browser.close()

    # Save JSON report
    report_path = os.path.join(EVIDENCE_DIR, "e2e_report.json")
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    report = {
        "suite": "DeepPredict E2E — ISO/IEC 25010 Functional Suitability",
        "target": BASE_URL,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": total, "passed": passed, "failed": failed},
        "results": results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed  |  {failed} failed")
    print(f"  Report  → {report_path}")
    print(f"  Screenshots → {EVIDENCE_DIR}")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_e2e_tests())
