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
        self.assertEqual(a['retained_deliveries']+a['excluded_deliveries'],a['deliveries'])
        self.assertEqual(a['retained_matches']+a['excluded_matches'],a['matches'])
        for label in ['batters','bowlers']:
            picks=d[label];self.assertEqual(len(picks),10);self.assertEqual(len({p['id'] for p in picks}),10)
            self.assertEqual([p['rank'] for p in picks],list(range(1,11)))
            self.assertEqual([p['score'] for p in picks],sorted([p['score'] for p in picks],reverse=True))
            for p in picks:
                self.assertGreaterEqual(p['matches'],5);self.assertGreaterEqual(p['balls'],30)
                self.assertAlmostEqual(100*p['residual_sum']/(p['balls']+60),p['score'],places=3)
                observed=p['runs']-p['expected_runs'] if label=='batters' else p['expected_runs']-p['runs']
                self.assertAlmostEqual(observed,p['residual_sum'],places=3)
                self.assertEqual(p['rr_case'].keys(),dict.fromkeys(['capability_demonstrated','current_verified_rr_coverage','measured_gap_or_uncertainty','primary_alternative','biggest_risk','actionability']).keys())
    def test_chronology_and_no_pack_in_public(self):
        d=pd.read_parquet(ROOT/'artifacts/private/evaluated.parquet')
        self.assertTrue((d.year>=2023).all());self.assertFalse(d.duplicated(['match_id','innings','innings_ball_num']).any())
        for mid,g in d.groupby('match_id'):self.assertEqual(g.year.nunique(),1)
        public=ROOT/'results/public';self.assertEqual({p.name for p in public.iterdir()},{'analysis.json','methodology.pdf'})
    def test_pdf_agreement(self):
        from pypdf import PdfReader
        d=json.loads((ROOT/'results/public/analysis.json').read_text());pages=[p.extract_text() for p in PdfReader(ROOT/'results/public/methodology.pdf').pages]
        self.assertIn(d['analysis_id'],pages[0])
        for i,label in [(2,'batters'),(3,'bowlers')]:
            text=pages[i];positions=[text.index(p['name']) for p in d[label]];self.assertEqual(positions,sorted(positions))

if __name__=='__main__':unittest.main()
