import json, sys, tempfile, unittest, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis'))
from audit import read_pack
from pipeline import before,episodes,tolerance,probability,reconstruct

class Reference:
    def predict_proba(self,x):
        # Controlled synthetic probability decreases when fewer balls remain.
        p=np.clip(x[:,2]/10,0,1)
        return np.column_stack([1-p,p])

class Contract(unittest.TestCase):
    def test_batter_exposure_excludes_wides(self):
        from supporting import role_rows
        d=pd.DataFrame({"extra":["None","wide","legbyes"],"runs":[4,0,0]})
        self.assertEqual(role_rows(d,"batting").index.tolist(),[0,2])
        self.assertEqual(role_rows(d,"bowling").index.tolist(),[0,1,2])

    def state(self):
        return pd.DataFrame({'match_id':[1],'innings':[2],'score':[10],'lost':[2],'remaining':[4],'need':[8],'used':[116]})
    def test_pre_delivery(self):
        d=pd.DataFrame({'match_id':[1]*3,'innings':[1]*3,'runs':[4,1,6]})
        self.assertEqual(before(d,'runs').tolist(),[0,4,5])
    def test_margin_path_and_below_viability(self):
        d=self.state();m,q=tolerance(Reference(),d,100,'batting',.2)
        self.assertEqual(m.tolist(),[2]);self.assertAlmostEqual(q[0],.4)
        d['remaining']=1;m,_=tolerance(Reference(),d,100,'batting',.2);self.assertEqual(m.tolist(),[-1])
    def test_terminal_target_and_wickets(self):
        d=self.state();d['need']=0
        self.assertEqual(probability(Reference(),d,100)[0],1)
        d['need']=8;d['lost']=10
        self.assertEqual(probability(Reference(),d,100)[0],0)
    def test_horizon_cap(self):
        d=self.state();d['remaining']=40
        self.assertEqual(tolerance(Reference(),d,100,'batting',.2)[0].tolist(),[6])
    def test_episode_contiguity(self):
        d=pd.DataFrame({'match_id':[1]*5,'innings':[1]*5});mask=pd.Series([True,True,False,True,True])
        ids=episodes(d,mask);self.assertEqual(ids.iloc[0],ids.iloc[1]);self.assertNotEqual(ids.iloc[1],ids.iloc[3])
    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('../leak.csv','secret')
            with self.assertRaises(ValueError):read_pack(z)
    def test_nested_zip_traversal_rejected(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            memory=io.BytesIO()
            with zipfile.ZipFile(memory,'w') as f:f.writestr('../leak.csv','secret')
            z=Path(tmp)/'outer.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('nested.zip',memory.getvalue())
            with self.assertRaises(ValueError):read_pack(z)
    def test_legal_balls_extras_and_runout(self):
        rows=[]
        for i in range(120):
            rows.append({'match_id':1,'innings':1,'innings_ball_num':i+2,'overid':i//6+1,'extras_type':None,'runs':0,'extras1_runs':0,'extras_2_runs':0,'is_wicket':i==0,'dismissal_type':'RunOut' if i==0 else None,'batting_team_id':1,'bowling_team_id':2})
        rows[1].update(extras_type='byes',extras1_runs=1)
        rows.insert(0,{**rows[2],'innings_ball_num':1,'extras_type':'wide','extras1_runs':1})
        rows.append({**rows[2],'innings':2,'innings_ball_num':1,'overid':1,'runs':3,'extras_type':None,'extras1_runs':0,'is_wicket':False,'dismissal_type':None,'batting_team_id':2,'bowling_team_id':1})
        m=pd.DataFrame([{'match_id':1,'comp_id':1,'match_date':'2024-01-01','venue_id':1,'win_team_id':2,'first_inn_revised_overs':np.nan,'second_inn_revised_overs':np.nan,'revised_target':np.nan,'result':'Won by wickets'}])
        b,_,reasons=reconstruct(pd.DataFrame(rows),m)
        self.assertFalse(reasons);self.assertEqual(b[b.innings==1].legal.sum(),120)
        self.assertEqual(b.iloc[0].used,0);self.assertEqual(b.iloc[1].used,0)
        self.assertFalse(b.iloc[1].credit_wicket);self.assertEqual(b.iloc[2].bowler_runs,0)
        self.assertEqual(b.iloc[-1].target,3)
    def test_real_export_reconciliation(self):
        d=json.loads((ROOT/'results/public/analysis.json').read_text());a=d['audit']
        self.assertEqual(a['retained_deliveries']+a['excluded_deliveries'],a['scope_deliveries'])
        self.assertEqual(a['retained_matches']+a['excluded_matches'],a['scope_matches'])
        self.assertEqual(a['scope_deliveries']+a['out_of_scope_deliveries'],a['deliveries'])
        self.assertEqual(a['scope_matches']+a['out_of_scope_matches'],a['matches'])
        evaluated=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
        for label,role in [('batters','batting'),('bowlers','bowling')]:
            picks=d[label];self.assertEqual(len(picks),10);self.assertEqual(len({p['id'] for p in picks}),10)
            self.assertEqual(len({p['name'].casefold().strip() for p in picks}),10)
            self.assertEqual([p['rank'] for p in picks],list(range(1,11)))
            self.assertEqual([p['selection_tier'] for p in picks],sorted([p['selection_tier'] for p in picks]))
            for tier in {p['selection_tier'] for p in picks}:
                lower=[p['pressure_interval'][0] for p in picks if p['selection_tier']==tier]
                self.assertEqual(lower,sorted(lower,reverse=True))
            for p in picks:
                self.assertGreaterEqual(p['matches'],5);self.assertGreaterEqual(p['balls'],30)
                self.assertGreaterEqual(p['nonpressure_balls'],60);self.assertGreaterEqual(p['usual_matches'],5)
                self.assertAlmostEqual(100*p['weighted_residual_sum']/(p['balls']+60),p['pressure_score'],places=3)
                self.assertAlmostEqual(100*p['uplift_sum']/(p['balls']+60),p['score'],places=3)
                self.assertEqual(p['balls'],p['ipl_balls']+p['t20i_balls'])
                player_col='striker_id' if role=='batting' else 'bowler_id';key=f'{role}_0.2'
                player_rows=evaluated[evaluated[player_col]==p['id']]
                if role=='batting':player_rows=player_rows[player_rows.extra.ne('wide')]
                pressure_rows=player_rows[player_rows[key]]
                self.assertEqual(len(pressure_rows),p['balls'])
                format_uplift=0.0;weight_total=0.0
                for is_ipl in pressure_rows.is_ipl.unique():
                    pressure_format=pressure_rows[pressure_rows.is_ipl==is_ipl]
                    usual_format=player_rows[(~player_rows[key])&(player_rows.is_ipl==is_ipl)]
                    self.assertGreaterEqual(len(usual_format),30);self.assertGreaterEqual(usual_format.match_id.nunique(),3)
                    w=p['ipl_evidence_weight'] if is_ipl else 1.0
                    weight_total+=w*len(pressure_format)
                    format_uplift += w*(pressure_format[role+'_residual'].sum()-len(pressure_format)*usual_format[role+'_residual'].mean())
                self.assertAlmostEqual(format_uplift*p['balls']/weight_total,p['uplift_sum'],places=3)
                observed=p['runs']-p['expected_runs'] if label=='batters' else p['expected_runs']-p['runs']
                self.assertAlmostEqual(observed,p['residual_sum'],places=3)
                self.assertEqual(p['rr_case'].keys(),dict.fromkeys(['capability_demonstrated','current_verified_rr_coverage','measured_gap_or_uncertainty','primary_alternative','biggest_risk','actionability']).keys())
    def test_chronology_and_no_pack_in_public(self):
        d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
        self.assertTrue((d.is_ipl | d.is_t20i).all())
        self.assertTrue((d.year>=2023).all());self.assertFalse(d.duplicated(['match_id','innings','innings_ball_num']).any())
        for mid,g in d.groupby('match_id'):self.assertEqual(g.year.nunique(),1)
        public=ROOT/'results/public';self.assertTrue({'analysis.json','methodology.pdf'} <= {p.name for p in public.iterdir()} <= {'analysis.json','methodology.pdf','Royals_Resolve_methodology.pdf','auction-strategy.json'})
    def test_pdf_agreement(self):
        from pypdf import PdfReader
        d=json.loads((ROOT/'results/public/analysis.json').read_text());pages=[p.extract_text() for p in PdfReader(ROOT/'results/public/methodology.pdf').pages]
        # Submission copy deliberately omits internal run identifiers.
        self.assertNotIn(d['analysis_id'],pages[0])
        for i,label in [(2,'batters'),(3,'bowlers')]:
            text=pages[i];positions=[text.index(p['name']) for p in d[label]];self.assertEqual(positions,sorted(positions))

    def test_decision_audit_matches_published_objective(self):
        d=json.loads((ROOT/'results/public/analysis.json').read_text())
        audit=json.loads((ROOT/'artifacts/private/decision-audit.json').read_text())
        self.assertEqual(d['analysis_id'],audit['analysis_id'])
        for role,key in [('batting','batters'),('bowling','bowlers')]:
            self.assertEqual([p['id'] for p in d[key+'_all']],[p['id'] for p in audit['roles'][role]['primary']])
            for p in audit['roles'][role]['ipl_only']:
                self.assertEqual(p['t20i_balls'],0)
                self.assertEqual(p['balls'],p['ipl_balls'])
            self.assertEqual(len(audit['roles'][role]['stability']),10)

    def test_recruitment_filter_requires_verified_entry_and_availability(self):
        from recruitment import classify_candidate,verified_recruitment_pool
        e={'players':[{'name':'Retained','status':'retained_elsewhere'}],'confirmed_auction_entries':[]}
        self.assertFalse(classify_candidate('Unknown',e)['auction_actionable'])
        e['confirmed_auction_entries']=[{'name':'Unknown','registration_confirmed':True,'availability_confirmed':False,'source':'synthetic official source'}]
        self.assertFalse(classify_candidate('Unknown',e)['auction_actionable'])
        e['confirmed_auction_entries'][0]['availability_confirmed']=True
        self.assertTrue(classify_candidate('Unknown',e)['auction_actionable'])
        e['confirmed_auction_entries'].append({'name':'Retained','registration_confirmed':True,'availability_confirmed':True,'source':'synthetic official source'})
        self.assertFalse(classify_candidate('Retained',e)['auction_actionable'])
        self.assertEqual(verified_recruitment_pool([{'name':'Unknown'},{'name':'Retained'}],e),[{'name':'Unknown'}])

    def test_report_exposes_bowling_sort_inputs(self):
        from pypdf import PdfReader
        d=json.loads((ROOT/'results/public/analysis.json').read_text())
        pages=[p.extract_text() for p in PdfReader(ROOT/'results/public/methodology.pdf').pages]
        for p in d['bowlers']:
            self.assertIn(f"{p['wicket_interval'][0]:+.4f}",pages[3])
            self.assertIn(f"{p['pressure_interval'][0]:+.4f}",pages[3])
        self.assertIn('Future IPL performance is not demonstrated',pages[0])
        self.assertIn('Matheesha Pathirana has the most pressure deliveries',pages[3])
        self.assertIn('Pressure output compares with the contextual model',' '.join(pages))

    def test_reconciled_no_ball_accounting(self):
        # Two legitimate no-ball codes, including four byes off one no-ball.
        rows=[]
        for i in range(120):
            rows.append({'match_id':1,'innings':1,'innings_ball_num':i+3,'overid':i//6+1,'extras_type':None,'runs':0,'extras1_runs':0,'extras_2_runs':0,'is_wicket':False,'dismissal_type':None,'batting_team_id':1,'bowling_team_id':2})
        rows.insert(0,{**rows[0],'innings_ball_num':1,'extras_type':'Overstep','runs':2,'extras1_runs':1})
        rows.insert(1,{**rows[1],'innings_ball_num':2,'extras_type':'other','extras1_runs':1,'extras_2_runs':4})
        rows.append({**rows[-1],'innings':2,'innings_ball_num':1,'overid':1,'runs':9,'batting_team_id':2,'bowling_team_id':1})
        m=pd.DataFrame([{'match_id':1,'comp_id':1,'match_date':'2024-01-01','venue_id':1,'win_team_id':2,'first_inn_revised_overs':np.nan,'second_inn_revised_overs':np.nan,'revised_target':np.nan,'result':'Won by 10 wickets'}])
        d,_,reasons=reconstruct(pd.DataFrame(rows),m)
        self.assertFalse(reasons)
        self.assertEqual(d.iloc[0].bowler_runs,3)
        self.assertEqual(d.iloc[1].bowler_runs,1)
        self.assertEqual(d.iloc[1].total,5)
        self.assertEqual(d.iloc[2].used,0)
        self.assertEqual(d.iloc[-1].target,9)
        broken=pd.DataFrame(rows);broken.loc[0,'extras1_runs']=2
        _,_,reasons=reconstruct(broken,m)
        self.assertIn('no-ball signature or dismissal inconsistent',reasons[1])

    def test_source_no_ball_over_reconciliation(self):
        review=json.loads((ROOT/'artifacts/private/extras-recovery-review.json').read_text())
        for code in ['Overstep','other']:
            r=review['no_ball_codes'][code]
            self.assertEqual(r['events'],r['one_run_penalty'])
            self.assertEqual(r['complete_overs'],r['complete_overs_with_six_legal'])
            self.assertEqual(r['incompatible_dismissals'],0)

    def test_coach_selection_is_not_improvement_order(self):
        from selection_policy import order_candidates
        def p(pid,quality,lift,wick=0):
            return dict(id=pid,rank=pid,score=lift,pressure_interval=[quality,quality+20],pressure_score=quality+10,wicket_interval=[wick,wick+1],matches=12,ipl_pressure_matches=5,ipl_balls=60,ipl_usual_matches=5,ipl_usual_balls=100,roles=['Death'])
        a=p(1,5,100);b=p(2,10,1)
        self.assertEqual([x['id'] for x in order_candidates([a,b],'batting')],[2,1])
        # Wicket evidence changes Pareto membership without inventing a run value.
        a=p(1,10,1,0);b=p(2,9,100,-1);c=p(3,8,2,1)
        ranked=order_candidates([a,b,c],'bowling')
        self.assertEqual([x['id'] for x in ranked],[1,3,2])
        c['ipl_pressure_matches']=0
        self.assertIn(3,[x['id'] for x in order_candidates([a,c],'batting')])

    def test_source_weight_does_not_invent_exposure(self):
        from pipeline import summarize
        d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
        # Within one format a constant evidence weight must cancel completely.
        pid=int(d.loc[d.striker_name.eq('Shashank Singh'),'striker_id'].iloc[0])
        g=d[d.striker_id==pid]
        self.assertTrue(g.is_ipl.all())
        a=summarize(g,'batting',ipl_weight=1.0)[0]
        b=summarize(g,'batting',ipl_weight=2.0)[0]
        self.assertEqual(a['balls'],b['balls'])
        self.assertAlmostEqual(a['pressure_score'],b['pressure_score'],places=8)
        self.assertEqual(a['pressure_interval'],b['pressure_interval'])

if __name__=='__main__':unittest.main()
