import sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leverage_challenger_v2 import advance,wp,leverage
class ConstantModel:
    def predict_proba(self,x):return np.tile([.6,.4],(len(x),1))
class LeverageContracts(unittest.TestCase):
    def state(self,innings=2):return pd.DataFrame(dict(innings=[innings],score=[150],lost=[9],remaining=[1],need=[1],is_ipl=[True],phase=['Death']))
    def test_target_completion_overrides_model(self):
        d=advance(self.state(),1,1,0)
        self.assertEqual(wp(ConstantModel(),d)[0],1)
    def test_exhausted_chase_is_loss(self):
        d=advance(self.state(),0,1,0)
        self.assertEqual(wp(ConstantModel(),d)[0],0)
    def test_first_innings_end_does_not_force_loss(self):
        d=advance(self.state(1),0,1,1)
        self.assertEqual(d.remaining.iloc[0],0)
        self.assertEqual(wp(ConstantModel(),d)[0],.4)
    def test_joint_outcomes_have_expected_absolute_swing(self):
        d=self.state();dist={(2,'Death',True):pd.Series([.5,.5],index=pd.MultiIndex.from_tuples([(0,True,0),(1,True,0)]))}
        self.assertAlmostEqual(leverage(ConstantModel(),d,dist)[0],.5)
if __name__=='__main__':unittest.main()
