import tempfile,unittest
from pathlib import Path
from src.domain.contracts import EmailInput
from src.application.p5b8_pipeline import execute,check_reply,reply_messages,strip_sentiment
from src.evaluation.p5b8_lexicon import predict

class B8Tests(unittest.TestCase):
    def test_budget_400_hard_limit_and_unknown_lease(self):
        from scripts import p5b8_live as live
        import json
        old=live.LOCAL
        with tempfile.TemporaryDirectory() as folder:
            try:
                live.LOCAL=Path(folder);auth=dict(limits=live.LIMITS);(live.LOCAL/'authorization.json').write_text(json.dumps(auth),encoding='utf-8')
                b=live.Budget.create(live.LOCAL/'budget.sqlite3',[],auth)
                with b.connection() as c:c.executescript('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL);CREATE TABLE precalls(run_id TEXT PRIMARY KEY,stage TEXT,n_before INTEGER,total_before REAL,bound REAL,privacy_check TEXT,created_at TEXT);')
                e=EmailInput(email_id='fixture',subject='',body='fixture');msgs=[('human','fixture')];b.bind(e,None,msgs,'TEST')
                with b.connection() as c:c.executemany('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at,completed) VALUES(?,1,?,0,?,1)',[(str(i),e.input_hash,'fixture') for i in range(399)])
                b.acquire('400',e.input_hash);b.reserve('400',1,e.input_hash,msgs,4000)
                with self.assertRaises(Exception):b.acquire('UNKNOWN_RETRY',e.input_hash)
                b.completed('400',1);b.release('400');b.acquire('401',e.input_hash)
                with self.assertRaises(Exception):b.reserve('401',1,e.input_hash,msgs,4000)
            finally:live.LOCAL=old
    def test_budget_12_cny_and_invalid_usage(self):
        from scripts import p5b8_live as live
        import json
        old=live.LOCAL
        with tempfile.TemporaryDirectory() as folder:
            try:
                live.LOCAL=Path(folder);auth=dict(limits=live.LIMITS);(live.LOCAL/'authorization.json').write_text(json.dumps(auth),encoding='utf-8')
                b=live.Budget.create(live.LOCAL/'budget.sqlite3',[],auth)
                with b.connection() as c:
                    c.executescript('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL);CREATE TABLE precalls(run_id TEXT PRIMARY KEY,stage TEXT,n_before INTEGER,total_before REAL,bound REAL,privacy_check TEXT,created_at TEXT);')
                    c.execute("INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES('prior',1,'fixture',11.99,'fixture')")
                e=EmailInput(email_id='fixture',subject='',body='fixture');msgs=[('human','fixture')];b.bind(e,None,msgs,'TEST');b.acquire('next',e.input_hash)
                with self.assertRaises(Exception):b.reserve('next',1,e.input_hash,msgs,4000)
                with self.assertRaises(RuntimeError):b.estimate_cost({'input_tokens':None})
            finally:live.LOCAL=old
    def test_baseline_boundaries(self):
        cases={'产品很好':'positive','真的很失望':'negative','不满意':'negative','没有不满意':'neutral','虽然产品好，但是物流差':'mixed','耳机没声音，请问怎么维修？':'neutral','请问库存有蓝色吗？谢谢。':'neutral'}
        for text,label in cases.items():self.assertEqual(predict(text)['expressed_sentiment'],label,text)
    def test_receipts_idempotency_scope_and_no_external(self):
        with tempfile.TemporaryDirectory() as d:
            e=EmailInput(email_id='fixture',subject='',body='物流延误，请核实。')
            a=[dict(kind='logistics_followup',issue_ids=['I1'],goal='check',evidence=['物流延误'],priority='normal')]
            r=execute(e,a,Path(d)/'actions.sqlite3');self.assertEqual(r,execute(e,a,Path(d)/'actions.sqlite3'))
            self.assertEqual(check_reply(e,'已登记内部物流跟进请求，目前等待核实。',r)['hard_findings'],[])
            self.assertTrue(check_reply(e,'已登记内部物流跟进请求。',dict(events=[]))['hard_findings'])
            self.assertTrue(check_reply(e,'已经向物流公司确认包裹已发出。',r)['hard_findings'])
            self.assertTrue(all(x['payload']['external_execution'] is False for x in r['events']))
    def test_safety_negation_and_real_test(self):
        e=EmailInput(email_id='fixture',subject='',body='锁扣松了，差点摔倒。')
        self.assertFalse(check_reply(e,'请不要再试骑，先暂停骑行。',dict(events=[]))['hard_findings'])
        self.assertTrue(check_reply(e,'请再试骑确认锁扣。',dict(events=[]))['hard_findings'])
    def test_ab_information_and_ablation(self):
        e=EmailInput(email_id='fixture',subject='',body='产品很好但物流差。');r=dict(events=[],facts={'status':'UNKNOWN'})
        import json
        a=json.loads(reply_messages(e,r)[1][1]);b=json.loads(reply_messages(e,r,{'sentiment':'mixed'})[1][1]);b.pop('structured_analysis');self.assertEqual(a,b)
        self.assertEqual(strip_sentiment({'issues':[{'sentiment':'negative','experience_polarity':'negative','customer_requests':['check']}]}),{'issues':[{'customer_requests':['check']}]})
    def test_language_attachment(self):
        e=EmailInput(email_id='fixture',subject='',body='I sent photos. Please check the charge.')
        self.assertTrue(check_reply(e,'您好，请提供照片。',dict(events=[]))['hard_findings'])
        self.assertTrue(check_reply(e,'I have received the photos.',dict(events=[]))['hard_findings'])
if __name__=='__main__':unittest.main()
