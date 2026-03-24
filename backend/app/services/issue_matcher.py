from __future__ import annotations

import math
from collections import defaultdict

PROXIMITY_THRESHOLD = 50  # pixels


def _distance(a: dict, b: dict) -> float:
    """Return the Euclidean distance between location_x/y of two issue dicts."""
    dx = a["location_x"] - b["location_x"]
    dy = a["location_y"] - b["location_y"]
    return math.sqrt(dx * dx + dy * dy)


def match_issues(prev_issues: list[dict], curr_issues: list[dict]) -> dict[str, list]:
    """Match issues across runs to classify them as still_open, resolved, or new.

    Algorithm:
      1. Group issues by (page, breakpoint).
      2. Pass 1 — selector match: match current to previous by (element_selector, type)
         when both are non-None.
      3. Pass 2 — proximity match: match remaining unmatched issues by Euclidean
         distance <= PROXIMITY_THRESHOLD and same type.
      4. Unmatched previous → resolved; unmatched current → new;
         matched current → still_open (carries _matched_prev).

    Args:
        prev_issues: Issues from the previous run.
        curr_issues: Issues from the current run.

    Returns:
        {"still_open": [...], "resolved": [...], "new": [...]}
    """
    still_open: list[dict] = []
    resolved: list[dict] = []
    new: list[dict] = []

    # Group by (page, breakpoint)
    def _group(issues: list[dict]) -> dict[tuple, list[dict]]:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for issue in issues:
            key = (issue["page"], issue["breakpoint"])
            groups[key].append(issue)
        return groups

    prev_groups = _group(prev_issues)
    curr_groups = _group(curr_issues)

    all_keys = set(prev_groups.keys()) | set(curr_groups.keys())

    for key in all_keys:
        prev_group = list(prev_groups.get(key, []))
        curr_group = list(curr_groups.get(key, []))

        # Track which items are still unmatched
        unmatched_prev = list(prev_group)
        unmatched_curr = list(curr_group)

        # --- Pass 1: Selector match ---
        matched_prev_indices = set()
        matched_curr_indices = set()

        for ci, curr in enumerate(unmatched_curr):
            curr_selector = curr.get("element_selector")
            curr_type = curr.get("type")
            if curr_selector is None:
                continue  # no selector to match on
            for pi, prev in enumerate(unmatched_prev):
                if pi in matched_prev_indices:
                    continue
                prev_selector = prev.get("element_selector")
                if prev_selector is None:
                    continue
                if prev_selector == curr_selector and prev.get("type") == curr_type:
                    matched_prev_indices.add(pi)
                    matched_curr_indices.add(ci)
                    matched_issue = dict(curr)
                    matched_issue["_matched_prev"] = prev
                    still_open.append(matched_issue)
                    break

        # Rebuild unmatched lists after pass 1
        remaining_prev = [p for i, p in enumerate(unmatched_prev) if i not in matched_prev_indices]
        remaining_curr = [c for i, c in enumerate(unmatched_curr) if i not in matched_curr_indices]

        # --- Pass 2: Proximity match ---
        matched_prev_indices2 = set()
        matched_curr_indices2 = set()

        for ci, curr in enumerate(remaining_curr):
            curr_type = curr.get("type")
            best_dist = float("inf")
            best_pi = None
            for pi, prev in enumerate(remaining_prev):
                if pi in matched_prev_indices2:
                    continue
                if prev.get("type") != curr_type:
                    continue
                dist = _distance(prev, curr)
                if dist <= PROXIMITY_THRESHOLD and dist < best_dist:
                    best_dist = dist
                    best_pi = pi
            if best_pi is not None:
                matched_prev_indices2.add(best_pi)
                matched_curr_indices2.add(ci)
                matched_issue = dict(curr)
                matched_issue["_matched_prev"] = remaining_prev[best_pi]
                still_open.append(matched_issue)

        # Collect unmatched after pass 2
        for pi, prev in enumerate(remaining_prev):
            if pi not in matched_prev_indices2:
                resolved.append(prev)

        for ci, curr in enumerate(remaining_curr):
            if ci not in matched_curr_indices2:
                new.append(curr)

    return {"still_open": still_open, "resolved": resolved, "new": new}
