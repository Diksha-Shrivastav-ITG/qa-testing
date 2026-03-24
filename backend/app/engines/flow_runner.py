from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FlowResult:
    name: str
    status: str  # "pass" or "fail"
    step_failed: Optional[int] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None


# ---------------------------------------------------------------------------
# FlowRunner
# ---------------------------------------------------------------------------


class FlowRunner:
    """Executes multi-step Playwright flows and returns a FlowResult."""

    def __init__(self, base_url: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        # Internal baseline storage for assert_changed steps
        self._baseline: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Step executor
    # ------------------------------------------------------------------

    async def execute_step(self, page, step: dict) -> None:
        """Execute a single flow step against *page*.

        Raises an exception (AssertionError or Playwright error) on failure.
        """
        action = step.get("action", "")

        if action == "navigate":
            value = step.get("value", "")
            await page.goto(self.base_url + value)

        elif action == "click":
            await page.click(step["selector"])

        elif action == "type":
            await page.fill(step["selector"], step["value"])

        elif action == "select":
            await page.select_option(step["selector"], step["value"])

        elif action == "hover":
            await page.hover(step["selector"])

        elif action == "scroll":
            amount = step.get("value", 500)
            await page.evaluate(f"window.scrollBy(0, {amount})")

        elif action == "wait":
            duration_ms = step.get("duration_ms", 1000)
            await page.wait_for_timeout(duration_ms)

        elif action == "assert_visible":
            sel = step["selector"]
            visible = await page.locator(sel).is_visible()
            if not visible:
                raise AssertionError(f"Expected element '{sel}' to be visible, but it was not.")

        elif action == "assert_hidden":
            sel = step["selector"]
            visible = await page.locator(sel).is_visible()
            if visible:
                raise AssertionError(f"Expected element '{sel}' to be hidden, but it was visible.")

        elif action == "assert_text":
            sel = step["selector"]
            expected = step.get("value", "")
            content = await page.locator(sel).text_content() or ""
            if expected not in content:
                raise AssertionError(
                    f"Expected text '{expected}' not found in '{sel}'. Got: '{content}'"
                )

        elif action == "assert_changed":
            sel = step["selector"]
            current = await page.locator(sel).text_content() or ""
            baseline = self._baseline.get(sel, "")
            if current == baseline:
                raise AssertionError(
                    f"Expected content of '{sel}' to change, but it remained: '{current}'"
                )

        elif action == "assert_count":
            sel = step["selector"]
            expected_count = step.get("value", 0)
            actual_count = await page.locator(sel).count()
            if actual_count != expected_count:
                raise AssertionError(
                    f"Expected {expected_count} elements matching '{sel}', found {actual_count}."
                )

        elif action == "screenshot":
            # No-op — screenshots are handled at the flow level
            pass

        else:
            raise ValueError(f"Unknown action: '{action}'")

    # ------------------------------------------------------------------
    # Baseline snapshot helper
    # ------------------------------------------------------------------

    async def _take_baseline_snapshots(self, page, steps: list[dict]) -> None:
        """Capture text snapshots for any assert_changed steps before the flow runs."""
        for step in steps:
            if step.get("action") == "assert_changed":
                sel = step["selector"]
                try:
                    content = await page.locator(sel).text_content() or ""
                    self._baseline[sel] = content
                except Exception:
                    self._baseline[sel] = ""

    # ------------------------------------------------------------------
    # Flow runner
    # ------------------------------------------------------------------

    async def run_flow(self, page, flow: dict, output_dir: str) -> FlowResult:
        """Execute all steps in *flow* and return a FlowResult.

        On failure the engine:
        1. Takes a failure screenshot saved to *output_dir*.
        2. Returns a FlowResult with status="fail", step_failed, and error_message.
        """
        name = flow.get("name", "unnamed_flow")
        steps: list[dict] = flow.get("steps", [])

        # Take baseline snapshots for assert_changed steps
        self._baseline = {}
        await self._take_baseline_snapshots(page, steps)

        for index, step in enumerate(steps):
            try:
                await self.execute_step(page, step)
            except Exception as exc:
                # Attempt to save a failure screenshot
                screenshot_path: Optional[str] = None
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    screenshot_path = os.path.join(output_dir, f"{name}_step{index}_failure.png")
                    await page.screenshot(path=screenshot_path)
                except Exception:
                    screenshot_path = None

                return FlowResult(
                    name=name,
                    status="fail",
                    step_failed=index,
                    error_message=str(exc),
                    screenshot_path=screenshot_path,
                )

        return FlowResult(name=name, status="pass")
