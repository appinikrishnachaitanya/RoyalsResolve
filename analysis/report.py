"""Build the short, plain-language methodology PDF from public aggregates."""
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor('#172447')
PINK = colors.HexColor('#C21868')
MUTED = colors.HexColor('#626D83')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='Cover', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=28, leading=34, textColor=NAVY, spaceAfter=18))
styles.add(ParagraphStyle(name='Section', parent=styles['Heading1'], fontSize=20, leading=25, textColor=NAVY, spaceAfter=12))
styles.add(ParagraphStyle(name='Subsection', parent=styles['Heading2'], fontSize=13, leading=17, textColor=PINK, spaceBefore=9, spaceAfter=5))
styles.add(ParagraphStyle(name='BodyPlain', parent=styles['BodyText'], fontSize=10, leading=15, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name='TablePlain', parent=styles['BodyText'], fontSize=8, leading=11, textColor=NAVY))
styles.add(ParagraphStyle(name='Note', parent=styles['BodyText'], fontSize=8, leading=12, textColor=MUTED, spaceAfter=6))


def para(value, style='BodyPlain'):
    text = str(value).replace('\u2019', "'").replace('\u2013', '-').replace('\u2014', '-').replace('\u2265', '>=').replace('\u2264', '<=').replace('\u2212', '-')
    return Paragraph(escape(text).replace('\n', '<br/>'), styles[style])


def table(rows, widths):
    cells = [[para(cell, 'TablePlain') for cell in row] for row in rows]
    result = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5EFF7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), 1, PINK),
        ('LINEBELOW', (0, 1), (-1, -1), .35, colors.HexColor('#DDE1E9')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return result


def main():
    data = json.loads((ROOT / 'results/public/analysis.json').read_text(encoding='utf-8'))
    audit = data['audit']
    story = [
        para("ROYALS' RESOLVE", 'Subsection'), Spacer(1, 34),
        para('Pressure Calculation', 'Cover'),
        para('A short guide to what the score means, how it is calculated, and what the data can support.'),
        Spacer(1, 15),
        para(f"Analysis {data['analysis_id']}  |  Data: {audit['date_range'][0]} to {audit['date_range'][1]}", 'Note'),
        para(f"{audit['deliveries']:,} supplied deliveries across {audit['matches']:,} matches. The report uses a smaller retained sample after the documented exclusions.", 'BodyPlain'),
        para('These lists describe contextual runs in selected situations. They are not a measure of total player quality and are not auction recommendations.', 'Note'),
        PageBreak(),
        para('How to read the score', 'Section'),
        para('First, compare the score with zero. A positive batting score means more batter runs than the model expected. A positive bowling score means fewer charged runs than expected. Higher is better within the same role; batting and bowling scores should not be compared with each other.'),
        para('The zero line means a player scored exactly what the expected-runs model predicted for the pressure deliveries. Each player result is pulled partway toward zero so a small sample does not dominate the ranking.', 'BodyPlain'),
        para('The calculation', 'Subsection'),
        table([
            ['Step', 'Plain-language calculation'],
            ['1. Expected runs', 'Use earlier seasons to estimate runs for similar match situations.'],
            ['2. Delivery result', 'Batting: batter runs minus expected runs. Bowling: expected charged runs minus actual charged runs.'],
            ['3. Player score', '100 x total delivery result / (pressure deliveries + 60).'],
        ], [105, 400]),
        Spacer(1, 8),
        para('Example: 120 pressure deliveries produced 18 more runs than expected. The score is 100 x 18 / (120 + 60) = +10 runs per 100 pressure deliveries.', 'BodyPlain'),
        para('What counts as a pressure situation?', 'Subsection'),
        para('Chase: 60 or fewer legal balls remain and the required rate is at least 8 runs per over. First innings: 30 or fewer legal balls remain and at least 3 wickets have fallen. The strict margin rule did not find enough eligible players for both lists, so this stated fallback is used for both roles.'),
        para('A player needs at least 30 pressure deliveries across 5 matches. The 95% range resamples whole matches; if it crosses zero, the evidence does not clearly separate the score from zero. Wickets are reported separately and are not assigned an unvalidated run value.', 'Note'),
        PageBreak(),
    ]
    for label, role_word in [('batters', 'Batting'), ('bowlers', 'Bowling')]:
        story += [para(f"Top 10 {label}", 'Section'), para(f"Ordered from highest to lowest {role_word.lower()} score. Each estimate is shown with its sample and 95% range.", 'BodyPlain')]
        rows = [['Rank / player', 'Observed role evidence', 'Score / 100', 'Matches', '95% range']]
        for player in data[label]:
            rows.append([
                f"{player['rank']}. {player['name']}", ', '.join(player['roles']) or 'Not established',
                f"{player['score']:+.1f}", str(player['matches']),
                f"{player['interval'][0]:+.1f} to {player['interval'][1]:+.1f}",
            ])
        story += [table(rows, [145, 116, 68, 54, 122]), para('Role labels need 60 role events across 5 matches. Batting roles come from recorded batting order or actual late-innings batting exposure; bowlers’ phase labels describe bowling only. A player may have evidence for more than one batting role.', 'Note'), PageBreak()]

    story += [para('Data, checks and limits', 'Section'), para(f"The source pack contains {audit['deliveries']:,} deliveries and {audit['matches']:,} matches. {audit['retained_deliveries']:,} deliveries from {audit['retained_matches']:,} matches were retained for this analysis; {audit['excluded_deliveries']:,} deliveries were excluded under the documented data-quality rules."), para('Why matches were excluded', 'Subsection')]
    story.append(table([['Reason', 'Matches affected']] + [[reason, str(count)] for reason, count in audit['exclusion_reasons_overlapping'].items()], [390, 115]))
    story += [Spacer(1, 8), para('Exclusion reasons can overlap, so match counts in this table should not be added together.', 'Note'), para('What the checks can and cannot say', 'Subsection'), para('Expected runs are estimated from earlier seasons and evaluated on later matches. Match-bootstrap ranges describe uncertainty in the player average, conditional on that expected-runs model; they do not include every source of model uncertainty. The 2026 check was not a prospectively sealed test.'), para('The data does not validate a combined wicket-and-run score, venue adjustment, auction price, 2027 availability, or a psychological measure of pressure. Missing evidence is not treated as poor ability. Verify official squad and auction information separately before making decisions.', 'BodyPlain'), para(f"Reproduce from the supplied data using the repository pipeline. Analysis ID: {data['analysis_id']}.", 'Note')]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(45, 25, 'Royals Resolve | Pressure Calculation')
        canvas.drawRightString(A4[0] - 45, 25, str(document.page))
        canvas.restoreState()

    path = ROOT / 'results/public/methodology.pdf'
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=45, leftMargin=45, topMargin=44, bottomMargin=42, title='Royals Resolve - Pressure Calculation', author="Royals' Resolve").build(story, onFirstPage=footer, onLaterPages=footer)
    target = ROOT / 'frontend/public/results'
    target.mkdir(parents=True, exist_ok=True)
    for name in ['analysis.json', 'methodology.pdf']:
        shutil.copy2(ROOT / 'results/public' / name, target / name)
    print(path)


if __name__ == '__main__':
    main()
