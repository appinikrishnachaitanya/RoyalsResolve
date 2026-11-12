"""Build the Round 1 methodology and evidence PDF from the versioned analysis."""
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
GOLD = colors.HexColor('#A57937')
MUTED = colors.HexColor('#626D83')
PALE = colors.HexColor('#F5F6F9')
PALE_PINK = colors.HexColor('#FBF3F8')
LINE = colors.HexColor('#DDE2EA')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='EyebrowRR', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=GOLD, spaceAfter=5))
styles.add(ParagraphStyle(name='TitleRR', fontName='Helvetica-Bold', fontSize=25, leading=30, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name='SectionRR', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name='SubRR', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=PINK, spaceBefore=8, spaceAfter=4))
styles.add(ParagraphStyle(name='BodyRR', fontName='Helvetica', fontSize=9, leading=13, textColor=NAVY, spaceAfter=6))
styles.add(ParagraphStyle(name='SmallRR', fontName='Helvetica', fontSize=7.4, leading=10, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle(name='CellRR', fontName='Helvetica', fontSize=7.2, leading=9.2, textColor=NAVY))
styles.add(ParagraphStyle(name='HeadRR', fontName='Helvetica-Bold', fontSize=7, leading=8.5, textColor=NAVY))
styles.add(ParagraphStyle(name='BigRR', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=PINK))
styles.add(ParagraphStyle(name='CardRR', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=NAVY))


def para(text, style='BodyRR'):
    value = str(text)
    for old, new in [('’', "'"), ('–', '-'), ('—', '-'), ('−', '-'), ('·', '|'), ('≥', '>='), ('≤', '<=')]:
        value = value.replace(old, new)
    return Paragraph(escape(value).replace('\n', '<br/>'), styles[style])


def table(rows, widths, compact=False):
    data = [[para(v, 'HeadRR' if i == 0 else 'CellRR') for v in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    pad = 4 if compact else 6
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PALE_PINK),
        ('LINEBELOW', (0, 0), (-1, 0), 1, PINK),
        ('LINEBELOW', (0, 1), (-1, -1), .35, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), pad), ('RIGHTPADDING', (0, 0), (-1, -1), pad),
        ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
    ]))
    return t


def fmt(value, digits=1):
    return f'{float(value):+.{digits}f}'


def leader(role, player, bowling=False):
    rows = [
        [para(role.upper() + ' / RANK 1', 'EyebrowRR')],
        [para(player['name'], 'CardRR')],
        [para(fmt(player['score']) + ' per 100', 'BigRR')],
        [para('pressure lift vs own usual level', 'SmallRR')],
        [para(f"{player['matches']} pressure matches | {player['balls']} deliveries", 'SmallRR')],
        [para(f"IPL {player['ipl_balls']} | T20I {player['t20i_balls']}", 'SmallRR')],
        [para(f"95% range {fmt(player['interval'][0])} to {fmt(player['interval'][1])}", 'SmallRR')],
    ]
    card = Table(rows, colWidths=[238], hAlign='LEFT')
    card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PALE_PINK if not bowling else PALE),
        ('BOX', (0, 0), (-1, -1), .7, LINE),
        ('LINEBEFORE', (0, 0), (0, -1), 3, PINK if not bowling else NAVY),
        ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return card


def main():
    data = json.loads((ROOT / 'results/public/analysis.json').read_text(encoding='utf-8'))
    audit = data['audit']
    shaheen = next((p for p in data['bowlers_all'] if p['name'] == 'Shaheen Afridi'), None)
    shaheen_note = (f"Shaheen Afridi has {shaheen['t20i_balls']} T20I pressure deliveries and {shaheen['ipl_balls']} IPL pressure deliveries; the revised combined list places him at rank {shaheen['rank']}, outside the top ten. This is challenge evidence, not IPL auction eligibility." if shaheen else 'Shaheen Afridi is not in the top ten under the stated score ordering; a T20I-only sample does not make an auction claim.')
    story = [
        para("SUPERR SELECTOR SEASON 2 | ROUND 1", 'EyebrowRR'),
        para('Who delivers when it matters?', 'TitleRR'),
        para('Methodology and evidence for the pressure performer rankings', 'BodyRR'),
        para("The Round 1 brief requests top-ten batter and bowler rankings using IPL and T20I data. The player pool therefore includes eligible role samples from either competition. Their pressure and usual-play evidence is compared within format, then weighted to the player's pressure mix.", 'BodyRR'),
        Spacer(1, 4),
        Table([[leader('Batter', data['batters'][0]), leader('Bowler', data['bowlers'][0], True)]], colWidths=[249, 249], style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 10)])),
        para('What a positive score means', 'SubRR'),
        para('The player produced more context-adjusted runs under pressure than in their ordinary deliveries. For bowlers, runs saved are oriented positive. Rank 1 is the highest estimated pressure lift in that role; batting and bowling scores are not compared with one another.'),
        para('Data used', 'SubRR'),
        table([
            ['Source pack', 'Ranking scope', 'After data-quality checks'],
            [f"{audit['deliveries']:,} deliveries | {audit['matches']:,} matches", f"{audit['scope_deliveries']:,} IPL/T20I deliveries | {audit['scope_matches']:,} matches", f"{audit['retained_deliveries']:,} retained; {audit['oos_deliveries']:,} scored / {audit['oos_matches']} matches"],
        ], [150, 190, 165], compact=True),
        Spacer(1, 6),
        para(f"The rankings use out-of-time deliveries from 2023-2026; {audit['warmup_deliveries']:,} retained 2022 warm-up deliveries train the first evaluation year. The pack also contained {audit['out_of_scope_deliveries']:,} deliveries from other T20 competitions; these were excluded because the brief names IPL and T20I. A T20I-only player may qualify for the challenge ranking if the pressure and usual-play sample rules are met. That is not proof of IPL experience, 2027 auction registration or availability.", 'SmallRR'),
        para(f"Analysis {data['analysis_id']} | Data dates {audit['date_range'][0]} to {audit['date_range'][1]} | {audit['competitions']} IPL/T20I competitions in scope", 'SmallRR'),
        PageBreak(),
        para('How pressure and the score are defined', 'SectionRR'),
        para('Pressure situations', 'SubRR'),
        table([
            ['Situation', 'Included when'],
            ['Chase', '60 or fewer legal balls remain AND the required rate is at least 8 runs per over.'],
            ['First innings', '30 or fewer legal balls remain AND at least 3 wickets have fallen.'],
        ], [115, 390], compact=True),
        para(f"The proposed margin rule estimates how many consecutive dot-ball or boundary shocks can occur before task success drops below 20%. The fallback captures late chases with high run demand and late first innings with few balls and wickets already lost. It found {data['margin_eligible_counts']['batting']} eligible batters and {data['margin_eligible_counts']['bowling']} eligible bowlers. Because it could not support both top-ten lists, the documented late-innings fallback above was used for both roles. This is a transparent operational definition, not a validated measure of psychological pressure.", 'BodyRR'),
        para('Expected runs and player baseline', 'SubRR'),
        para('A Ridge model trained on earlier IPL/T20I seasons predicts runs for each delivery from the pre-delivery state: score, wickets lost, balls remaining, required rate, innings, phase and IPL-versus-T20I indicator. Each test season uses earlier seasons only. Batting residual = batter runs - expected batter runs. Bowling residual = expected bowler-charged runs - actual charged runs. Positive residual is better for both roles.'),
        para('Ranked pressure-lift formula', 'SubRR'),
        Table([[para('SCORE = 100 x [pressure residual sum - pressure deliveries x usual residual per delivery] / (pressure deliveries + 60)', 'CardRR')]], colWidths=[505], style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), PALE_PINK), ('BOX', (0, 0), (-1, -1), .7, LINE), ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11), ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)])),
        Spacer(1, 5),
        para('Usual baseline: the player’s average contextual residual on non-pressure deliveries in the same format (IPL or T20I), weighted to match the formats in their pressure sample. Example: pressure residuals total +18 runs over 60 deliveries, while usual output is +0.10 residual runs per delivery. Adjusted total = 18 - (60 x 0.10) = 12; score = 100 x 12 / (60 + 60) = +10 runs per 100 pressure deliveries. The fixed 60-event zero prior shrinks small pressure samples toward zero; it is not 60 observed balls.', 'BodyRR'),
        para('Eligibility and uncertainty', 'SubRR'),
        para('Eligibility is role-specific: at least 30 pressure deliveries across 5 matches; 60 non-pressure deliveries across 5 matches overall; and 30 non-pressure deliveries in 3 matches for every format represented in the pressure sample. Ranks sort by score descending, then pressure matches descending, then player ID. The 95% interval uses 400 match-cluster bootstrap replicates and re-estimates the usual baseline in each replicate. It reflects match-to-match uncertainty conditional on the fitted run model; it does not include model-fitting uncertainty.', 'BodyRR'),
        para('The score uses runs only. Wickets are reported separately and receive no invented run value. No value is added across the six pressure dimensions.', 'SmallRR'),
        PageBreak(),
    ]

    for key, title in [('batters', 'Top 10 batters under pressure'), ('bowlers', 'Top 10 bowlers under pressure')]:
        players = data[key]
        story += [para(title, 'SectionRR'), para('Ordered by pressure lift versus the player’s own usual contextual level. Higher is better; intervals crossing zero indicate uncertainty about the direction of the lift.', 'BodyRR')]
        rows = [['Rank / player', 'Observed role', 'Lift / 100', 'P matches', 'IPL pressure', 'T20I pressure', '95% range']]
        for p in players:
            rows.append([f"{p['rank']}. {p['name']}", ', '.join(p['roles']) or 'Not established', fmt(p['score']), str(p['matches']), str(p['ipl_balls']), str(p['t20i_balls']), f"{fmt(p['interval'][0])} to {fmt(p['interval'][1])}"])
        story += [table(rows, [105, 95, 55, 55, 55, 55, 85], compact=True), Spacer(1, 9)]
        story += [para('Eligibility is based on pressure evidence in the named role and a supported non-pressure baseline. IPL and T20I event counts show where the pressure evidence came from; a zero in one format does not mean zero ability. It means no qualifying pressure deliveries in that format.', 'SmallRR')]
        if key == 'batters':
            story.append(PageBreak())
        else:
            story.append(PageBreak())

    exclusions = sorted(audit['exclusion_reasons_overlapping'].items(), key=lambda x: (-x[1], x[0]))
    last = data['validation'][-1]
    lin = last['models']['logistic']; quad = last['models']['quadratic_logistic']
    story += [
        para('Checks, interpretation and limits', 'SectionRR'),
        para('Consistency and validation', 'SubRR'),
        para(f"Player uncertainty resamples whole matches, not individual balls. The rolling task-model check uses {last['test_matches']} later matches in {last['year']}; the linear model Brier score is {lin['brier']:.3f} and log loss is {lin['log_loss']:.3f}. This checks the match-state task model, not whether player pressure-lift rankings predict future performance. The 2026 data was inspected during this analysis, so it is not a prospectively sealed test.", 'BodyRR'),
        para('Data-quality exclusions', 'SubRR'),
        table([['Reason', 'Matches affected']] + [[reason, str(count)] for reason, count in exclusions], [390, 115], compact=True),
        Spacer(1, 4),
        para('Exclusion reason counts can overlap. Ambiguous extras are the largest source of excluded IPL/T20I matches and may affect which matches are represented.', 'SmallRR'),
        para('What these lists do and do not establish', 'SubRR'),
        para(f"The rankings describe contextual run contribution relative to each player’s usual level in supplied IPL/T20I data. They are not overall talent grades, win-probability predictions, or proof of mental toughness. Venue, opponent, exact batting position, opponent quality and hierarchical season effects are not fully controlled. IPL/T20I cross-format transfer is not established. T20I-only players remain eligible under the brief when they meet these statistical sample rules; they are not presented as auction-available players. {shaheen_note}", 'BodyRR'),
        para('The supplied pack does not verify IPL 2027 auction registration, player availability, retention, price, purse or Rajasthan Royals’ final squad gaps. The report therefore presents evidence for the requested player rankings, not a claim that every ranked player can be purchased or should be selected. RR incumbent comparisons use IPL deliveries only and do not establish a 2027 roster need. The Unstop dropdown options were not available for a direct name-to-option check; confirm the final selections match the displayed names.', 'BodyRR'),
        para('Reproduce from the supplied data with analysis/audit.py, analysis/pipeline.py and analysis/report.py. Raw source deliveries remain local; only eligible-player aggregates are included in this report.', 'SmallRR'),
    ]

    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(LINE); canvas.line(45, 35, A4[0]-45, 35)
        canvas.setFillColor(MUTED); canvas.setFont('Helvetica', 7.2)
        canvas.drawString(45, 23, "Royals' Resolve | SupeRR Selector Round 1")
        canvas.drawRightString(A4[0]-45, 23, f"{doc.page} | {data['analysis_id']}")
        canvas.restoreState()

    output = ROOT / 'results/public/methodology.pdf'
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=45, leftMargin=45, topMargin=40, bottomMargin=46, title='SupeRR Selector Round 1 - Methodology and Evidence', author="Royals' Resolve").build(story, onFirstPage=footer, onLaterPages=footer)
    front = ROOT / 'frontend/public/results'; front.mkdir(parents=True, exist_ok=True)
    for name in ['analysis.json', 'methodology.pdf']:
        shutil.copy2(ROOT / 'results/public' / name, front / name)
    print(output)


if __name__ == '__main__':
    main()
