import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from src.domain.contracts import EmailInput
from src.infrastructure.deepseek import LiveError
from scripts import p5b5r2_live as live

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.local=Path(self.tmp.name);self.patcher=patch.object(live,'LOCAL',self.local);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.auth=dict(limits=live.LIMITS,pricing={})
        (self.local/'authorization.json').write_text(json.dumps(self.auth))
        self.b=live.Budget.create(self.local/'budget.sqlite3',[],self.auth)
        with self.b.connection() as c:
            c.execute('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL NOT NULL)')
            c.execute('CREATE TABLE precalls(run_id TEXT PRIMARY KEY,stage TEXT,n_before INTEGER,total REAL,bound REAL,at TEXT)')
        self.email=EmailInput(email_id='fixture',subject='synthetic',body='fixture synthetic only')
        self.msgs=[('system','JSON'),('human','fixture')]
        self.b.bind(self.email,None,self.msgs,'TEST');self.b.acquire('run',self.email.input_hash)
    def reserve(self):return self.b.reserve('run',1,self.email.input_hash,self.msgs,4000)
    def test_request_limit(self):
        with self.b.connection() as c:
            for i in range(300):c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny) VALUES(?,?,?,?)',(str(i),1,self.email.input_hash,.0001))
        with self.assertRaises(LiveError):self.reserve()
    def test_money_limit_including_pending(self):
        with self.b.connection() as c:c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny) VALUES(?,?,?,?)',('prior',1,self.email.input_hash,9.999))
        with self.assertRaises(LiveError):self.reserve()
    def test_preflight_and_settlement(self):
        bound=self.reserve();self.assertGreater(bound,0)
        cost=self.b.estimate_cost(dict(input_tokens=10,output_tokens=10,total_tokens=20));self.assertLess(cost,bound)
        with self.b.connection() as c:self.assertEqual(c.execute('SELECT n_before FROM precalls').fetchone()[0],0)
    def test_unknown_blocks_rebind(self):
        self.reserve();self.b.halt('UNKNOWN')
        with self.assertRaises(LiveError):self.b.bind(self.email,None,self.msgs,'OTHER')
        with self.assertRaises(LiveError):self.reserve()
    def test_content_mismatch_and_retry(self):
        with self.assertRaises(LiveError):self.b.reserve('run',2,self.email.input_hash,self.msgs,4000)
        with self.assertRaises(LiveError):self.b.reserve('run',1,self.email.input_hash,[('human','other')],4000)
    def test_existing_ledger_not_recreated(self):
        with self.assertRaises(FileExistsError):live.Budget.create(self.local/'budget.sqlite3',[],self.auth)

if __name__=='__main__':unittest.main()
