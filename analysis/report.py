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
    for old, new in [("\u2019", "\x27"), ("\u2014", "-"), ("\u2013", "-"), ("\u2212", "-"), ("\u2265", ">="), ("\u2264", "<=")]:
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
        [para('improvement over own usual level', 'SmallRR')],
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
    story = [
        para("SUPERR SELECTOR SEASON 2 | ROUND 1", 'EyebrowRR'),
        para('Who improves under pressure?', 'TitleRR'),
        para('How we selected and ranked the top ten batters and bowlers', 'BodyRR'),
        para("Our question is simple: when the match becomes demanding, does a player perform better or worse than their usual level? We used the supplied IPL and T20I data to answer that question separately for batting and bowling. The lists rank improvement, so a player who is excellent all the time may not finish first.", 'BodyRR'),
        Spacer(1, 4),
        Table([[leader('Batter', data['batters'][0]), leader('Bowler', data['bowlers'][0], True)]], colWidths=[249, 249], style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 10)])),
        para('What a positive score means', 'SubRR'),
        para('A positive score means the player improved on their usual performance after we allowed for the match situation. For batters, more runs is better. For bowlers, fewer runs conceded is better. The two lists are separate; a batting score should not be compared with a bowling score.'),
        para('Data used', 'SubRR'),
        table([
            ['Source pack', 'Ranking scope', 'After data-quality checks'],
            [f"{audit['deliveries']:,} deliveries | {audit['matches']:,} matches", f"{audit['scope_deliveries']:,} IPL/T20I deliveries | {audit['scope_matches']:,} matches", f"{audit['retained_deliveries']:,} retained; {audit['oos_deliveries']:,} scored / {audit['oos_matches']} matches"],
        ], [150, 190, 165], compact=True),
        Spacer(1, 6),
        para(f"The rankings use out-of-time deliveries from 2023-2026; {audit['warmup_deliveries']:,} retained 2022 warm-up deliveries train the first evaluation year. The pack also contained {audit['out_of_scope_deliveries']:,} deliveries from other T20 competitions; these were excluded because the brief names IPL and T20I. A T20I-only player may qualify for the challenge ranking if the pressure and usual-play sample rules are met. That is not proof of IPL experience, 2027 auction registration or availability.", 'SmallRR'),
        para(f"Analysis {data['analysis_id']} | Data dates {audit['date_range'][0]} to {audit['date_range'][1]} | {audit['competitions']} IPL/T20I competitions in scope", 'SmallRR'),
        PageBreak(),
        para('How we measure pressure performance', 'SectionRR'),
        para('Which deliveries count as pressure?', 'SubRR'),
        table([
            ['Situation', 'Included when'],
            ['Chase', '60 or fewer legal balls remain AND the required rate is at least 8 runs per over.'],
            ['First innings', '30 or fewer legal balls remain AND at least 3 wickets have fallen.'],
        ], [115, 390], compact=True),
        para("These rules select late chases with sustained run demand and late first innings after wickets have fallen. They give us a clear, reproducible sample, but miss early collapses and can include almost-decided chases. We also tested a rule based on the room left for mistakes while the game was still contested. It produced too few eligible batters for a top ten, so it does not determine these rankings."),
        para('First, allow for the match situation', 'SubRR'),
        para('Scoring eight runs in an over means different things in different situations. We estimate the runs expected on each delivery using earlier seasons only. The model uses the score, wickets lost, balls used, scoring rate, chase required rate, innings, phase and IPL/T20I format. We use standardised features and Ridge regression (alpha = 60). For batting, we subtract expected runs from actual runs. For bowling, we reverse that subtraction so runs saved are positive. Wides are excluded from batting samples; charged wide events remain in bowling samples.'),
        para('Then compare with the player’s usual level', 'SubRR'),
        Table([[para('SCORE = 100 x [pressure residual sum - pressure deliveries x usual residual per delivery] / (pressure deliveries + 60)', 'CardRR')]], colWidths=[505], style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), PALE_PINK), ('BOX', (0, 0), (-1, -1), .7, LINE), ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11), ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)])),
        Spacer(1, 5),
        para('For each player, we calculate their average runs above expectation outside pressure, separately in IPL and T20I. We use the same format mix as their pressure sample. Subtracting that usual level gives improvement under pressure. The separate pressure-performance column compares only with model expectation, without subtracting the usual level.'),
        para('Example: a batter makes 18 runs more than expected across 60 pressure deliveries. Their usual level is 0.10 runs above expectation per delivery. We subtract 60 x 0.10 = 6 runs, leaving 12. The score is 100 x 12 / (60 + 60) = +10 per 100 deliveries. Adding 60 to the denominator reduces extreme estimates from small samples. It is a fixed modelling choice, not extra observed deliveries or a proven optimum.', 'BodyRR'),
        para('How much evidence is enough?', 'SubRR'),
        para('A player needs at least 30 pressure deliveries in five matches, plus 60 ordinary deliveries in five matches. Each format in their pressure sample also needs 30 ordinary deliveries in three matches. We rank the highest score first; ties use pressure-match count, then player ID. To estimate the 95% range, we resample whole matches 400 times and recalculate the usual level each time. A range crossing zero leaves the direction of improvement uncertain. The range assumes the fitted run model is fixed.', 'BodyRR'),
        para('The ranking uses runs only. Wickets taken and striker dismissals (shown as Outs) are reported separately, with no invented run value. The fixed +60 adjustment reduces small-sample estimates; it was not learned as an optimal value from these data.', 'SmallRR'),
        PageBreak(),
    ]

    for key, title in [('batters', 'Top 10 batters under pressure'), ('bowlers', 'Top 10 bowlers under pressure')]:
        players = data[key]
        story += [para(title, 'SectionRR'), para('Ranked by improvement over each player’s usual level. Read the score alongside the match count and range: the order is an estimate, and nearby ranks need not be meaningfully different.', 'BodyRR')]
        rows = [['Rank / player / observed role', 'Improvement / 100', 'Pressure performance / 100', 'Pressure matches', 'IPL balls', 'T20I balls', 'Wickets' if key == 'bowlers' else 'Outs', '95% score range']]
        for p in players:
            rows.append([f"{p['rank']}. {p['name']}\n" + (', '.join(p['roles']) or 'Insufficient role sample'), fmt(p['score']), fmt(p['pressure_score']), str(p['matches']), str(p['ipl_balls']), str(p['t20i_balls']), str(p['dismissals']), f"{fmt(p['interval'][0])} to {fmt(p['interval'][1])}"])
        story += [table(rows, [105, 55, 65, 42, 42, 42, 44, 110], compact=True), Spacer(1, 9)]
        story += [para('Pressure performance measures runs above model expectation (runs saved for bowlers). Improvement also subtracts the player’s usual level. Both include the same small-sample adjustment and are shown per 100 deliveries. The range refers to improvement; if it includes zero, the direction is uncertain.', 'SmallRR'), para('IPL and T20I counts show the source of pressure evidence. Zero means no qualifying pressure deliveries in that format, not zero ability. A positive range does not prove that one player is better than another.', 'SmallRR')]
        if key == 'batters':
            story.append(para('Towhid Hridoy leads the point estimates, based on 77 T20I pressure deliveries in six matches and no IPL pressure deliveries. His range includes zero, so the evidence does not establish a clear positive improvement. Seven of these ten batting ranges include zero. Treat the exact order with care.', 'BodyRR'))
            story.append(PageBreak())
        else:
            story.append(para('Two of these ten bowling ranges include zero. Brijesh Sharma meets the bowling-ranking minimum with 45 pressure deliveries in five matches. His role label is unassigned because phase tags require a separate 60-delivery, five-match sample; this does not mean he is ineligible for the ranking.', 'BodyRR'))
            story.append(PageBreak())

    exclusions = sorted(audit['exclusion_reasons_overlapping'].items(), key=lambda x: (-x[1], x[0]))
    story += [
        para('What we checked and where to be careful', 'SectionRR'),
        para('Does the result hold up?', 'SubRR'),
        para("We resample whole matches 400 times and recalculate each player's score and usual level. We also remove each pressure match in turn and test wider and narrower pressure rules. These checks show how dependent a finding is on particular matches or definitions; they do not establish that the score predicts future success. Earlier-to-later-season player checks were mixed. Reliable prediction of future pressure performance has not been established, and the later seasons were already inspected during development."),
        para("The wider rule uses chase balls remaining <=72 and required rate >=7, or first-innings balls remaining <=36 and wickets lost >=2. The narrower rule uses <=48 and >=9, or <=24 and >=4. These are sensitivity checks, not alternative published rankings.", 'SmallRR'),
        para('Data-quality exclusions', 'SubRR'),
        table([['Reason', 'Matches affected']] + [[reason, str(count)] for reason, count in exclusions], [390, 115], compact=True),
        Spacer(1, 4),
        para(f"Of {audit['scope_matches']} in-scope matches, {audit['excluded_matches']} ({100*audit['excluded_matches']/audit['scope_matches']:.1f}%) were excluded and {audit['retained_matches']} retained. The retained set includes {audit['retained_matches']-audit['oos_matches']} warm-up matches and {audit['oos_matches']} out-of-time evaluation matches. Reason counts overlap. Matches with ambiguous extras types or penalty timing are quarantined because legal-ball use, charged runs or state timing cannot be reconciled safely from the supplied fields. This conservative policy causes selection bias; it does not prove every excluded match is unusable with further investigation.", 'SmallRR'),
        para('Using the findings for RR', 'SubRR'),
        para("Use these lists to identify players worth a closer scouting look, then check their pressure performance, role and sample before making a decision. Improvement alone is not overall quality: a consistently strong player can improve little. Venue, opposition strength and exact batting position are not fully controlled. Wickets have no direct score value, so bowling results measure run prevention rather than complete bowling value. Separate IPL/T20I baselines help comparisons, but do not prove that T20I form will transfer to the IPL."),
        para('The supplied pack does not verify IPL 2027 auction registration, player availability, retention, price, purse or Rajasthan Royals’ final squad gaps. The report therefore presents evidence for the requested player rankings, not a claim that every ranked player can be purchased or should be selected. The Unstop dropdown options were not available for a direct name-to-option check; confirm the final selections match the displayed names.', 'BodyRR'),
        para('Reproduce from the supplied data with analysis/audit.py, analysis/pipeline.py and analysis/report.py. Raw source deliveries remain local; only eligible-player aggregates are included in this report.', 'SmallRR'),
    ]

    story += [
        PageBreak(),
        para('Appendix: the terms in this report', 'SectionRR'),
        para('Understanding the scores', 'SubRR'),
        table([
            ['Term', 'Plain-language meaning'],
            ['Expected runs', 'Runs the historical model estimates for a delivery in that match situation. This is an estimate, not a guaranteed result or venue par score.'],
            ['Contextual residual', 'Actual minus expected batter runs. For bowling, expected minus actual charged runs. Positive means better run output or run prevention than the model expected.'],
            ['Usual baseline / 100', 'The player’s average contextual contribution outside the selected pressure situations, multiplied by 100. Calculated separately for IPL and T20I, then weighted to the player’s pressure mix.'],
            ['Pressure performance / 100', 'Contribution against model expectation on pressure deliveries, adjusted for sample size: 100 x pressure residual sum / (pressure deliveries + 60). This is not the raw scoring rate.'],
            ['Improvement / 100', 'Pressure contribution after subtracting the player’s ordinary contextual baseline and applying the same sample adjustment. This is the ranking score. A consistently excellent player can have little lift if their pressure and ordinary levels are similar.'],
            ['Per 100 deliveries', 'A common scale for comparison, not a claim that the player faced exactly 100 balls. For bowling, wides remain charged delivery events; batting exposure excludes wides.'],
            ['Shrinkage / +60 adjustment', 'A fixed adjustment that pulls estimates from small samples toward zero. At 30 pressure deliveries, one third of the raw lift remains. It is not 60 observed balls, a learned optimum or a fitted empirical Bayes prior.'],
        ], [130, 375], compact=True),
        Spacer(1, 8),
        para('Evidence, reliability and scope', 'SubRR'),
        table([
            ['Term', 'How to interpret it'],
            ['Pressure match / sample', 'A match containing qualifying pressure deliveries for that player. Multiple balls in one match are related observations; 30 balls from five matches are not 30 independent experiments.'],
            ['95% score range', 'An interval from repeatedly resampling whole matches and recalculating the score and ordinary baseline. A range containing zero leaves the direction of improvement uncertain. It is not a 95% chance of winning or a confidence score.'],
            ['Match-cluster bootstrap', 'Resample complete player-match clusters rather than isolated deliveries. Published intervals condition on fitted expectations and the selected pressure rules; they do not include every source of uncertainty.'],
            ['Single-match removal', 'Remove each pressure match in turn, including its ordinary deliveries, and recalculate. Report the lowest resulting score. Any peer rank holds other player scores fixed.'],
            ['Out-of-time evaluation', 'Fit a model on earlier seasons and evaluate it on a later season. The 2022 warm-up trains the first evaluation year. Previously inspected later seasons are not a pristine prospective test.'],
            ['Role sample', 'Observed batting position or bowling phase exposure. Insufficient role sample means the tagging threshold was not met; it does not mean the player has no role or ability.'],
            ['Wickets / dismissals', 'Wickets credited to a bowler or recorded striker dismissals for a batter in pressure situations. Shown as context; they receive no direct run value in the ranking score.'],
        ], [130, 375], compact=True),
        Spacer(1, 6),
        para('Pressure here is an operational match-situation definition. It is not a direct measurement of emotion, a validated universal leverage index, or proof of future IPL auction suitability.', 'SmallRR'),
    ]

    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(LINE); canvas.line(45, 35, A4[0]-45, 35)
        canvas.setFillColor(MUTED); canvas.setFont('Helvetica', 7.2)
        canvas.drawString(45, 23, "Royals' Resolve | SupeRR Selector Round 1")
        canvas.drawRightString(A4[0]-45, 23, f"{doc.page} | {data['analysis_id']}")
        canvas.restoreState()

    output = ROOT / 'results/public/methodology.pdf'
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=45, leftMargin=45, topMargin=40, bottomMargin=46, title='SupeRR Selector Round 1 - Methodology and Evidence', author="Royals' Resolve").build(story, onFirstPage=footer, onLaterPages=footer)
    shutil.copy2(output, ROOT / 'results/public/Royals_Resolve_methodology.pdf')
    front = ROOT / 'frontend/public/results'; front.mkdir(parents=True, exist_ok=True)
    for name in ['analysis.json', 'methodology.pdf']:
        shutil.copy2(ROOT / 'results/public' / name, front / name)
    print(output)


if __name__ == '__main__':
    main()
