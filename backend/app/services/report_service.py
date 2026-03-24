from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.comparison import Comparison
from app.models.functional_test import FunctionalTest, FunctionalTestStatus
from app.models.issue import Issue, IssueSeverity
from app.models.qa_run import QaRun


def _severity_badge(severity: str) -> str:
    colors = {
        "critical": "#dc2626",
        "major": "#ea580c",
        "minor": "#ca8a04",
    }
    color = colors.get(severity.lower(), "#6b7280")
    label = severity.capitalize()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.75rem;font-weight:600;">{label}</span>'
    )


def _status_badge(status: str) -> str:
    if status in ("pass",):
        color = "#16a34a"
    elif status in ("fail",):
        color = "#dc2626"
    else:
        color = "#6b7280"
    label = status.capitalize()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.75rem;font-weight:600;">{label}</span>'
    )


def generate_html_report(db: Session, run_id: int) -> str:
    """Generate a professional HTML QA report for the given run."""
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    issues = db.query(Issue).filter(Issue.qa_run_id == run_id).all()
    functional_tests = db.query(FunctionalTest).filter(FunctionalTest.qa_run_id == run_id).all()
    comparisons = db.query(Comparison).filter(Comparison.qa_run_id == run_id).all()

    # Counts
    critical_count = sum(1 for i in issues if i.severity == IssueSeverity.critical)
    major_count = sum(1 for i in issues if i.severity == IssueSeverity.major)
    minor_count = sum(1 for i in issues if i.severity == IssueSeverity.minor)
    pass_count = sum(1 for ft in functional_tests if ft.status == FunctionalTestStatus.pass_)
    fail_count = sum(1 for ft in functional_tests if ft.status == FunctionalTestStatus.fail)

    score_str = f"{run.overall_score:.1f}" if run.overall_score is not None else "N/A"

    # Build issues rows
    issue_rows = ""
    for issue in issues:
        bp = str(issue.breakpoint) if issue.breakpoint is not None else "—"
        suggestion = issue.ai_suggestion or "—"
        issue_rows += f"""
        <tr>
          <td>{issue.page}</td>
          <td>{bp}</td>
          <td>{_severity_badge(issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity))}</td>
          <td>{issue.description}</td>
          <td>{suggestion}</td>
        </tr>"""

    # Build functional test rows
    ft_rows = ""
    for ft in functional_tests:
        error = ft.error_message or "—"
        status_val = ft.status.value if hasattr(ft.status, "value") else str(ft.status)
        ft_rows += f"""
        <tr>
          <td>{ft.test_name}</td>
          <td>{_status_badge(status_val)}</td>
          <td>{error}</td>
        </tr>"""

    # Build SSIM rows
    ssim_rows = ""
    for comp in comparisons:
        score = f"{comp.ssim_score:.4f}" if comp.ssim_score is not None else "—"
        ssim_rows += f"""
        <tr>
          <td>{comp.page}</td>
          <td>{comp.breakpoint}</td>
          <td>{score}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>QA Report — Run #{run.run_number}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f9fafb; color: #111827; padding: 2rem; }}
    h1 {{ font-size: 1.75rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.25rem; margin: 2rem 0 0.75rem; border-bottom: 2px solid #e5e7eb;
          padding-bottom: 0.5rem; }}
    .meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 2rem; }}
    .summary-grid {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }}
    .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
             padding: 1rem 1.5rem; min-width: 120px; }}
    .card .label {{ font-size: 0.75rem; color: #6b7280; text-transform: uppercase;
                    letter-spacing: 0.05em; }}
    .card .value {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff;
             border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;
             margin-bottom: 1rem; }}
    th {{ background: #f3f4f6; padding: 0.75rem 1rem; text-align: left;
          font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
          color: #6b7280; }}
    td {{ padding: 0.75rem 1rem; border-top: 1px solid #f3f4f6;
          font-size: 0.875rem; vertical-align: top; }}
    tr:hover td {{ background: #f9fafb; }}
    .no-data {{ color: #9ca3af; font-style: italic; padding: 1rem; }}
  </style>
</head>
<body>
  <h1>QA Report</h1>
  <p class="meta">Run #{run.run_number} &bull; Status: {run.status} &bull; Score: {score_str}</p>

  <h2>Executive Summary</h2>
  <div class="summary-grid">
    <div class="card">
      <div class="label">Overall Score</div>
      <div class="value">{score_str}</div>
    </div>
    <div class="card">
      <div class="label">Critical</div>
      <div class="value" style="color:#dc2626;">{critical_count}</div>
    </div>
    <div class="card">
      <div class="label">Major</div>
      <div class="value" style="color:#ea580c;">{major_count}</div>
    </div>
    <div class="card">
      <div class="label">Minor</div>
      <div class="value" style="color:#ca8a04;">{minor_count}</div>
    </div>
    <div class="card">
      <div class="label">Tests Passed</div>
      <div class="value" style="color:#16a34a;">{pass_count}</div>
    </div>
    <div class="card">
      <div class="label">Tests Failed</div>
      <div class="value" style="color:#dc2626;">{fail_count}</div>
    </div>
  </div>

  <h2>Visual Issues ({len(issues)})</h2>
  {"<table><thead><tr><th>Page</th><th>Breakpoint</th><th>Severity</th><th>Description</th><th>Suggestion</th></tr></thead><tbody>" + issue_rows + "</tbody></table>" if issues else '<p class="no-data">No visual issues found.</p>'}

  <h2>Functional Tests ({len(functional_tests)})</h2>
  {"<table><thead><tr><th>Test Name</th><th>Status</th><th>Error</th></tr></thead><tbody>" + ft_rows + "</tbody></table>" if functional_tests else '<p class="no-data">No functional tests recorded.</p>'}

  <h2>SSIM Scores ({len(comparisons)})</h2>
  {"<table><thead><tr><th>Page</th><th>Breakpoint</th><th>SSIM Score</th></tr></thead><tbody>" + ssim_rows + "</tbody></table>" if comparisons else '<p class="no-data">No comparison data available.</p>'}
</body>
</html>"""

    return html


def generate_pdf_report(db: Session, run_id: int) -> bytes:
    """Generate a PDF report using WeasyPrint."""
    try:
        from weasyprint import HTML  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("WeasyPrint is required for PDF generation. Install it with: pip install weasyprint") from exc

    html_content = generate_html_report(db, run_id)
    pdf_bytes: bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
