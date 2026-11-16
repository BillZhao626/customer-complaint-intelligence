import unittest
from src.application.p5b5r2_guard import inspect
from src.domain.contracts import EmailInput

class GuardTests(unittest.TestCase):
    def test_unrelated_task_cannot_support_logistics_record(self):
        e=EmailInput(email_id='scope',subject='物流',body='查询包裹')
        events=[dict(event_id='fixture',input_hash=e.input_hash,kind='invoice_request',status='created')]
        result=inspect(e,{},'已记录物流情况，请等待核实。',events=events)
        self.assertIn('executed_action',{f['code'] for f in result['findings'] if f['severity']=='block'})
    def test_unrelated_electrical_warning_cannot_waive_stop_riding(self):
        e=EmailInput(email_id='scope',subject='车架锁扣',body='车架锁扣自行打开，差点摔。')
        d=dict(issues=[dict(issue_id='i',risk_level='severe',urgency='high',risk_evidence=[dict(field='body',start=0,end=len(e.body),quote=e.body)])])
        result=inspect(e,d,'请不要通电，等待处理。')
        self.assertIn('missing_stop_use_advice',{f['code'] for f in result['findings'] if f['severity']=='block'})
    def test_safe_stop_synonyms_do_not_waive_bad_analysis(self):
        email=EmailInput(email_id='safe',subject='锁扣问题',body='车架锁扣自行打开，差点摔。')
        result=inspect(email,{},'请停止骑行，不要再试骑。',accepted=False)
        codes={f['code'] for f in result['findings'] if f['severity']=='block'}
        self.assertIn('analysis_not_accepted',codes)
        self.assertNotIn('missing_stop_use_advice',codes)
    def test_unsafe_power_and_missing_receipt_block(self):
        email=EmailInput(email_id='bad',subject='破损灯',body='箱子浸水灯罩破裂')
        result=inspect(email,{},'请通电试一下，已登记售后请求。',accepted=True)
        self.assertIn('H01',{f['code'] for f in result['findings']})
        self.assertIn('H04',{f['code'] for f in result['findings']})
    def test_transport_cause_not_forgiven_by_safe_reply(self):
        email=EmailInput(email_id='rain',subject='雨淋',body='外箱被雨淋湿')
        data=dict(issues=[dict(issue_id='i',reason='delivery delay',evidence=[dict(field='body',start=0,end=7,quote=email.body)])])
        result=inspect(email,data,'先不要通电。',accepted=True)
        self.assertIn('unsupported_delivery_delay',{f['code'] for f in result['findings']})
