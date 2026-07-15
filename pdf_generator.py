"""
Rebuilds interview_qa.pdf from scratch every time it's called, using the DB
as the source of truth. This is what makes "update that one PDF" safe - there
is never more than one file, and it can never drift out of sync with the DB.
"""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from html import escape

from config import PDF_PATH, LEVELS
from db import fetch_all_grouped_by_level

_LEVEL_TITLES = {
    "basic": "Basic",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
}


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="LevelHeading", fontSize=20, spaceAfter=14, spaceBefore=20, textColor=colors.HexColor("#1a1a1a")))
    styles.add(ParagraphStyle(name="TopicHeading", fontSize=13, spaceAfter=6, spaceBefore=14, textColor=colors.HexColor("#444444")))
    styles.add(ParagraphStyle(name="Question", fontSize=11, leading=15, spaceBefore=8, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Answer", fontSize=10, leading=14, spaceBefore=2))
    styles.add(ParagraphStyle(name="Example", fontSize=9, leading=13, spaceBefore=2, textColor=colors.HexColor("#555555"), leftIndent=12))
    styles.add(ParagraphStyle(name="Meta", fontSize=8, leading=11, spaceBefore=2, textColor=colors.HexColor("#888888")))
    return styles


def regenerate_pdf() -> str:
    grouped = fetch_all_grouped_by_level()
    styles = _styles()
    story = []

    story.append(Paragraph("Interview Q&A Notes", styles["Title"]))
    story.append(Spacer(1, 12))

    for level in LEVELS:
        entries = grouped.get(level, [])
        story.append(Paragraph(_LEVEL_TITLES[level], styles["LevelHeading"]))
        if not entries:
            story.append(Paragraph("No entries yet.", styles["Answer"]))
            continue

        current_topic = None
        for row in entries:
            topic = row.get("topic") or "General"
            if topic != current_topic:
                story.append(Paragraph(escape(topic), styles["TopicHeading"]))
                current_topic = topic

            question = escape(row.get("question") or "")
            answer = escape(row.get("answer_summary") or "")
            tech_ans = row.get("technical_answer")
            example = row.get("example")
            company = row.get("company")
            source = row.get("source_url")

            story.append(Paragraph(f"Q: {question}", styles["Question"]))
            story.append(Paragraph(f"Analogy: {answer}", styles["Answer"]))
            if tech_ans:
                story.append(Paragraph(f"Technical: {escape(tech_ans)}", styles["Answer"]))
            if example:
                story.append(Paragraph(f"Example: {escape(example)}", styles["Example"]))

            meta_bits = []
            if company:
                meta_bits.append(f"Company: {escape(company)}")
            if source:
                meta_bits.append(f"Source: {escape(source)}")
            if meta_bits:
                story.append(Paragraph(" | ".join(meta_bits), styles["Meta"]))

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(story)
    return str(PDF_PATH)


if __name__ == "__main__":
    path = regenerate_pdf()
    print(f"Rebuilt {path}")
