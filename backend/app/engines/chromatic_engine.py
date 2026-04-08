"""Chromatic visual regression engine.

Uses @chromatic-com/playwright to capture Playwright snapshots and submit
them to Chromatic for visual comparison against the stored baseline.

Flow:
  1. Generate a Playwright TypeScript test file for the given pages
  2. Run `npx chromatic --playwright --project-token=...`
  3. Parse CLI output for build URL and visual change counts
  4. Return structured ChromaticResult
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Absolute path to the chromatic-tests Node.js project (relative to this file)
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMATIC_TESTS_DIR = os.path.abspath(
    os.path.join(_ENGINE_DIR, "..", "..", "chromatic-tests")
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ChromaticSnapshot:
    name: str
    url: str
    status: str   # "changed" | "unchanged" | "added" | "error"
    change_count: int = 0


@dataclass
class ChromaticResult:
    build_url: str
    status: str           # "passed" | "failed" | "error"
    snapshot_count: int
    change_count: int
    snapshots: list[ChromaticSnapshot] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ChromaticEngine:
    """Run a Chromatic visual regression build for a Shopify store."""

    def __init__(self, project_token: str) -> None:
        self.project_token = project_token
        self.tests_dir = CHROMATIC_TESTS_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compare(
        self,
        shopify_url: str,
        page_paths: list[str],
        project_name: str = "QA Run",
        viewport_width: int = 1440,
        viewport_height: int = 900,
    ) -> ChromaticResult:
        """Capture Playwright snapshots and submit to Chromatic.

        Args:
            shopify_url:     Base URL of the Shopify store.
            page_paths:      URL paths to capture (e.g. ["/", "/collections/all"]).
            project_name:    Label for logging.
            viewport_width:  Snapshot viewport width.
            viewport_height: Snapshot viewport height.

        Returns:
            ChromaticResult with build URL, status, and change counts.
        """
        paths = [p if p.startswith("/") else f"/{p}" for p in page_paths]
        if not paths:
            paths = ["/"]

        base_url = shopify_url.rstrip("/")
        test_content = self._generate_test_file(base_url, paths, viewport_width, viewport_height)

        tests_subdir = os.path.join(self.tests_dir, "tests")
        os.makedirs(tests_subdir, exist_ok=True)
        test_file = os.path.join(tests_subdir, "generated.spec.ts")

        try:
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_content)

            return await self._run_chromatic(len(paths))

        except Exception as exc:
            logger.warning("Chromatic engine error: %s", exc)
            return ChromaticResult(
                build_url="",
                status="error",
                snapshot_count=0,
                change_count=0,
                error=str(exc),
            )
        finally:
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_test_file(
        self,
        base_url: str,
        paths: list[str],
        width: int,
        height: int,
    ) -> str:
        """Return a TypeScript Playwright test file that captures each page."""
        tests = []
        for path in paths:
            page_url = f"{base_url}{path}"
            name = path.strip("/").replace("/", " > ") or "Homepage"
            name_escaped = name.replace("'", "\\'")
            url_escaped = page_url.replace("'", "\\'")
            tests.append(
                f"test('{name_escaped}', async ({{ page }}) => {{\n"
                f"  await page.goto('{url_escaped}');\n"
                f"  await page.waitForLoadState('networkidle');\n"
                f"}});"
            )

        return (
            'import { test } from "@chromatic-com/playwright";\n\n'
            + "\n\n".join(tests)
            + "\n"
        )

    async def _run_chromatic(self, expected_snapshots: int) -> ChromaticResult:
        """Execute `npx chromatic --playwright` and parse the output."""
        cmd = [
            "npx", "chromatic",
            "--playwright",
            f"--project-token={self.project_token}",
            "--exit-zero-on-changes",
            "--force-rebuild",
            "--no-interactive",
        ]

        logger.info("Chromatic: running in %s", self.tests_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.tests_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=300
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Chromatic CLI timed out after 300 seconds")

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        logger.info("Chromatic stdout:\n%s", stdout)
        if stderr:
            logger.debug("Chromatic stderr:\n%s", stderr)

        return self._parse_output(stdout, stderr, expected_snapshots)

    def _parse_output(self, stdout: str, stderr: str, expected_snapshots: int) -> ChromaticResult:
        """Parse Chromatic CLI output into a ChromaticResult."""
        combined = stdout + "\n" + stderr

        # Build URL
        build_url = ""
        url_match = re.search(r"https://www\.chromatic\.com/build\?[^\s]+", combined)
        if url_match:
            build_url = url_match.group(0).rstrip(".")

        # Change count
        change_count = 0
        changes_match = re.search(r"(\d+)\s+(?:visual\s+)?change", combined, re.IGNORECASE)
        if changes_match:
            change_count = int(changes_match.group(1))

        # Snapshot count
        snapshot_count = expected_snapshots
        snap_match = re.search(r"(\d+)\s+snapshot", combined, re.IGNORECASE)
        if snap_match:
            snapshot_count = int(snap_match.group(1))

        # Status
        lower = combined.lower()
        if "build passed" in lower:
            status = "passed"
        elif "build failed" in lower:
            status = "failed"
        elif change_count > 0:
            status = "failed"
        elif build_url:
            status = "passed"
        else:
            status = "error"

        return ChromaticResult(
            build_url=build_url,
            status=status,
            snapshot_count=snapshot_count,
            change_count=change_count,
        )
