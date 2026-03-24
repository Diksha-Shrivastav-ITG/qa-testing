from __future__ import annotations

import math

import pytest

from app.services.issue_matcher import match_issues


def _issue(page: str, bp: str, type_: str, selector: str | None = None, x: float = 100, y: float = 200) -> dict:
    """Create a minimal issue dict for testing."""
    return {
        "page": page,
        "breakpoint": bp,
        "type": type_,
        "element_selector": selector,
        "location_x": x,
        "location_y": y,
        "severity": "minor",
        "description": "test issue",
    }


class TestMatchBySelector:
    def test_match_by_selector(self):
        """Same page/bp/type/selector in prev and curr → still_open=1, resolved=0, new=0."""
        prev = [_issue("home", "desktop", "layout", selector=".nav")]
        curr = [_issue("home", "desktop", "layout", selector=".nav")]

        result = match_issues(prev, curr)

        assert len(result["still_open"]) == 1
        assert len(result["resolved"]) == 0
        assert len(result["new"]) == 0

    def test_still_open_has_matched_prev(self):
        """still_open entries must carry _matched_prev pointing to the previous issue."""
        prev_issue = _issue("home", "desktop", "layout", selector=".hero")
        curr_issue = _issue("home", "desktop", "layout", selector=".hero")

        result = match_issues([prev_issue], [curr_issue])

        assert len(result["still_open"]) == 1
        assert "_matched_prev" in result["still_open"][0]
        assert result["still_open"][0]["_matched_prev"] is prev_issue


class TestResolvedIssue:
    def test_resolved_issue(self):
        """prev has issue, curr empty → resolved=1, new=0, still_open=0."""
        prev = [_issue("home", "desktop", "layout", selector=".nav")]
        curr = []

        result = match_issues(prev, curr)

        assert len(result["resolved"]) == 1
        assert len(result["new"]) == 0
        assert len(result["still_open"]) == 0


class TestNewIssue:
    def test_new_issue(self):
        """prev empty, curr has issue → new=1, resolved=0, still_open=0."""
        prev = []
        curr = [_issue("home", "desktop", "layout", selector=".nav")]

        result = match_issues(prev, curr)

        assert len(result["new"]) == 1
        assert len(result["resolved"]) == 0
        assert len(result["still_open"]) == 0


class TestMatchByProximity:
    def test_match_by_proximity(self):
        """prev at (100,200), curr at (120,210), same type → still_open=1 (within 50px)."""
        distance = math.sqrt((120 - 100) ** 2 + (210 - 200) ** 2)
        assert distance < 50, f"Expected distance < 50, got {distance:.2f}"

        prev = [_issue("home", "desktop", "layout", selector=None, x=100, y=200)]
        curr = [_issue("home", "desktop", "layout", selector=None, x=120, y=210)]

        result = match_issues(prev, curr)

        assert len(result["still_open"]) == 1
        assert len(result["resolved"]) == 0
        assert len(result["new"]) == 0

    def test_proximity_match_ignores_different_type(self):
        """Issues with different types should NOT match even if within 50px."""
        prev = [_issue("home", "desktop", "layout", selector=None, x=100, y=200)]
        curr = [_issue("home", "desktop", "color", selector=None, x=110, y=205)]

        result = match_issues(prev, curr)

        assert len(result["resolved"]) == 1
        assert len(result["new"]) == 1
        assert len(result["still_open"]) == 0


class TestNoMatchBeyondProximity:
    def test_no_match_beyond_proximity(self):
        """prev at (100,200), curr at (300,500) → resolved=1, new=1 (beyond 50px)."""
        distance = math.sqrt((300 - 100) ** 2 + (500 - 200) ** 2)
        assert distance > 50, f"Expected distance > 50, got {distance:.2f}"

        prev = [_issue("home", "desktop", "layout", selector=None, x=100, y=200)]
        curr = [_issue("home", "desktop", "layout", selector=None, x=300, y=500)]

        result = match_issues(prev, curr)

        assert len(result["resolved"]) == 1
        assert len(result["new"]) == 1
        assert len(result["still_open"]) == 0


class TestGroupingByPageAndBreakpoint:
    def test_different_page_no_match(self):
        """Issues on different pages do not match, even with same selector."""
        prev = [_issue("home", "desktop", "layout", selector=".nav")]
        curr = [_issue("about", "desktop", "layout", selector=".nav")]

        result = match_issues(prev, curr)

        assert len(result["resolved"]) == 1
        assert len(result["new"]) == 1
        assert len(result["still_open"]) == 0

    def test_different_breakpoint_no_match(self):
        """Issues on different breakpoints do not match, even with same selector."""
        prev = [_issue("home", "desktop", "layout", selector=".nav")]
        curr = [_issue("home", "mobile", "layout", selector=".nav")]

        result = match_issues(prev, curr)

        assert len(result["resolved"]) == 1
        assert len(result["new"]) == 1
        assert len(result["still_open"]) == 0

    def test_multiple_groups(self):
        """Issues across multiple groups are matched independently."""
        prev = [
            _issue("home", "desktop", "layout", selector=".nav"),
            _issue("about", "mobile", "color", selector=".hero"),
        ]
        curr = [
            _issue("home", "desktop", "layout", selector=".nav"),
            # about/mobile issue is gone
        ]

        result = match_issues(prev, curr)

        assert len(result["still_open"]) == 1
        assert len(result["resolved"]) == 1
        assert len(result["new"]) == 0


class TestSelectorTakesPriorityOverProximity:
    def test_selector_match_preferred_over_proximity(self):
        """Selector match in pass 1 should consume issues before proximity in pass 2."""
        prev = [_issue("home", "desktop", "layout", selector=".nav", x=100, y=200)]
        # curr has same selector but at a very different location
        curr = [_issue("home", "desktop", "layout", selector=".nav", x=300, y=500)]

        result = match_issues(prev, curr)

        # Should match by selector even though they're far apart
        assert len(result["still_open"]) == 1
        assert len(result["resolved"]) == 0
        assert len(result["new"]) == 0
