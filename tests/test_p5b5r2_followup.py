from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import p5b5r2_live as live
from src.application.mail_threads import assemble_context
from src.domain.contracts import digest

class FollowupTests(unittest.TestCase):
    def test_real_context_uses_saved_edited_simulation_and_latest_constraint(self):
        context=[dict(role='customer',body='我要预约安装，订单DEMO-S1。',subject='安装',at='fixture',source='synthetic'),
                 dict(role='assistant_simulation',body='已登记内部安装核实请求，尚未预约。',subject='模拟回复',at='fixture',source='simulation_only')]
        latest='我要取消安装，不要再预约。另请补开发票。'
        captured={}
        def fake(email,state,arm,out,f,**kwargs):
            captured.update(email=email,state=state.extract(),arm=arm,context_hash=kwargs['context_hash']);return 'saved-real-run',{}
        with TemporaryDirectory() as tmp,patch.object(live,'LOCAL',Path(tmp)),patch.object(live,'freeze',return_value={}),patch.object(live,'generate_one',side_effect=fake):
            result=live.generate_followup_ui(SimpleNamespace(run_id='parent-run'),latest,'operation-fixture',context_messages=context,subject='补充')
        self.assertEqual(result,'saved-real-run')
        self.assertEqual(captured['email'].body,assemble_context(context,'补充',latest))
        self.assertEqual(captured['context_hash'],digest(context))
        self.assertTrue(captured['state']['installation_cancelled'])
        self.assertIn('DEMO-S1',captured['state']['identifiers'])
        self.assertEqual(captured['arm'],'UI-FOLLOWUP')
    def test_unreviewed_history_rejected_without_model(self):
        with TemporaryDirectory() as tmp,patch.object(live,'LOCAL',Path(tmp)),patch.object(live,'generate_one') as generate:
            with self.assertRaises(ValueError):live.generate_followup_ui(SimpleNamespace(run_id='p'),'x','operation-fixture',context_messages=[dict(role='customer',body='fixture')],subject='x')
            generate.assert_not_called()
