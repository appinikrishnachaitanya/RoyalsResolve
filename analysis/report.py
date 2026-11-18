"""Build the Round 1 methodology and evidence PDF from the versioned analysis."""
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape
from recruitment import classify_candidate, verified_recruitment_pool

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
        [para(fmt(player['pressure_score']) + ' per 100', 'BigRR')],
        [para('pressure output against expectation', 'SmallRR')],
        [para(f"{player['matches']} pressure matches | {player['balls']} deliveries", 'SmallRR')],
        [para(f"IPL {player['ipl_balls']} | T20I {player['t20i_balls']}", 'SmallRR')],
        [para(f"95% range {fmt(player['pressure_interval'][0])} to {fmt(player['pressure_interval'][1])}", 'SmallRR')],
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
    decision=json.loads((ROOT/'artifacts/private/decision-audit.json').read_text())
    assert decision['analysis_id']==data['analysis_id'],'Run analysis/decision_audit.py for the current analysis'
    auction=json.loads((ROOT/'config/auction_evidence_2027.json').read_text())
    import pandas as pd
    from reportlab.graphics.shapes import Drawing, Line, Circle, String

    evaluated = pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet',
        columns=['is_ipl', 'baseline_pressure', 'extra', 'match_id', 'striker_id',
                 'bowler_id', 'batting_residual', 'bowling_residual'])
    ipl_pressure = evaluated[evaluated.is_ipl & evaluated.baseline_pressure]
    story = [
        para('Pressure performance in IPL and T20I', 'TitleRR'),
        para('Top-ten performance rankings and an evidence-led RR scouting framework', 'BodyRR'),
        para('These are retrospective pressure-performance rankings. Future IPL performance is not demonstrated; auction use should remain supplementary.', 'CardRR'),
        para("We use the supplied IPL and T20I data to compare pressure output, improvement over usual performance and consistency across matches. IPL and T20I deliveries receive equal weight. We rank conservative pressure performance. T20I-only players can qualify. For these selection tables we exclude players mapped to Pakistan or Pakistan A in the supplied data. This is our candidate-pool choice. Their matches still inform contextual expectations.", 'BodyRR'),
        Spacer(1, 4),
        Table([[leader('Batter', data['batters'][0]), leader('Bowler', data['bowlers'][0], True)]], colWidths=[249, 249], style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 10)])),
        para('What a positive score means', 'SubRR'),
        para('Positive pressure performance means output above the contextual model: extra runs for batters or runs saved for bowlers. Positive improvement means better than the player’s usual contextual level. The decision lists first prioritise supported positive pressure output; bowling also considers wicket-taking evidence.'),
        para('Data used', 'SubRR'),
        table([
            ['Source pack', 'Ranking scope', 'After data-quality checks'],
            [f"{audit['deliveries']:,} deliveries | {audit['matches']:,} matches", f"{audit['scope_deliveries']:,} IPL/T20I deliveries | {audit['scope_matches']:,} matches", f"{audit['retained_deliveries']:,} retained; {audit['oos_deliveries']:,} scored / {audit['oos_matches']} matches"],
        ], [150, 190, 165], compact=True),
        Spacer(1, 6),
        para(f"The rankings use out-of-time deliveries from 2023-2026; {audit['warmup_deliveries']:,} retained 2022 warm-up deliveries train the first evaluation year. The pack also contained {audit['out_of_scope_deliveries']:,} deliveries from other T20 competitions; these were excluded because the brief names IPL and T20I. A T20I-only player may qualify for the challenge ranking if the pressure and usual-play sample rules are met. ", 'SmallRR'),
        para(f"Data coverage: {audit['date_range'][0]} to {audit['date_range'][1]}", 'SmallRR'),
        PageBreak(),
        para('How we measure pressure performance', 'SectionRR'),
        para('Which deliveries count as pressure?', 'SubRR'),
        table([
            ['Situation', 'Included when'],
            ['Chase', '60 or fewer legal balls remain AND the required rate is at least 8 runs per over.'],
            ['First innings', '30 or fewer legal balls remain AND at least 3 wickets have fallen.'],
            ['Collapse, either innings', 'At least 2 wickets fell in the preceding 12 legal balls, including early or middle overs.'],
        ], [115, 390], compact=True),
        para("We include a delivery if any rule above holds. In chases, we exclude states needing more than six runs per remaining legal ball, a no-extras plausibility filter rather than a claim that winning is impossible. The collapse rule extends coverage beyond late innings. Labels use only the state before the delivery."),
        para('First, allow for the match situation', 'SubRR'),
        para('Scoring eight runs in an over means different things in different situations. We estimate the runs expected on each delivery using earlier seasons only. The model uses the score, wickets lost, balls used, scoring rate, chase required rate, innings, phase and IPL/T20I format. We use standardised features and Ridge regression (alpha = 60). For batting, we subtract expected runs from actual runs. For bowling, we reverse that subtraction so runs saved are positive. Wides are excluded from batting samples; charged wide events remain in bowling samples.'),
        para('Measure improvement over usual', 'SubRR'),
        Table([[para('PERFORMANCE = 100 x mean pressure contribution x N / (N + 60)\nIMPROVEMENT = 100 x mean [contribution - usual level in that format] x N / (N + 60)', 'CardRR')]], colWidths=[505], style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), PALE_PINK), ('BOX', (0, 0), (-1, -1), .7, LINE), ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11), ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)])),
        Spacer(1, 5),
        para('For each player, we calculate their average runs above expectation outside pressure, separately in IPL and T20I. We use the same format mix as their pressure sample. Subtracting that usual level gives improvement under pressure. The separate pressure-performance column compares only with model expectation, without subtracting the usual level.'),
        para('Example: a batter makes 18 runs more than expected across 60 pressure deliveries. Their usual level is 0.10 runs above expectation per delivery. We subtract 60 x 0.10 = 6 runs, leaving 12. The score is 100 x 12 / (60 + 60) = +10 per 100 deliveries. Adding 60 to the denominator reduces extreme estimates from small samples. The +60 adjustment pulls estimates from smaller samples towards zero. For mixed-format players we compare pressure and ordinary performance within each format, then combine using the observed pressure exposure mix.', 'BodyRR'),
        para('How much evidence is enough?', 'SubRR'),
        para('A player needs at least 30 pressure deliveries in five matches, plus 60 ordinary deliveries in five matches. Each format in their pressure sample also needs 30 ordinary deliveries in three matches. The improvement figure remains available alongside the selection order. To estimate the 95% range, we resample whole matches 400 times and recalculate the usual level each time. The range shows variation across the resampled matches.', 'BodyRR'),
        para('A supported role is required for the decision lists. IPL and T20I receive equal delivery weights; the actual delivery count N is used for the +60 adjustment. Players whose pressure-output lower bound is positive are prioritised first. Batters then rank by that bound. Within each support group, bowling uses non-dominated tiers of that bound and the lower 95% credited-wicket contribution bound, then sorts each tier by its lower pressure-output bound. This is an explicit conservative selection policy, not a learned optimum.', 'SmallRR'),
        PageBreak(),
    ]

    for key, title in [('batters', 'Top 10 batters under pressure'), ('bowlers', 'Top 10 bowlers under pressure')]:
        players = data[key]
        story += [para(title, 'SectionRR'), para('IPL/T20I decision list, with equal delivery weights. Batters rank by conservative pressure output; bowling tiers consider both run control and credited wickets. Improvement over usual is shown separately.', 'BodyRR')]
        if key=='batters':
            rows=[['Rank / player / role','Output /100','95% output','Positive / all','IPL / T20I','Lift /100','Outs / expected']]
            for p in players:
                rows.append([f"{p['rank']}. {p['name']}\n"+', '.join(p['roles']),fmt(p['pressure_score']),f"{fmt(p['pressure_interval'][0])} to {fmt(p['pressure_interval'][1])}",f"{p['positive_pressure_matches']} / {p['matches']}",f"{p['ipl_balls']} / {p['t20i_balls']}",fmt(p['score']),f"{p['dismissals']} / {p['expected_dismissals']:.1f}"])
            story.append(table(rows,[135,55,95,50,55,60,55],compact=True))
            story.append(para('Output measures batter runs above contextual expectation; lift compares with the player’s usual level. Outs / expected is a dismissal-risk diagnostic: more outs than expected flags additional wicket risk. Batting selection uses runs, not a dismissal penalty, so this diagnostic should inform scouting alongside scoring output.', 'SmallRR'))
        else:
            rows=[['Rank / player / role','Output /100','Output lower bound','Wicket lower bound','Positive / all','IPL / T20I','Wickets','Lift /100']]
            for p in players:
                support='S+' if p['evidence_group']==0 else 'S?'
                rows.append([f"{p['rank']}. {p['name']}\n"+', '.join(p['roles'])+f"\n{support} / Tier {p['selection_tier']}",fmt(p['pressure_score']),fmt(p['pressure_interval'][0],4),fmt(p['wicket_interval'][0],4),f"{p['positive_pressure_matches']} / {p['matches']}",f"{p['ipl_balls']} / {p['t20i_balls']}",str(p['dismissals']),fmt(p['score'])])
            story.append(table(rows,[135,50,65,65,50,50,45,45],compact=True))
            story.append(para('S+ means the output lower 95% bound is positive; S? means weaker output support. S+ comes first. Within each group, tiers compare both lower bounds; within a tier, the output lower bound determines order. All contributions are per 100 deliveries after the +60 adjustment. Four decimals expose the sorting inputs, not extra scientific certainty.', 'SmallRR'))
            ex=decision['dominance_example'];a0=ex['a'];b0=ex['b']
            story.append(para(f"Example: {a0['name']} has output / wicket lower bounds {fmt(a0['pressure_interval'][0],4)} / {fmt(a0['wicket_interval'][0],4)}, versus {fmt(b0['pressure_interval'][0],4)} / {fmt(b0['wicket_interval'][0],4)} for {b0['name']}. Both have the same support group; the first is higher on both inputs and therefore dominates the second under this rule. This is a model comparison, not proof of a future head-to-head advantage.", 'SmallRR'))
        most_matches=max(players,key=lambda p:p['matches']);most_balls=max(players,key=lambda p:p['balls'])
        story.append(para(f"{most_matches['name']} has the most pressure matches in this top ten ({most_matches['matches']}); {most_balls['name']} has the most pressure deliveries ({most_balls['balls']}). Positive / all counts matches with above-expectation average run output. IPL / T20I shows the pressure-delivery split.", 'SmallRR'))
        story.append(PageBreak())

    story += [para('Combined evidence versus IPL-only evidence','SectionRR'),
              para('The combined model uses both competitions. The IPL-only check keeps the fitted contextual models fixed, restricts scoring and ordinary baselines to IPL deliveries, and reapplies sample rules, role checks and the same selection policy. It is a scoring comparison, not an IPL-only model refit. T20I-only players have no IPL estimate.')]
    for role,key in [('batting','batters'),('bowling','bowlers')]:
        ipl={p['id']:p for p in decision['roles'][role]['ipl_only']}
        rows=[['Combined rank / player','Combined output','IPL-only rank','IPL-only output / 95% range','IPL pressure deliveries']]
        for p in data[key]:
            q=ipl.get(p['id'])
            rows.append([f"{p['rank']}. {p['name']}"+('\nT20I only' if p['ipl_balls']==0 else ''),fmt(p['pressure_score']),str(q['rank']) if q else 'Not supported',f"{fmt(q['pressure_score'])} [{fmt(q['pressure_interval'][0])}, {fmt(q['pressure_interval'][1])}]" if q else ('No IPL sample' if p['ipl_balls']==0 else 'Below sample rules'),str(p['ipl_balls'])])
        story += [para('Batting' if role=='batting' else 'Bowling','SubRR'),table(rows,[155,65,65,155,65],compact=True)]
    bat_overlap, bowl_overlap = [next(v['overlap'] for v in decision['roles'][role]['stability'] if v['label']=='IPL only') for role in ('batting','bowling')]
    story.append(para(f'IPL-only top-ten overlap is {bat_overlap}/10 for batting and {bowl_overlap}/10 for bowling. Format indicators adjust average scoring context; they do not establish opposition equivalence or transferability. The actual IPL evidence is therefore shown alongside each combined finding.', 'SmallRR'))
    story.append(PageBreak())

    backtest_path=ROOT/'artifacts/private/coach-backtest.json'
    if not backtest_path.exists():raise FileNotFoundError('Run analysis/coach_backtest.py before generating the report')
    backtest=json.loads(backtest_path.read_text())
    if backtest:assert backtest.get('ipl_weight')==data['config']['ipl_evidence_weight'],'Rerun coach backtest for this source weighting'
    story += [
        para('Validation and use of the findings', 'SectionRR'),
        para('Does the result hold up?', 'SubRR'),
        para("We checked results in three ways: resampling whole matches 400 times, removing each pressure match in turn, and testing wider and narrower pressure rules. We also compared earlier-season scores with later-season performance. The results are summarised alongside the match-level evidence."),
        table([['Later IPL season / role','Players measured','Coach order vs later output','Improvement vs later output','Raw rate vs later output']]+[
            [str(r['year'])+' / '+r['role'],str(r['measured']),str(r['correlations']['coach_order']['rho'])+' ['+', '.join(str(v) for v in r['correlations']['coach_order']['interval'])+']',str(r['correlations']['improvement']['rho']),str(r['correlations']['raw_rate']['rho'])]
            for r in (backtest['results'] if backtest else []) if 'correlations' in r], [110,65,110,110,110], compact=True),
        para('Values are rank correlations on identical follow-up cohorts, requiring at least ten IPL pressure deliveries in two matches. Values near zero show little forward association. The checks are exploratory on inspected seasons; coach-order ranges are 95% player-bootstrap intervals and include zero. For bowling, we separately check credited wickets above expectation on the same follow-up cohorts.', 'SmallRR'),
        para('Data preparation and quality checks', 'SubRR'),
        para("The source codes Overstep and other are treated as no-balls. Both carry a one-run penalty; all 489 complete overs containing Overstep and all 216 containing other reconcile to six legal balls under this interpretation. We record bat runs, no-ball penalties and additional byes separately, then check innings endings and the reported result margin. This classification is inferred from the scoring records rather than a provider-confirmed data dictionary.", 'BodyRR'),
        para('Stability of the actual decision lists', 'SubRR'),
        table([['Alternative','Batters: kept / max move','Bowlers: kept / max move','Bowling tier changes','Unavailable: bat / bowl']]+[
            [a['label'],f"{a['overlap']}/10 / {a['max_rank_move']}",f"{b['overlap']}/10 / {b['max_rank_move']}",str(b['tier_changes']),f"{a['unavailable']} / {b['unavailable']}"]
            for a,b in zip(decision['roles']['batting']['stability'],decision['roles']['bowling']['stability'])], [120,95,95,90,105],compact=True),
        para('Kept = top-ten overlap with the published list. Max move and tier changes refer to published top-ten players still sample-qualified; unavailable players are counted separately. Context models stay fixed. Wider/narrower rules retain the collapse branch and change late-demand thresholds; late demand only removes collapses. Prior 30/120 changes only the fixed shrinkage amount; it is a policy sensitivity, not evidence that 60 is an optimum. Different seeds and 2,000 resamples test Monte Carlo stability. Close positions and some tiers move, so the exact order should not be treated as highly reliable.', 'SmallRR'),
        para('Data-quality exclusions', 'SubRR'),

        Spacer(1, 4),
        para(f"Of {audit['scope_matches']} in-scope matches, {audit['excluded_matches']} ({100*audit['excluded_matches']/audit['scope_matches']:.1f}%) were excluded and {audit['retained_matches']} retained. The retained set includes {audit['retained_matches']-audit['oos_matches']} warm-up matches and {audit['oos_matches']} out-of-time evaluation matches. Reason counts overlap. Matches with unresolved penalties, incomplete innings or failed reconciliation checks are excluded. No-ball deliveries are included with their team and bowler charges recorded separately.", 'SmallRR'),

    ]

    story.append(PageBreak())
    story += [
        para('What changes when consistency comes first?', 'SectionRR'),
        para('The published order prioritises strong pressure output with statistical support. Improvement compares that output with the player’s usual level. Match consistency counts how often the player beats the model expectation across pressure matches.'),
        para('As a sensitivity check, we first prioritised players with positive improvement and above-expected output in more than half of their pressure matches, preserving the published order within each group. This is a descriptive test of a simple rule. The thresholds are illustrative and have no demonstrated forecasting advantage.'),
    ]
    rows = [['Role', 'Published picks retained', 'Players entering the top ten']]
    for label, key in [('Batting', 'batters'), ('Bowling', 'bowlers')]:
        ranked = data[key+'_all']
        alternative = sorted(ranked, key=lambda p: not (
            p['score'] > 0 and 2*p['positive_pressure_matches'] > p['matches']))[:10]
        published_ids = {p['id'] for p in data[key]}
        entrants = [p['name'] for p in alternative if p['id'] not in published_ids]
        rows.append([label, f'{10-len(entrants)}/10', ', '.join(entrants) or 'None'])
    story.append(table(rows, [85, 115, 305]))
    story += [
        para('Output and improvement tell different stories', 'SubRR'),
        para('Each dot represents a published top-ten player. Right of zero means improvement over usual. Higher means more runs scored or saved above contextual expectation.', 'SmallRR'),
    ]
    chart = Drawing(505, 190)
    players = data['batters'] + data['bowlers']
    xmin = min(0, min(p['score'] for p in players))-3
    xmax = max(p['score'] for p in players)+3
    ymax = max(p['pressure_score'] for p in players)+4
    x = lambda value: 44+427*(value-xmin)/(xmax-xmin)
    y = lambda value: 32+127*value/ymax
    chart.add(Line(44, 32, 471, 32, strokeColor=MUTED))
    chart.add(Line(x(0), 32, x(0), 159, strokeColor=MUTED))
    chart.add(String(44, 172, 'Pressure output per 100', fontSize=9))
    chart.add(String(165, 5, 'Improvement over usual per 100', fontSize=9))
    for value in range(0, int(ymax), 10):
        chart.add(String(23, y(value)-3, str(value), fontSize=8))
    for value in range(-40, 61, 10):
        if xmin <= value <= xmax:
            chart.add(String(x(value)-6, 20, str(value), fontSize=8))
    for name, key, color, left in [
        ('Batters', 'batters', colors.HexColor('#A52560'), 340),
        ('Bowlers', 'bowlers', colors.HexColor('#234A80'), 412),
    ]:
        chart.add(Circle(left, 174, 3, fillColor=color, strokeColor=None))
        chart.add(String(left+7, 171, name, fontSize=8))
        for player in data[key]:
            chart.add(Circle(x(player['score']), y(player['pressure_score']), 3,
                             fillColor=color, strokeColor=None))
    story.append(chart)
    rows = [['IPL follow-up', 'Bowling order vs wickets', 'Wicket lower bound vs wickets']]
    for record in backtest['results']:
        correlations = record.get('wicket_correlations')
        if correlations:
            values = [correlations[key] for key in ['coach_order', 'wicket_lower_bound']]
            rows.append([str(record['year'])]+[
                f"{value['rho']:+.3f} [{value['interval'][0]:+.3f}, {value['interval'][1]:+.3f}]"
                if value['interval'] is not None and value['rho'] is not None else 'Unavailable'
                for value in values])
    story += [
        para('Can the bowling ratings forecast wickets?', 'SubRR'),
        para('Rank correlations with next-season IPL credited wickets above expectation per 100 pressure deliveries. Brackets are 95% player-bootstrap ranges.', 'SmallRR'),
        table(rows, [115, 195, 195], compact=True),
    ]
    story.append(para('The historical ranking summarises performance in observed assignments. The low forward correlations and the IPL-only bowling overlap limit its use for forecasting. For RR, the direct IPL sample, role and uncertainty should drive follow-up alongside verified auction status.'))
    story.append(PageBreak())
    story += [para('RR Auction Strategy', 'SectionRR'),
              para('The statistical lists are not the recruitment pool. We analyse IPL/T20I performance first, apply documented status checks second, and assess RR role fit third. The Unstop dropdown establishes challenge selectability. Auction availability is assessed separately for every scouting candidate.'),
              para('Verified squad context: announcements dated 17 November 2026','SubRR'),
              para('RR reports a 19-player squad, six maximum vacancies and INR 27.05 crore remaining. Shami and Siddharth join an existing core including Archer, Sandeep, Jadeja and Bishnoi; Hetmyer is among the departures. Our role hypothesis is to review late-innings batting depth first, then specialist bowling cover, rather than assume every high-ranked role is a squad gap.'),
              para('Performance benchmarks, not auction targets','SubRR'),
              table([['Players','Documented status','Decision']]+[
                  ['Suryakumar Yadav / Jasprit Bumrah','Continuing with Mumbai Indians','Retained-player benchmarks; not part of the released-player acquisition review.'],
                  ['Sunil Narine','Retained by KKR','Spin benchmark; not an auction purchase recommendation.']], [155,145,205]),
              para('Released players to scout by role','SubRR')]
    watch = [
        ('M Shahrukh Khan', 'batting', 'Finisher to review first after Hetmyer’s departure. Compare his death-overs scoring with RR’s current options.'),
        ('Matheesha Pathirana', 'bowling', 'Specialist death cover for Archer. Strong direct IPL pressure evidence. Check fitness and overseas slot.'),
        ('Abishek Porel', 'batting', 'Opening or middle-order depth. Consider if RR needs flexible batting cover.'),
        ('Nitish Rana', 'batting', 'Middle-order depth if RR needs an experienced alternative. Review against the current batting unit.'),
        ('Gerald Coetzee', 'bowling', 'Overseas pace cover. Review his specific assignments because IPL-only output is uncertain.'),
        ('Ishant Sharma', 'bowling', 'Domestic seam cover across phases. Consider if preserving an overseas slot matters.'),
        ('Nehal Wadhera', 'batting', 'Middle and late-overs depth. Listed uncapped at the 2025 auction. Exploratory option given below-expected IPL pressure output.'),
        ('Jacob Bethell', 'batting', 'Flexible batting prospect. The direct IPL pressure sample is too small for a supported estimate.'),
        ('Trent Boult', 'bowling', 'New-ball alternative if RR needs specialist cover. Compare powerplay output with Shami and Archer.'),
        ('Dushmantha Chameera', 'bowling', 'Overseas pace depth across phases. Watchlist option with insufficient support for an IPL-only estimate.'),
        ('Rahul Tripathi', 'batting', 'Domestic middle-order alternative. Review his scoring against pace and spin in RR’s intended batting position.'),
        ('Shimron Hetmyer', 'batting', 'Familiar finishing benchmark and possible return option. His IPL pressure output was below expectation.'),
        ('Kamindu Mendis', 'batting', 'Overseas middle-order and late-overs option. Review how often RR could field him in that role.'),
        ('Rachin Ravindra', 'batting', 'Overseas opening or middle-order cover if squad balance calls for another top-order option.'),
        ('Matthew Short', 'batting', 'Overseas top-order alternative. Compare with RR’s established openers before spending a slot.'),
        ('Avesh Khan', 'bowling', 'Domestic pace alternative for death and powerplay cover. Compare his death-overs assignments with RR’s incumbents.'),
        ('Mustafizur Rahman', 'bowling', 'Left-arm death-bowling alternative. Stronger combined output than IPL-only output warrants a role-specific review.'),
        ('Jaydev Unadkat', 'bowling', 'Domestic left-arm pace cover. Compare across phases where RR needs a backup.'),
        ('Akash Madhwal', 'bowling', 'Domestic seam option to scout for death-overs cover. Review his recent IPL execution in that phase.'),
        ('Mayank Markande', 'bowling', 'Domestic middle-overs spin depth if RR needs cover for Bishnoi.'),

    ]
    header = ['Player / status','Combined / IPL output and IPL sample','RR role and next check']
    rows = [header]
    auction_picks = []
    for name,role,action in sorted(watch, key=lambda pick: pick[1]):
        if role == 'bowling' and len(auction_picks) == 10:
            story.extend([para('Top 10 batting targets', 'SubRR'), table(rows, [145,140,220]), PageBreak()])
            rows = [header]
        key='batters_all' if role=='batting' else 'bowlers_all'
        p=next(x for x in data[key] if x['name']==name)
        ip=next((x for x in decision['roles'][role]['ipl_only'] if x['id']==p['id']),None)
        status=classify_candidate(name,auction)
        label='Official release; registration unverified' if status['status']=='released_registration_unverified' else 'Reported release; registration unverified'
        val=fmt(p['pressure_score'])+' / '+(fmt(ip['pressure_score']) if ip else 'No supported IPL sample')
        player_column = 'striker_id' if role == 'batting' else 'bowler_id'
        sample = ipl_pressure[ipl_pressure[player_column].eq(p['id'])]
        if role == 'batting':
            sample = sample[sample.extra.ne('wide')]
        by_match = sample.groupby('match_id')[role+'_residual'].sum()
        if len(by_match):
            val += f"\n{len(sample)} IPL balls in {len(by_match)} matches"
            val += f"\n{(by_match > 0).sum()}/{len(by_match)} above expectation"
        if ip:val+=f"\nIPL range [{fmt(ip['pressure_interval'][0])}, {fmt(ip['pressure_interval'][1])}]"
        rows.append([name+'\n'+label,val,action])
        auction_picks.append(dict(name=name, role=role, assignments=p['roles'], rationale=action,
            status=label, ipl_output=ip['pressure_score'] if ip else None,
            ipl_range=ip['pressure_interval'] if ip else None, deliveries=len(sample),
            matches=len(by_match), positive_matches=int((by_match > 0).sum())))
    story.extend([para('Top 10 bowling targets', 'SubRR'), table(rows,[145,140,220])])
    story += [PageBreak(),
        para('A scouting route for uncapped players and debutants', 'SubRR'),
        para('In the previous SupeRR Selector, the winners backed Ravi Bishnoi and Vignesh Puthur. RR bought both at the IPL 2026 auction. Puthur was uncapped and already had five IPL appearances. Our data contains 13 pressure deliveries for him, below the 30 needed for a rating. This is exactly the kind of player a role-based scouting review can surface.', 'SmallRR'),
        para('For each squad need, compare an established IPL option with an emerging player when reliable evidence is available. Use IPL pressure evidence for the established option and verified domestic scorecards and video for emerging players. Keep the challenge pressure rating blank when the IPL and T20I sample is insufficient. Confirm auction entry and assess role fit before recommending a bid.', 'SmallRR'),
        Paragraph('<link href="https://unstop.com/hackathons/superr-selector-season-2-help-shape-rajasthan-royals-ipl-2027-auction-strategy-rajasthan-royals-1792758">Unstop case recap</link> | <link href="https://www.iplt20.com/teams/GL/squad-details/22266">IPL player profile</link>', styles['SmallRR']),
    ]
    verified=verified_recruitment_pool(data['batters_all']+data['bowlers_all'],auction)
    story += [para(f"Availability checks cover releases across all ten franchises, using official announcements where obtained and clearly marked reporting elsewhere. At this cutoff, {len(verified)} players in the rated pool have verified auction entry and availability in our evidence file. Released does not mean registered, medically ready or board-cleared. Retained, unavailable, conflicting or unknown cases cannot pass the confirmed-acquisition filter.", 'SmallRR')]

    story += [
        PageBreak(),
        para('Appendix: the terms in this report', 'SectionRR'),
        para('Understanding the scores', 'SubRR'),
        table([
            ['Term', 'Plain-language meaning'],
            ['Expected runs', 'Runs the historical model estimates for a delivery in that match situation.'],
            ['Contextual residual', 'Actual minus expected batter runs. For bowling, expected minus actual charged runs. Positive means better run output or run prevention than the model expected.'],
            ['Usual baseline / 100', 'The player’s average contextual contribution outside the selected pressure situations, multiplied by 100. Calculated separately for IPL and T20I, then weighted to the player’s pressure mix.'],
            ['Pressure performance / 100', 'Mean contribution against model expectation, multiplied by 100 x N/(N+60). IPL and T20I deliveries have equal weight; N is the actual pressure-delivery count.'],
            ['Improvement / 100', 'Pressure contribution after subtracting the player’s ordinary contextual baseline and applying the same sample adjustment. This is the improvement diagnostic, rather than the RR selection order.'],
            ['Wicket contribution', '100 x (credited wickets - expected credited wickets) / (N+60). Expected wickets come from logistic regression on the same pre-delivery features, trained on earlier seasons. Its whole-match bootstrap lower bound is used in bowling tiers.'],
            ['Bowling selection tier', 'Players are grouped by run-control and wicket-taking lower confidence bounds. A player is dominated if another is at least as strong on both and stronger on one. Remove that first group and repeat. Within each tier, sort by the run-control lower bound.'],
            ['Per 100 deliveries', 'A common scale for comparison, not a claim that the player faced exactly 100 balls. For bowling, wides remain charged delivery events; batting exposure excludes wides.'],
            ['Shrinkage / +60 adjustment', 'A fixed adjustment that pulls estimates from small samples toward zero. At 30 pressure deliveries, one third of the raw estimate remains. The fixed constant is a policy choice; the 30/120 audit shows its effect on selection.'],
        ], [130, 375], compact=True),
        Spacer(1, 8),
        para('Evidence, reliability and scope', 'SubRR'),
        table([
            ['Term', 'How to interpret it'],
            ['Pressure match / sample', 'A match containing qualifying pressure deliveries for that player. Multiple balls in one match are related observations; 30 balls from five matches are not 30 independent experiments.'],
            ['95% score range', 'An interval from repeatedly resampling whole matches and recalculating the score and ordinary baseline. A range containing zero leaves the direction of that contribution uncertain.'],
            ['Match-cluster bootstrap', 'Resample complete player-match clusters rather than isolated deliveries. Published intervals condition on frozen contextual models and do not include contextual-model fitting uncertainty. The published run uses 400 draws; seed and 2,000-draw checks are reported separately.'],
            ['Single-match removal', 'Remove each pressure match in turn, including its ordinary deliveries, and recalculate. Report the lowest resulting score. Any peer rank holds other player scores fixed.'],
            ['Out-of-time evaluation', 'Fit a model on earlier seasons and evaluate it on a later season. The 2022 warm-up trains the first evaluation year.'],
            ['Role sample', 'Observed batting position or bowling phase exposure. Insufficient role sample means the tagging threshold was not met; it does not mean the player has no role or ability.'],
            ['Wickets / dismissals', 'Credited bowling wickets enter selection tiers through their contribution above contextual expectation. Striker dismissals are shown for batting. No fixed runs-per-wicket conversion is used.'],
        ], [130, 375], compact=True),
        Spacer(1, 6),
        para('Pressure output compares with the contextual model; improvement additionally compares with the player’s usual level.', 'SmallRR'),
        para('Scope and limits', 'SubRR'),
        para('These are retrospective estimates on the retained sample. Venue and opposition strength are not fully controlled. Match-bootstrap intervals condition on fitted contextual models. Cross-format transfer and future IPL prediction are unproven; release status alone does not confirm auction availability.', 'SmallRR'),
    ]

    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(LINE); canvas.line(45, 35, A4[0]-45, 35)
        canvas.setFillColor(MUTED); canvas.setFont('Helvetica', 7.2)
        canvas.drawRightString(A4[0]-45, 23, f"{doc.page}")
        canvas.restoreState()

    output = ROOT / 'results/public/methodology.pdf'
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=45, leftMargin=45, topMargin=40, bottomMargin=46, title='SupeRR Selector Round 1 - Methodology and Evidence', author="Royals' Resolve").build(story, onFirstPage=footer, onLaterPages=footer)
    shutil.copy2(output, ROOT / 'results/public/Royals_Resolve_methodology.pdf')
    front = ROOT / 'frontend/public/results'; front.mkdir(parents=True, exist_ok=True)
    for name in ['analysis.json', 'methodology.pdf']:
        shutil.copy2(ROOT / 'results/public' / name, front / name)
    strategy_output = output.parent/'auction-strategy.json'
    strategy_output.write_text(json.dumps(dict(
        analysis_id=data['analysis_id'], as_of=auction['as_of'], squad=auction['rr'], picks=auction_picks
    ), indent=2), encoding='utf-8')
    shutil.copy2(strategy_output, front/strategy_output.name)
    print(output)


if __name__ == '__main__':
    main()
