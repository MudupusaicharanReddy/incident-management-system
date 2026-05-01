from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "submission"
OUT_FILE = OUT_DIR / "Incident_Management_System_Project_Submission.pdf"
FINAL_OUT_FILE = OUT_DIR / "MudupusaicharanReddy - Infrastructure SRE Intern Assignment.pdf"
GITHUB_URL = "https://github.com/MudupusaicharanReddy/incident-management-system"

INCLUDED_SUFFIXES = {".py", ".jsx", ".css", ".html", ".json", ".txt", ".yml", ".md", ".dockerfile"}
EXCLUDED_PARTS = {
    ".git",
    ".python-packages",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "submission",
}


def project_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        suffix = path.suffix.lower()
        if suffix in INCLUDED_SUFFIXES or path.name in {"Dockerfile", ".gitignore"}:
            files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(ROOT)).lower())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def add_heading(story: list, text: str, styles, level: int = 1) -> None:
    style = styles["Heading1"] if level == 1 else styles["Heading2"]
    story.append(Paragraph(text, style))
    story.append(Spacer(1, 0.12 * inch))


def add_bullets(story: list, items: list[str], styles) -> None:
    for item in items:
        story.append(Paragraph(f"- {item}", styles["Body"]))
    story.append(Spacer(1, 0.08 * inch))


def make_file_tree(files: list[Path]) -> str:
    return "\n".join(str(path.relative_to(ROOT)).replace("\\", "/") for path in files)


def build_pdf() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=13,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=7,
            leading=8.4,
            borderColor=colors.HexColor("#D8E0E7"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#F7FAFC"),
        )
    )

    doc = SimpleDocTemplate(
        str(OUT_FILE),
        pagesize=A4,
        rightMargin=0.58 * inch,
        leftMargin=0.58 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.62 * inch,
        title="Incident Management System Project Submission",
    )
    story: list = []

    story.append(Paragraph("Incident Management System", styles["Title"]))
    story.append(Paragraph("Engineering Assignment Project Submission", styles["Heading2"]))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}", styles["Body"]))
    story.append(Paragraph(f"GitHub Repository: {GITHUB_URL}", styles["Body"]))
    story.append(Spacer(1, 0.22 * inch))

    summary = (
        "This repository implements a mission-critical Incident Management System for ingesting "
        "high-volume infrastructure signals, debouncing repeated failures into work items, "
        "tracking incident state, enforcing RCA before closure, and providing a responsive dashboard."
    )
    story.append(Paragraph(summary, styles["Body"]))

    add_heading(story, "Implemented Requirements", styles)
    add_bullets(
        story,
        [
            "Async signal ingestion with FastAPI and a bounded asyncio queue.",
            "Rate limiting through a token-bucket guard on ingestion APIs.",
            "10-second component-level debouncing so repeated signals create one incident.",
            "Separated storage modules for raw signals, incidents/RCA, hot dashboard state, and aggregations.",
            "Alerting Strategy pattern for component-specific severity and channels.",
            "State-machine workflow for OPEN, INVESTIGATING, RESOLVED, and CLOSED.",
            "Mandatory RCA validation before closing incidents.",
            "Automatic MTTR calculation from first signal to RCA incident end.",
            "React dashboard with live feed, incident detail, raw signals, status controls, and RCA form.",
            "Docker Compose, sample data replay script, tests, README, and planning docs.",
        ],
        styles,
    )

    add_heading(story, "Architecture", styles)
    arch = """
Producers -> FastAPI Ingestion API -> Bounded Async Queue -> Async Signal Workers
Workers -> Raw Signal Lake
Workers -> Incident Repository
Workers -> Timeseries Aggregations
Incident Repository + Aggregations -> Hot Dashboard Cache -> React Dashboard
React Dashboard -> Incident APIs for status updates and RCA submission
""".strip()
    story.append(Preformatted(arch, styles["CodeBlock"]))
    story.append(Spacer(1, 0.12 * inch))

    add_heading(story, "Tech Stack", styles)
    table = Table(
        [
            ["Layer", "Choice"],
            ["Backend", "Python, FastAPI, Pydantic, asyncio"],
            ["Frontend", "React, Vite, lucide-react"],
            ["Testing", "pytest"],
            ["Packaging", "Docker Compose"],
            ["Persistence in assignment", "In-memory stores with production-like boundaries"],
        ],
        colWidths=[1.55 * inch, 4.6 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5DF")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.16 * inch))

    add_heading(story, "Run Instructions", styles)
    story.append(Preformatted("docker compose up --build", styles["CodeBlock"]))
    story.append(Paragraph("Frontend: http://localhost:3000", styles["Body"]))
    story.append(Paragraph("Backend API docs: http://localhost:8000/docs", styles["Body"]))
    story.append(Paragraph("Health endpoint: http://localhost:8000/health", styles["Body"]))
    story.append(Paragraph("Sample data: python scripts/replay_sample.py", styles["Body"]))

    add_heading(story, "Validation", styles)
    story.append(Paragraph("Backend tests cover RCA closure validation and debouncing behavior.", styles["Body"]))
    story.append(Preformatted("backend/tests: 4 passed", styles["CodeBlock"]))

    files = project_files()
    add_heading(story, "Project File Tree", styles)
    story.append(Preformatted(make_file_tree(files), styles["CodeBlock"]))

    story.append(PageBreak())
    add_heading(story, "Source Code Appendix", styles)
    story.append(Paragraph("The following appendix contains the submit-ready project source files.", styles["Body"]))

    for path in files:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        story.append(PageBreak())
        add_heading(story, rel, styles, level=2)
        text = read_text(path)
        wrapped_lines = []
        for line in text.splitlines():
            if len(line) <= 110:
                wrapped_lines.append(line)
            else:
                wrapped_lines.extend(wrap(line, width=110, subsequent_indent="    "))
        story.append(Preformatted("\n".join(wrapped_lines) or "[empty file]", styles["CodeBlock"]))

    doc.build(story)
    if OUT_FILE != FINAL_OUT_FILE:
        FINAL_OUT_FILE.write_bytes(OUT_FILE.read_bytes())


if __name__ == "__main__":
    build_pdf()
    print(FINAL_OUT_FILE)
