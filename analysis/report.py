"""Generate report and matching Markdown from publication-safe analysis only."""
import json, shutil
from pathlib import Path
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parents[1]
NAVY=colors.HexColor('#14204B');PINK=colors.HexColor('#EA1A85')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleRR',fontName='Helvetica-Bold',fontSize=32,leading=38,textColor=NAVY,spaceAfter=20))
styles.add(ParagraphStyle(name='SmallRR',fontSize=8,leading=12,textColor=NAVY,spaceAfter=6))
styles['BodyText'].leading=15;styles['BodyText'].spaceAfter=9;styles['BodyText'].textColor=NAVY
styles['Heading1'].textColor=NAVY;styles['Heading2'].textColor=PINK

def p(text,style='BodyText'):
    # Base PDF fonts do not encode typographic punctuation consistently.
    text=str(text).replace('\u2019',"'").replace('\u2013','-').replace('\u2014','-').replace('\u2265','>=').replace('\u2264','<=').replace('\u2212','-')
    return Paragraph(escape(text),styles[style])
def table(rows,widths=None):
    t=Table([[p(c,'SmallRR') for c in r] for r in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#F5EFF7')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,PINK),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#DDDFE8')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    return t

def support_lines(key,value):
    if value is None:return [key.replace('_',' ')+': insufficient evidence']
    if key=='entry_readiness':
        return [f"First-six readiness / {r['entry_phase']} / {'collapse' if r['collapse_entry'] else 'stable'}: {r['innings']} innings, {r['legal_balls']} legal balls; {r['runs_per_100_legal']} bat runs/100 legal balls; dismissal probability {r['dismissal_probability_per_innings']} per innings." for r in value] or ['First-six readiness: insufficient evidence']
    if key=='recovery_assignments':
        return [f"Entry assignment / {r['entry_phase']} / {'collapse' if r['collapse_entry'] else 'stable'}: {r['events']} events in {r['matches']} matches, {r['contextual_runs_per_100']:+.2f} contextual runs/100 events." for r in value] or ['Recovery assignment: insufficient evidence']
    if key=='scoring_without_boundaries':
        return [f"Non-boundary scoring: {value['nonboundary_runs_per_100_legal']} bat runs/100 legal balls; {value['nonboundary_scoring_percent']}% scoring events excluding boundaries; boundary share {value['boundary_share_bat_runs_percent']}% of legal-ball bat runs. {value['legal_balls']} legal balls in {value['innings']} innings."]
    if key=='downside':
        return [f"Match downside: lower quartile {value['lower_quartile']}, median {value['median']} unpooled runs/100 events; {value['unfavourable_matches']} unfavourable of {value['matches']} pressure matches. Mean interval {value['mean_interval']}; performance variability and mean uncertainty are distinct."]
    if key=='costly_delivery_exposure':
        return [f"Costly exposure: {value['verified_wides']} verified wides in {value['events']} events ({value['wides_per_100_events']}/100); {value['boundaries_per_100_legal']} boundaries/100 legal balls; wides cost {value['wide_run_cost']} charged runs. No-ball rate is not estimated because ambiguous records were quarantined."]
    if key=='boundary_damage_control':
        return [f"Observed same-over boundary follow-up: {value['events']} events / {value['legal_balls']} legal balls / {value['matches']} matches; boundary frequency {value['boundary_percent']}% versus {value['expected_boundary_percent']}% expected; {value['runs_conceded']} runs conceded, {value['runs_prevented']:+.2f} contextual runs prevented. Follow-ups are selected opportunities, not causal evidence of recovery."]
    raise ValueError('Unrecognised supporting metric')

def main():
    d=json.loads((ROOT/'results/public/analysis.json').read_text());a=d['audit'];story=[]
    text=(ROOT/'docs/methodology.md').read_text(encoding='utf-8')
    story += [p('ROYALS / RESOLVE','SmallRR'),Spacer(1,40),p('Find the nerve.\nBack the talent.','TitleRR'),p('Royals\u2019 Resolve - independent competition entry'),p('Methodology, evidence dossiers and conditional auction decision memo','Heading2'),p(d['status']),p('Analysis '+d['analysis_id']+' | Version '+d['version']+' | Generated '+d['generated'][:10]),Spacer(1,25),p(f"Real input audit: {a['deliveries']:,} deliveries / {a['matches']} matches. Retained {a['retained_deliveries']:,} deliveries / {a['retained_matches']} matches. Excluded {a['excluded_innings']} observed innings."),p('Source: supplied SupeRR Selector competition pack. Upstream provider is not established by the files. Raw records remain private.'),PageBreak()]
    story += [p('Auction decision memo','Heading1'),p(d['roster']['decision_memo']),p('Research priorities','Heading2'),p('1. Resolve source extras definitions before broadening coverage. 2. Validate role- and venue-matched transfer to IPL. 3. Confirm 2027 retention and registration before turning a statistical finding into a target.'),p('TARGET: none verified. CONDITIONAL WATCH: the statistical selections below. NOT CURRENTLY ACTIONABLE: no 2027 retained/unavailable designation is asserted without an official source.'),p('Current coverage is based on the official page labelled 2026, accessed 2026-11-12. It is not treated as a 2027 contract list. No prices, purse, overseas-slot assumptions or budget optimum are invented.'),p('Strict-margin coverage result','Heading2'),p(f"The proposed margin rule yields {d['margin_eligible_counts']['batting']} eligible batter(s) and {d['margin_eligible_counts']['bowling']} bowlers. It fails the two-top-ten coverage requirement. The current run therefore uses the explicit phase/required-rate fallback for both lists. This is a coverage decision, not evidence that the fallback predicts better."),p('Baseline and caveat','Heading2'),p('Chase pressure: 60 or fewer legal balls remaining and required rate at least 8 runs/over. First innings: 30 or fewer legal balls remaining and at least 3 wickets lost. Rank pooled contextual run contribution, not raw strike rate or economy. Wicket value is not yet validated, so rankings are provisional run-only evidence.'),PageBreak()]
    for label in ['batters','bowlers']:
        story += [p('Ordered top ten '+label,'Heading1'),p(f"{d[label+'_eligible_count']} eligible players. Minimum: 30 pressure events in five independent matches. Score units: residual runs per 100 delivery events, shrunk by 60 pseudo-events. Close intervals are not evidence of a precise ability ordering."),table([['Rank / player','Contribution','95% interval','Matches / episodes / events']]+[[f"{x['rank']}. {x['name']}",f"{x['score']:+.2f}",f"{x['interval'][0]:+.1f} to {x['interval'][1]:+.1f}",f"{x['matches']} / {x['episodes']} / {x['balls']}"] for x in d[label]],[190,70,100,145]),PageBreak()]
    story += [p('Measurement and reproduction','Heading1')]
    for line in text.splitlines():
        if not line.strip():continue
        if line.startswith('# '):story.append(p(line[2:],'Heading1'))
        elif line.startswith('## '):story.append(p(line[3:],'Heading2'))
        else:story.append(p(line))
    story += [PageBreak(),p('Audit and exclusions','Heading1'),table([['Disposition','Observed count']]+[[k,str(a[k])] for k in ['deliveries','matches','retained_matches','retained_innings','retained_deliveries','excluded_matches','excluded_innings','excluded_deliveries','oos_matches','oos_deliveries','warmup_deliveries']],[330,175]),p('Reasons overlap; their counts are not additive.'),table([['Reason','Matches']]+[[k,str(v)] for k,v in a['exclusion_reasons_overlapping'].items()],[420,85]),PageBreak(),p('Chronological reference-model validation','Heading1')]
    story.append(table([['Year','Train / test matches','Model','Brier','Log loss']]+[[str(v['year']),f"{v['train_matches']} / {v['test_matches']}",name,f"{s['brier']:.4f}",f"{s['log_loss']:.4f}"] for v in d['validation'] for name,s in v['models'].items()],[45,95,165,85,115]))
    story.append(p('Earlier-data first-innings benchmarks: '+ '; '.join(f"{v['year']}: {v['benchmark']} runs" for v in d['validation'])))
    story.append(p('Calibration bins (linear logistic): each interval is [lower, lower+0.2); predicted versus observed task-success frequency. These describe model calibration, not psychological-pressure accuracy.'))
    story.append(table([['Year / bin','Events','Predicted','Observed']]+[[f"{v['year']} / {s['low']:.1f}",str(s['rows']),str(round(s['predicted'],3)) if s['predicted'] is not None else '-',str(round(s['observed'],3)) if s['observed'] is not None else '-'] for v in d['validation'] for s in v['models']['logistic']['calibration']],[130,90,140,145]))
    for label in ['batters','bowlers']:
        story += [PageBreak(),p('Later-match selection check: '+label,'Heading1'),p('Retrospective diagnostic; eligibility and future participation are shown. Ordinary batting uses bat runs/event; ordinary bowling uses charged runs/legal ball. The phase/rate policy equals contextual policy under the fallback; it is not an independent win.'),table([['Year / policy','Observed / selected','Later events','Later runs / 100']]+[[str(v['year'])+' / '+v['policy'],f"{v['observed_later']} / {v['selected']}",str(v['future_events']),str(v['future_contribution'])] for v in d[label+'_selection_validation']],[210,95,80,120])]
        for x in d[label]:
            story += [PageBreak(),p(f"{label.upper()} / {x['rank']:02d}",'SmallRR'),p(x['name'],'TitleRR'),p(', '.join(x['roles']) or 'Insufficient role evidence','Heading2'),p('Score audit','Heading2'),p(f"{x['balls']} pressure events / {x['legal_balls']} legal balls -> {x['episodes']} episodes -> {x['matches']} matches. Expected runs {x['expected_runs']:.4f}; observed runs {x['runs']:.0f}; signed residual sum {x['residual_sum']:+.4f}. Score = 100 x {x['residual_sum']:.4f} / ({x['balls']} + 60) = {x['score']:+.4f}. 95% match-bootstrap interval {x['interval']}.")]
            story += [p('Six evidence dimensions','Heading2'),p(f"Contribution {x['score']:+.2f} runs/100. Nonpressure usual {x['usual']:+.2f} over {x['nonpressure_balls']} events; all-situation usual {x['overall_usual']:+.2f}. Unpooled pressure-minus-nonpressure {x['difference']:+.2f}. Repeatability: {x['matches']} matches / {x['episodes']} episodes. Between-match SD {x['between_match_sd']:.2f}. Coverage: {x['ipl_balls']} IPL events; first innings {x['first_innings_balls']}, chase {x['chase_balls']}.")]
            if x['phases']:story.append(table([['Phase','Events / matches','Runs / 100','Pressure events']]+[[r['role'],f"{r['balls']} / {r['matches']}",str(r['contribution']),str(r['pressure_balls'])] for r in x['phases']],[170,100,120,115]))
            story += [p('Potential RR contribution - six-part case','Heading2')]
            for k,v in x['rr_case'].items():story.append(p(k.replace('_',' ').capitalize()+': '+v))
            story += [p('Supporting coach evidence','Heading2')]
            for k,v in x['supporting'].items():
                for line in support_lines(k,v):story.append(p(line,'SmallRR'))
            if x['matchups']:
                story.append(p('Supported descriptive pressure splits','Heading2'))
                story.append(table([['Context','Events / matches','Runs per 100 / interval']]+[[z['dimension']+' / '+z['value'],f"{z['events']} / {z['matches']}",str(z['runs_per_100'])+' / '+str(z['interval'])] for z in x['matchups']],[195,100,210]))
            story += [p('Fixed-fit verdict checks','Heading2')]
            for k,v in x['scenarios'].items():story.append(p(k+': '+(str(v) if v is not None else 'insufficient pressure coverage'),'SmallRR'))
    story += [PageBreak(),p('RR coverage matrix','Heading1'),p('Phase evidence requires 60 events across five matches. Missing is not zero quality; source-name aliases are not guessed.')]
    for x in d['coverage']:
        story.append(p(x['name']+': batting '+(', '.join(f"{z['phase']} {z['score']:+.1f} ({z['balls']} events / {z['matches']} matches)" for z in x['batting']) or 'not assessed')+'; bowling '+(', '.join(f"{z['phase']} {z['score']:+.1f} ({z['balls']} events / {z['matches']} matches)" for z in x['bowling']) or 'not assessed'),'SmallRR'))
    story += [p('Sources and limitations','Heading1')]
    for s in d['roster']['sources']:story.append(p(s['publisher']+' | '+s['url']+' | accessed '+s['accessed']+' | '+s['claim']))
    for s in d['limitations']:story.append(p(s))
    story += [p('Provenance','Heading2'),p('Analysis ID '+d['analysis_id']),p(json.dumps(d['provenance']),'SmallRR')]
    def footer(c,doc):
        c.setFillColor(NAVY);c.setFont('Helvetica',8);c.drawString(45,25,'Royals Resolve | '+d['analysis_id']);c.drawRightString(A4[0]-45,25,str(doc.page))
    path=ROOT/'results/public/methodology.pdf'
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=45,bottomMargin=45,title='Royals Resolve - Methodology '+d['analysis_id'],author='Royals Resolve').build(story,onFirstPage=footer,onLaterPages=footer)
    target=ROOT/'frontend/public/results';target.mkdir(parents=True,exist_ok=True)
    for name in ['analysis.json','methodology.pdf']:shutil.copy2(ROOT/'results/public'/name,target/name)
    print(path)

if __name__=='__main__':main()
