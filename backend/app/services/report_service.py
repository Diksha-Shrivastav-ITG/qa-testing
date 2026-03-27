from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.accessibility_result import AccessibilityResult
from app.models.capture import Capture
from app.models.comparison import Comparison
from app.models.functional_test import FunctionalTest, FunctionalTestStatus
from app.models.issue import Issue, IssueSeverity, IssueType
from app.models.link_audit import LinkAudit
from app.models.project import Project
from app.models.qa_run import QaRun

BACKEND_BASE = "http://localhost:8000"

BREAKPOINT_LABELS = {
    375: "iPhone SE / Mobile (375px)",
    425: "Mobile Large (425px)",
    768: "iPad / Tablet (768px)",
    1024: "Desktop Small (1024px)",
    1280: "Desktop (1280px)",
    1440: "Desktop Large (1440px)",
    1920: "Full HD Desktop (1920px)",
}

SECTION_ICONS = {
    "visual": "🎨",
    "functional": "⚙️",
    "content": "📄",
}

SEV_COLORS = {"critical": "#dc2626", "major": "#d97706", "minor": "#ca8a04"}
SEV_BG = {"critical": "#fef2f2", "major": "#fffbeb", "minor": "#fefce8"}


def _esc(text: str) -> str:
    """Escape HTML special characters to prevent broken layout."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _storage_to_url(path: str | None, storage_base: str) -> str | None:
    if not path:
        return None
    rel = path.replace(storage_base.rstrip("/"), "").lstrip("/")
    return f"{BACKEND_BASE}/storage/{rel}"


def _fmt_date(dt) -> str:
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return str(dt)
    return dt.strftime("%B %d, %Y at %I:%M %p")


def _title_from_description(desc: str) -> str:
    """Convert a raw description into a short readable title."""
    if not desc:
        return "Unknown Issue"
    # Truncate long descriptions to a title
    if len(desc) <= 80:
        return desc
    # Try to get first sentence
    for sep in [". ", ".\n", " - ", ": "]:
        idx = desc.find(sep)
        if idx > 0 and idx <= 80:
            return desc[:idx]
    return desc[:77] + "…"


def _page_label(page: str) -> str:
    mapping = {
        "home": "Homepage",
        "/": "Homepage",
        "": "Homepage",
        "collection": "Collection Page",
        "collections": "Collections Page",
        "product": "Product Page",
        "products": "Products Page",
        "about": "About Page",
        "contact": "Contact Page",
    }
    return mapping.get(page.lower().strip("/"), page.replace("-", " ").replace("_", " ").title())


def generate_html_report(db: Session, run_id: int, auto_print: bool = False) -> str:
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    project = db.query(Project).filter(Project.id == run.project_id).first()

    from app.config import settings
    storage_base = settings.storage_path

    issues = db.query(Issue).filter(Issue.qa_run_id == run_id).order_by(
        Issue.type, Issue.severity, Issue.page, Issue.id
    ).all()
    functional_tests = db.query(FunctionalTest).filter(FunctionalTest.qa_run_id == run_id).all()
    comparisons = db.query(Comparison).filter(Comparison.qa_run_id == run_id).all()
    captures = db.query(Capture).filter(Capture.qa_run_id == run_id).all()
    accessibility_results = db.query(AccessibilityResult).filter(AccessibilityResult.qa_run_id == run_id).order_by(
        AccessibilityResult.page, AccessibilityResult.severity
    ).all()
    link_audits = db.query(LinkAudit).filter(LinkAudit.qa_run_id == run_id).order_by(
        LinkAudit.page, LinkAudit.element_type
    ).all()

    # Index captures
    cap_index: dict[tuple, str | None] = {}
    for c in captures:
        cap_index[(c.page, c.breakpoint, c.source.value)] = _storage_to_url(c.image_path, storage_base)
    comp_index: dict[tuple, Comparison] = {}
    for c in comparisons:
        comp_index[(c.page, c.breakpoint)] = c

    # Group issues by type
    visual_issues = [i for i in issues if i.type == IssueType.visual]
    functional_issues = [i for i in issues if i.type == IssueType.functional]
    content_issues = [i for i in issues if i.type == IssueType.content] if hasattr(IssueType, "content") else []

    # Counts
    critical_count = sum(1 for i in issues if i.severity == IssueSeverity.critical)
    major_count = sum(1 for i in issues if i.severity == IssueSeverity.major)
    minor_count = sum(1 for i in issues if i.severity == IssueSeverity.minor)
    pass_count = sum(1 for ft in functional_tests if ft.status == FunctionalTestStatus.pass_)
    fail_count = sum(1 for ft in functional_tests if ft.status == FunctionalTestStatus.fail)
    ada_critical = sum(1 for a in accessibility_results if a.severity == "critical")
    ada_major = sum(1 for a in accessibility_results if a.severity == "major")
    link_issues_count = sum(1 for l in link_audits if l.issue is not None)
    score = run.overall_score if run.overall_score is not None else 0
    score_str = f"{score:.0f}/100"
    score_color = "#16a34a" if score >= 90 else "#d97706" if score >= 70 else "#dc2626"

    project_name = project.name if project else "Unknown Project"
    shopify_url = project.shopify_url if project else "N/A"
    source_type = (project.source_type.value.title() if hasattr(project.source_type, "value") else str(project.source_type)) if project else "N/A"
    source_url = project.source_url if project and project.source_url else "N/A (AI testing only)"
    test_mode = getattr(run, "test_mode", "design") or "design"
    run_date = _fmt_date(run.started_at)

    auto_print_js = "window.onload=function(){setTimeout(function(){window.print();},1000);};" if auto_print else ""

    # ─── BUILD SECTIONS ────────────────────────────────────────────────
    sections_html = ""
    section_num = 0

    # ── SECTION: Visual Issues ──
    if visual_issues:
        section_num += 1
        # Group by page
        by_page: dict[str, list[Issue]] = defaultdict(list)
        for issue in visual_issues:
            by_page[issue.page or "home"].append(issue)

        sub_html = ""
        sub_num = 0
        for page, page_issues in by_page.items():
            sub_num += 1
            page_label = _page_label(page)

            # Group by breakpoint within the page
            by_bp: dict[str | None, list[Issue]] = defaultdict(list)
            for issue in page_issues:
                key = str(issue.breakpoint) if issue.breakpoint else "general"
                by_bp[key].append(issue)

            issue_items_html = ""
            global_issue_n = visual_issues.index(page_issues[0]) + 1

            for bp_key, bp_issues in by_bp.items():
                if bp_key != "general":
                    bp_label = BREAKPOINT_LABELS.get(int(bp_key), f"{bp_key}px")
                    issue_items_html += f'<p class="bp-heading">📐 {bp_label}</p>'

                    # Show screenshots for this breakpoint
                    bp_int = int(bp_key)
                    design_url = cap_index.get((page, bp_int, "design"))
                    shopify_url_bp = cap_index.get((page, bp_int, "shopify"))
                    comp = comp_index.get((page, bp_int))
                    heatmap_url = _storage_to_url(comp.heatmap_path if comp else None, storage_base)
                    ssim = f"{comp.ssim_score:.3f}" if comp and comp.ssim_score is not None else None

                    if design_url or shopify_url_bp:
                        ssim_badge = f'<span class="ssim-badge">Similarity: {ssim}</span>' if ssim else ""
                        issue_items_html += f"""
                        <div class="screenshot-row">
                          {f'<div class="ss-block"><p class="ss-label">DESIGN (Source)</p><img src="{design_url}" class="ss-img"/></div>' if design_url else ''}
                          {f'<div class="ss-block"><p class="ss-label">SHOPIFY (Live)</p><img src="{shopify_url_bp}" class="ss-img"/></div>' if shopify_url_bp else ''}
                          {f'<div class="ss-block"><p class="ss-label">DIFF HEATMAP</p><img src="{heatmap_url}" class="ss-img"/></div>' if heatmap_url else ''}
                        </div>
                        {ssim_badge}"""

                for issue in bp_issues:
                    n = visual_issues.index(issue) + 1
                    sev = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
                    suggestion = issue.ai_suggestion or ""
                    selector = issue.element_selector or ""
                    title = _title_from_description(issue.description)

                    issue_items_html += f"""
                    <div class="issue-block" style="border-left:4px solid {SEV_COLORS.get(sev,'#999')};background:{SEV_BG.get(sev,'#f9fafb')};">
                      <div class="issue-header-row">
                        <span class="issue-label">Issue {section_num}.{sub_num}.{n}</span>
                        <span class="sev-pill" style="background:{SEV_COLORS.get(sev,'#999')};">{sev.upper()}</span>
                      </div>
                      <p class="issue-title">{title}</p>
                      <ul class="issue-meta">
                        <li><strong>Issue:</strong> {issue.description}</li>
                        {f'<li><strong>Element:</strong> <code>{selector}</code></li>' if selector else ''}
                        {f'<li><strong>Expected / Fix:</strong> {suggestion}</li>' if suggestion else ''}
                      </ul>
                    </div>"""

            sub_html += f"""
            <div class="subsection">
              <h3 class="sub-title">{section_num}.{sub_num} {page_label} — {len(page_issues)} Issue{"s" if len(page_issues)!=1 else ""}</h3>
              {issue_items_html}
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">🎨</span>{section_num}. Visual Design Issues <span class="count-badge">{len(visual_issues)}</span></h2>
          {sub_html}
        </div>"""

    # ── SECTION: Functional Issues ──
    if functional_issues:
        section_num += 1
        by_page_f: dict[str, list[Issue]] = defaultdict(list)
        for issue in functional_issues:
            by_page_f[issue.page or "home"].append(issue)

        sub_html = ""
        sub_num = 0
        for page, page_issues in by_page_f.items():
            sub_num += 1
            page_label = _page_label(page)
            issue_items_html = ""
            for n, issue in enumerate(page_issues, 1):
                sev = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
                title = _title_from_description(issue.description)
                issue_items_html += f"""
                <div class="issue-block" style="border-left:4px solid {SEV_COLORS.get(sev,'#999')};background:{SEV_BG.get(sev,'#f9fafb')};">
                  <div class="issue-header-row">
                    <span class="issue-label">Issue {section_num}.{sub_num}.{n}</span>
                    <span class="sev-pill" style="background:{SEV_COLORS.get(sev,'#999')};">{sev.upper()}</span>
                  </div>
                  <p class="issue-title">{title}</p>
                  <ul class="issue-meta">
                    <li><strong>Observation:</strong> {issue.description}</li>
                    <li><strong>Page:</strong> {page_label}</li>
                    <li><strong>Expected Result:</strong> {issue.ai_suggestion or 'This functionality should work as designed.'}</li>
                  </ul>
                </div>"""
            sub_html += f"""
            <div class="subsection">
              <h3 class="sub-title">{section_num}.{sub_num} {page_label}</h3>
              {issue_items_html}
            </div>"""
        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">⚙️</span>{section_num}. Functional Issues <span class="count-badge">{len(functional_issues)}</span></h2>
          {sub_html}
        </div>"""

    # ── SECTION: Functional Test Results ──
    if functional_tests:
        section_num += 1
        passed = [ft for ft in functional_tests if ft.status == FunctionalTestStatus.pass_]
        failed = [ft for ft in functional_tests if ft.status == FunctionalTestStatus.fail]

        ft_items = ""
        sub_num = 0
        if failed:
            sub_num += 1
            fail_items = ""
            for n, ft in enumerate(failed, 1):
                err = ft.error_message or "Test failed without error details"
                # Clean up long playwright errors
                if len(err) > 300:
                    err = err[:300] + "…"
                fail_items += f"""
                <div class="issue-block" style="border-left:4px solid #dc2626;background:#fef2f2;">
                  <div class="issue-header-row">
                    <span class="issue-label">Test {section_num}.{sub_num}.{n}</span>
                    <span class="sev-pill" style="background:#dc2626;">FAILED</span>
                  </div>
                  <p class="issue-title">{ft.test_name.replace("_", " ").title()}</p>
                  <ul class="issue-meta">
                    <li><strong>Error:</strong> {err}</li>
                    {f'<li><strong>Failed at step:</strong> {ft.step_failed}</li>' if ft.step_failed else ''}
                    <li><strong>Severity:</strong> {ft.severity or "N/A"}</li>
                  </ul>
                </div>"""
            ft_items += f"""
            <div class="subsection">
              <h3 class="sub-title">{section_num}.{sub_num} Failed Tests ({len(failed)})</h3>
              {fail_items}
            </div>"""
        if passed:
            sub_num += 1
            pass_list = "".join(f"<li>✅ {ft.test_name.replace('_',' ').title()}</li>" for ft in passed)
            ft_items += f"""
            <div class="subsection">
              <h3 class="sub-title">{section_num}.{sub_num} Passed Tests ({len(passed)})</h3>
              <ul class="pass-list">{pass_list}</ul>
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">🧪</span>{section_num}. Automated Test Results <span class="count-badge">{len(functional_tests)} tests</span></h2>
          {ft_items}
        </div>"""

    # ── SECTION: ADA / Accessibility ──
    if accessibility_results:
        section_num += 1
        by_page_a: dict[str, list[AccessibilityResult]] = defaultdict(list)
        for ar in accessibility_results:
            by_page_a[ar.page or "home"].append(ar)

        _sev_pill_a = {
            "critical": "background:#dc2626;color:#fff;",
            "major": "background:#d97706;color:#fff;",
            "minor": "background:#ca8a04;color:#fff;",
        }

        sub_html = ""
        sub_num = 0
        for page, page_ars in by_page_a.items():
            sub_num += 1
            page_label = _page_label(page)
            items_html = ""
            for n, ar in enumerate(page_ars, 1):
                sev = ar.severity or "minor"
                pill_style = _sev_pill_a.get(sev, "background:#6b7280;color:#fff;")
                title = _esc(ar.test_name.replace('-', ' ').replace('_', ' ').title())
                desc = _esc(ar.description or "")

                # WCAG — extract only wcagXXX references, skip category names
                wcag_ref = ""
                if ar.wcag:
                    import re
                    wcag_codes = re.findall(r'wcag\d[\w.]*', ar.wcag)
                    if wcag_codes:
                        wcag_ref = f'<span style="display:inline-block;background:#eff6ff;color:#1d4ed8;padding:1px 8px;border-radius:3px;font-size:0.65rem;font-weight:600;margin-left:4px;">WCAG {_esc(wcag_codes[0])}</span>'

                # Element — escape HTML and keep short
                elem_html = ""
                if ar.element:
                    short_elem = _esc(ar.element[:60] + ("..." if len(ar.element) > 60 else ""))
                    elem_html = f'<div style="margin-top:6px;padding:4px 8px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:4px;font-family:monospace;font-size:0.7rem;color:#6b7280;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{short_elem}</div>'

                # Fix suggestion
                fix_html = ""
                if ar.help_text:
                    fix_html = f'<div style="margin-top:6px;font-size:0.8rem;color:#374151;"><strong style="color:#059669;">Fix:</strong> {_esc(ar.help_text)}</div>'

                items_html += f"""
                <div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;margin-bottom:10px;background:#fff;page-break-inside:avoid;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
                  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                    <span style="font-size:0.65rem;font-weight:700;color:#9ca3af;text-transform:uppercase;">ADA {section_num}.{sub_num}.{n}</span>
                    <span style="{pill_style}padding:1px 10px;border-radius:20px;font-size:0.6rem;font-weight:700;text-transform:uppercase;">{sev}</span>
                    {wcag_ref}
                  </div>
                  <div style="font-size:0.85rem;font-weight:700;color:#1f2937;margin-top:6px;">{title}</div>
                  <div style="font-size:0.8rem;color:#4b5563;margin-top:4px;line-height:1.5;">{desc}</div>
                  {elem_html}
                  {fix_html}
                </div>"""

            sub_html += f"""
            <div style="margin-bottom:1.5rem;">
              <h3 style="font-family:-apple-system,sans-serif;font-size:0.95rem;font-weight:700;color:#374151;margin-bottom:0.75rem;padding-bottom:0.4rem;border-bottom:1px solid #f3f4f6;">{section_num}.{sub_num} {page_label} — {len(page_ars)} Issue{"s" if len(page_ars)!=1 else ""}</h3>
              {items_html}
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">♿</span>{section_num}. ADA / Accessibility Compliance <span class="count-badge">{len(accessibility_results)}</span></h2>
          <p style="font-family:-apple-system,sans-serif;font-size:0.8rem;color:#6b7280;margin-bottom:1rem;">
            Based on WCAG 2.1 AA standards. Issues affect screen readers, keyboard navigation, and assistive technologies.
          </p>
          {sub_html}
        </div>"""

    # ── SECTION: Links & Navigation Audit ──
    if link_audits:
        section_num += 1
        by_page_l: dict[str, list[LinkAudit]] = defaultdict(list)
        for la in link_audits:
            by_page_l[la.page or "home"].append(la)

        _issue_labels = {
            "missing_href": ("Link has no destination (# or javascript:void)", "#dc2626"),
            "empty_text": ("Link has no readable text or accessible label", "#d97706"),
            "no_accessible_name": ("Button has no accessible name (no text or aria-label)", "#dc2626"),
        }

        sub_html = ""
        sub_num = 0
        for page, page_las in by_page_l.items():
            sub_num += 1
            page_label = _page_label(page)
            issues_on_page = [la for la in page_las if la.issue]
            ok_on_page = [la for la in page_las if not la.issue]

            table_rows = ""
            for la in page_las[:200]:  # limit rows to prevent huge reports
                icon = "🔗" if la.element_type == "a" else "🔲"
                dest = la.destination or "—"
                if len(dest) > 60:
                    dest = dest[:57] + "…"
                text_disp = (la.text or "—")
                if len(text_disp) > 50:
                    text_disp = text_disp[:47] + "…"
                ext_badge = (
                    '<span style="background:#f0fdf4;color:#15803d;padding:1px 5px;border-radius:4px;font-size:0.65rem;">EXT</span> '
                    if la.is_external else ""
                )
                mail_badge = (
                    '<span style="background:#eff6ff;color:#1d4ed8;padding:1px 5px;border-radius:4px;font-size:0.65rem;">✉</span> '
                    if la.is_mail_or_tel else ""
                )
                if la.issue:
                    issue_label, issue_color = _issue_labels.get(la.issue, (la.issue, "#dc2626"))
                    status_cell = f'<td style="color:{issue_color};font-size:0.75rem;font-weight:600;">⚠ {issue_label}</td>'
                else:
                    status_cell = '<td style="color:#16a34a;font-size:0.75rem;">✅ OK</td>'

                table_rows += f"""<tr style="border-bottom:1px solid #f3f4f6;">
                  <td style="padding:6px 8px;font-size:0.8rem;">{icon} {ext_badge}{mail_badge}<code style="font-size:0.75rem;">{text_disp}</code></td>
                  <td style="padding:6px 8px;font-size:0.75rem;color:#374151;">{dest}</td>
                  {status_cell}
                </tr>"""

            sub_html += f"""
            <div class="subsection">
              <h3 class="sub-title">
                {section_num}.{sub_num} {page_label}
                <span style="font-size:0.8rem;font-weight:400;color:#6b7280;margin-left:0.5rem;">
                  {len(page_las)} elements | <span style="color:#dc2626;">{len(issues_on_page)} issues</span> | <span style="color:#16a34a;">{len(ok_on_page)} OK</span>
                </span>
              </h3>
              <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-family:-apple-system,sans-serif;font-size:0.85rem;">
                  <thead>
                    <tr style="background:#f3f4f6;text-align:left;">
                      <th style="padding:8px;font-size:0.7rem;color:#6b7280;font-weight:600;width:30%;">ELEMENT / TEXT</th>
                      <th style="padding:8px;font-size:0.7rem;color:#6b7280;font-weight:600;width:35%;">NAVIGATES TO</th>
                      <th style="padding:8px;font-size:0.7rem;color:#6b7280;font-weight:600;width:35%;">STATUS</th>
                    </tr>
                  </thead>
                  <tbody>{table_rows}</tbody>
                </table>
              </div>
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">🔗</span>{section_num}. Links &amp; Navigation Audit <span class="count-badge">{len(link_audits)} elements</span></h2>
          <p style="font-family:-apple-system,sans-serif;font-size:0.875rem;color:#6b7280;margin-bottom:1rem;">
            All &lt;a&gt; tags and &lt;button&gt; elements on the Shopify site. Shows navigation destinations and flags missing hrefs or inaccessible buttons.
          </p>
          {sub_html}
        </div>"""

    # ── SECTION: SEO Analysis ──
    from app.models.seo_result import SeoResult as SeoResultModel, PerformanceResult
    seo_results = db.query(SeoResultModel).filter(SeoResultModel.qa_run_id == run_id).order_by(SeoResultModel.page).all()
    perf_results = db.query(PerformanceResult).filter(PerformanceResult.qa_run_id == run_id).order_by(PerformanceResult.page).all()

    if seo_results:
        section_num += 1
        seo_passed = sum(1 for s in seo_results if s.passed)
        seo_failed = sum(1 for s in seo_results if not s.passed)

        by_page_seo: dict[str, list] = defaultdict(list)
        for sr in seo_results:
            by_page_seo[sr.page or "home"].append(sr)

        seo_sub_html = ""
        for page, page_srs in by_page_seo.items():
            page_label = _page_label(page)
            rows = ""
            for sr in page_srs:
                icon = "✅" if sr.passed else "❌"
                rec = f'<div style="font-size:0.75rem;color:#d97706;margin-top:2px;">{_esc(sr.recommendation)}</div>' if sr.recommendation else ""
                sev_html = ""
                if sr.severity and not sr.passed:
                    sev_c = {"critical": "#dc2626", "major": "#d97706", "minor": "#ca8a04"}.get(sr.severity, "#6b7280")
                    sev_html = f'<span style="color:#fff;background:{sev_c};padding:1px 6px;border-radius:10px;font-size:0.6rem;font-weight:700;margin-left:6px;">{sr.severity.upper()}</span>'
                rows += f"""
                <tr style="border-bottom:1px solid #f3f4f6;">
                  <td style="padding:8px;font-size:0.85rem;">{icon}</td>
                  <td style="padding:8px;font-size:0.85rem;font-weight:600;color:#1f2937;">{_esc(sr.label)}{sev_html}</td>
                  <td style="padding:8px;font-size:0.8rem;color:#4b5563;">{_esc(sr.value)}</td>
                </tr>
                {f'<tr><td></td><td colspan="2" style="padding:0 8px 8px;">{rec}</td></tr>' if rec else ''}"""

            seo_sub_html += f"""
            <div style="margin-bottom:1.5rem;">
              <h3 style="font-family:-apple-system,sans-serif;font-size:0.95rem;font-weight:700;color:#374151;margin-bottom:0.5rem;">{page_label}</h3>
              <table style="width:100%;border-collapse:collapse;font-family:-apple-system,sans-serif;">
                <tbody>{rows}</tbody>
              </table>
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">🔍</span>{section_num}. SEO Analysis <span class="count-badge" style="background:#16a34a;">{seo_passed} passed</span> {f'<span class="count-badge">{seo_failed} issues</span>' if seo_failed else ''}</h2>
          {seo_sub_html}
        </div>"""

    # ── SECTION: Performance ──
    if perf_results:
        section_num += 1
        import json as _json

        perf_sub_html = ""
        for pr in perf_results:
            page_label = _page_label(pr.page or "home")
            load_color = "#dc2626" if pr.load_time_ms > 5000 else "#d97706" if pr.load_time_ms > 3000 else "#16a34a"
            ttfb_color = "#d97706" if pr.ttfb_ms > 600 else "#16a34a"
            size_mb = pr.total_size_bytes / 1024 / 1024
            size_color = "#dc2626" if size_mb > 5 else "#16a34a"

            def _fmt_b(b: int) -> str:
                return f"{b/1024/1024:.1f} MB" if b > 1024*1024 else f"{b/1024:.0f} KB"

            def _fmt_ms(ms: int) -> str:
                return f"{ms/1000:.1f}s" if ms > 1000 else f"{ms}ms"

            perf_issues = _json.loads(pr.issues_json) if pr.issues_json else []
            issues_html = ""
            for pi in perf_issues:
                pi_sev_c = {"critical": "#dc2626", "major": "#d97706", "minor": "#ca8a04"}.get(pi.get("severity", ""), "#6b7280")
                issues_html += f"""
                <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:8px 12px;margin-top:6px;font-family:-apple-system,sans-serif;">
                  <div style="font-size:0.8rem;font-weight:600;color:#92400e;">
                    <span style="color:#fff;background:{pi_sev_c};padding:1px 6px;border-radius:10px;font-size:0.6rem;font-weight:700;margin-right:6px;">{pi.get('severity','').upper()}</span>
                    {_esc(pi.get('label',''))}: {_esc(pi.get('value',''))}
                  </div>
                  <div style="font-size:0.75rem;color:#78350f;margin-top:2px;">{_esc(pi.get('recommendation',''))}</div>
                </div>"""

            perf_sub_html += f"""
            <div style="margin-bottom:1.5rem;">
              <h3 style="font-family:-apple-system,sans-serif;font-size:0.95rem;font-weight:700;color:#374151;margin-bottom:0.75rem;">{page_label}</h3>
              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px;">
                <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:10px;text-align:center;font-family:-apple-system,sans-serif;">
                  <div style="font-size:1.25rem;font-weight:800;color:{load_color};">{_fmt_ms(pr.load_time_ms)}</div>
                  <div style="font-size:0.65rem;color:#9ca3af;text-transform:uppercase;font-weight:600;">Load Time</div>
                </div>
                <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:10px;text-align:center;font-family:-apple-system,sans-serif;">
                  <div style="font-size:1.25rem;font-weight:800;color:{ttfb_color};">{_fmt_ms(pr.ttfb_ms)}</div>
                  <div style="font-size:0.65rem;color:#9ca3af;text-transform:uppercase;font-weight:600;">TTFB</div>
                </div>
                <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:10px;text-align:center;font-family:-apple-system,sans-serif;">
                  <div style="font-size:1.25rem;font-weight:800;color:{size_color};">{_fmt_b(pr.total_size_bytes)}</div>
                  <div style="font-size:0.65rem;color:#9ca3af;text-transform:uppercase;font-weight:600;">Page Size</div>
                </div>
                <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:10px;text-align:center;font-family:-apple-system,sans-serif;">
                  <div style="font-size:1.25rem;font-weight:800;color:#1f2937;">{pr.total_resources}</div>
                  <div style="font-size:0.65rem;color:#9ca3af;text-transform:uppercase;font-weight:600;">Requests</div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;font-family:-apple-system,sans-serif;font-size:0.75rem;color:#6b7280;margin-bottom:8px;">
                <div>JS: {pr.js_count} files ({_fmt_b(pr.js_size_bytes)})</div>
                <div>CSS: {pr.css_count} files ({_fmt_b(pr.css_size_bytes)})</div>
                <div>Images: {pr.img_count} ({_fmt_b(pr.img_size_bytes)})</div>
              </div>
              <div style="font-family:-apple-system,sans-serif;font-size:0.75rem;color:#6b7280;">DOM Nodes: {pr.dom_nodes}</div>
              {issues_html}
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="sec-title"><span class="sec-icon">⚡</span>{section_num}. Performance Metrics</h2>
          {perf_sub_html}
        </div>"""

    # ── No issues ──
    if not sections_html:
        sections_html = '<div class="section"><p style="color:#16a34a;font-size:1.1rem;text-align:center;padding:2rem;">✅ No issues found. QA Passed!</p></div>'

    # ── SUMMARY TABLE ──
    status_color = "#16a34a" if run.status == "completed" else "#dc2626"
    result_text = "PASSED ✅" if score >= (project.pass_threshold if project else 90) else "FAILED ❌"
    result_color = "#16a34a" if score >= (project.pass_threshold if project else 90) else "#dc2626"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>QA Report — {project_name} — Run #{run.run_number}</title>
  <script>{auto_print_js}</script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:Georgia,'Times New Roman',serif;background:#fff;color:#1a1a1a;line-height:1.6;overflow-x:hidden;}}
    .page{{max-width:900px;margin:0 auto;padding:2.5rem 2rem;overflow-x:hidden;}}
    table{{table-layout:fixed;width:100%;}}
    td,th{{overflow-wrap:break-word;word-break:break-word;}}
    /* Header */
    .report-header{{border-bottom:3px solid #1e3a5f;padding-bottom:1.5rem;margin-bottom:2rem;}}
    .report-title{{font-size:2rem;font-weight:700;color:#1e3a5f;display:flex;align-items:center;gap:0.5rem;margin-bottom:1.25rem;}}
    .meta-table{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:0.875rem;color:#374151;}}
    .meta-table tr td:first-child{{font-weight:700;padding-right:1rem;white-space:nowrap;color:#6b7280;}}
    .meta-table tr td:last-child{{color:#111827;}}
    /* Score banner */
    .score-banner{{background:#f0f4ff;border:2px solid #c7d2fe;border-radius:10px;padding:1.5rem;margin:2rem 0;display:flex;align-items:flex-start;gap:1.5rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;flex-wrap:wrap;}}
    .score-big{{font-size:2.5rem;font-weight:800;color:{score_color};line-height:1;}}
    .score-label{{font-size:0.7rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;}}
    .score-detail{{display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem 1rem;}}
    .score-detail .item{{text-align:center;}}
    .score-detail .item .val{{font-size:1.1rem;font-weight:700;}}
    .score-detail .item .lbl{{font-size:0.6rem;color:#9ca3af;text-transform:uppercase;}}
    .result-badge{{font-size:1.1rem;font-weight:700;color:{result_color};margin-top:0.25rem;}}
    /* Sections */
    .section{{margin:2.5rem 0;page-break-inside:avoid;}}
    .sec-title{{font-size:1.35rem;font-weight:700;color:#1e3a5f;border-bottom:2px solid #e5e7eb;padding-bottom:0.5rem;margin-bottom:1.25rem;display:flex;align-items:center;gap:0.5rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
    .sec-icon{{font-size:1.2rem;}}
    .count-badge{{background:#1e3a5f;color:#fff;font-size:0.75rem;padding:2px 10px;border-radius:20px;font-weight:600;margin-left:0.5rem;vertical-align:middle;}}
    .subsection{{margin:1.25rem 0 1.75rem;}}
    .sub-title{{font-size:1.05rem;font-weight:700;color:#374151;margin-bottom:0.875rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
    /* Issue blocks */
    .issue-block{{padding:1rem 1.25rem;border-radius:8px;margin-bottom:1rem;page-break-inside:avoid;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;overflow:hidden;}}
    .issue-header-row{{display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;flex-wrap:wrap;}}
    .issue-label{{font-size:0.7rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;}}
    .sev-pill{{color:#fff;padding:2px 10px;border-radius:20px;font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;}}
    .issue-title{{font-size:0.9rem;font-weight:700;color:#1f2937;margin-bottom:0.5rem;line-height:1.4;overflow-wrap:break-word;}}
    .issue-meta{{padding-left:1.25rem;font-size:0.875rem;color:#374151;overflow-wrap:break-word;word-break:break-word;}}
    .issue-meta li{{margin-bottom:0.4rem;line-height:1.5;}}
    .issue-meta code{{background:#f3f4f6;padding:2px 6px;border-radius:3px;font-size:0.75rem;word-break:break-all;display:inline-block;max-width:100%;}}
    .bp-heading{{font-size:0.875rem;font-weight:700;color:#4f46e5;margin:1rem 0 0.5rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
    /* Screenshots */
    .screenshot-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:0.75rem;margin:0.75rem 0;}}
    .ss-block{{border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;}}
    .ss-label{{background:#f3f4f6;padding:0.25rem 0.5rem;font-size:0.7rem;font-weight:700;color:#6b7280;text-transform:uppercase;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
    .ss-img{{width:100%;max-height:300px;object-fit:contain;background:#fff;display:block;}}
    .ssim-badge{{display:inline-block;background:#f0fdf4;border:1px solid #bbf7d0;color:#15803d;padding:2px 10px;border-radius:4px;font-size:0.75rem;font-weight:600;margin-bottom:0.75rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
    /* Passed tests */
    .pass-list{{list-style:none;padding-left:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:0.875rem;color:#374151;}}
    .pass-list li{{padding:0.3rem 0;border-bottom:1px solid #f3f4f6;}}
    /* Footer */
    .footer{{margin-top:3rem;border-top:1px solid #e5e7eb;padding-top:1rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:0.75rem;color:#9ca3af;display:flex;justify-content:space-between;}}
    @media print{{
      body{{background:#fff;}}
      .page{{padding:2rem;}}
      .screenshot-row{{grid-template-columns:1fr 1fr;}}
      *{{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
    }}
  </style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="report-header">
    <div class="report-title">✏️ Website Quality Assurance Report</div>
    <table class="meta-table">
      <tr><td>Project Name:</td><td>{project_name}</td></tr>
      <tr><td>Platform:</td><td>Shopify ({source_type} Design)</td></tr>
      <tr><td>Version Tested:</td><td>Current live build — Run #{run.run_number}</td></tr>
      <tr><td>Test URL:</td><td>{shopify_url}</td></tr>
      <tr><td>Design Source:</td><td>{source_url}</td></tr>
      <tr><td>QA Type:</td><td>{"AI-Powered Analysis + Functional + ADA Compliance" if test_mode == "ai" or source_url == "N/A (AI testing only)" else "Design Comparison + Functional + ADA Compliance"}</td></tr>
      <tr><td>Devices Tested:</td><td>Mobile (375px, 425px), Tablet (768px), Desktop (1024px, 1280px, 1440px, 1920px)</td></tr>
      <tr><td>Report Date:</td><td>{run_date}</td></tr>
    </table>
  </div>

  <!-- Score Banner -->
  <div class="score-banner">
    <div>
      <div class="score-label">Overall Score</div>
      <div class="score-big">{score:.0f}</div>
      <div class="score-label">out of 100</div>
    </div>
    <div>
      <div class="result-badge">{result_text}</div>
      <div class="score-detail" style="margin-top:0.75rem;">
        <div class="item"><div class="val" style="color:#dc2626;">{critical_count}</div><div class="lbl">Critical</div></div>
        <div class="item"><div class="val" style="color:#d97706;">{major_count}</div><div class="lbl">Major</div></div>
        <div class="item"><div class="val" style="color:#ca8a04;">{minor_count}</div><div class="lbl">Minor</div></div>
        <div class="item"><div class="val" style="color:#16a34a;">{pass_count}</div><div class="lbl">Tests Passed</div></div>
        <div class="item"><div class="val" style="color:#dc2626;">{fail_count}</div><div class="lbl">Tests Failed</div></div>
        <div class="item"><div class="val" style="color:#7c3aed;">{len(accessibility_results)}</div><div class="lbl">ADA Issues</div></div>
        <div class="item"><div class="val" style="color:#0369a1;">{link_issues_count}</div><div class="lbl">Link Issues</div></div>
        <div class="item"><div class="val" style="color:{status_color};">{run.status.title()}</div><div class="lbl">Status</div></div>
      </div>
    </div>
  </div>

  <!-- Sections -->
  {sections_html}

  <!-- Footer -->
  <div class="footer">
    <span>Shopify QA AI — Automated Report</span>
    <span>{project_name} | Run #{run.run_number} | {run_date}</span>
  </div>

</div>
</body>
</html>"""

    return html


def generate_pdf_report(db: Session, run_id: int) -> bytes:
    """Generate a PDF report using WeasyPrint."""
    try:
        from weasyprint import HTML  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("WeasyPrint is required for PDF generation.") from exc
    html_content = generate_html_report(db, run_id)
    pdf_bytes: bytes = HTML(string=html_content, base_url=None).write_pdf()
    return pdf_bytes
