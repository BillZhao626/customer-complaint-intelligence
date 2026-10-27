"""Explicit offline entry; never collects legacy API scripts. No external sockets."""
import os
from pathlib import Path
import socket
import sys
import json
import time
import unittest
import tempfile
import atexit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false')
# Older UI suites predate P4 and isolate only their P3 analysis database.
# Give every collected test safe defaults, even when the invoking shell points
# at a researcher's open workspace. Individual fixtures may override these.
test_storage=tempfile.TemporaryDirectory(prefix='complaint_offline_')
atexit.register(test_storage.cleanup)
os.environ.update(COMPLAINT_PRODUCT_DB=str(Path(test_storage.name)/'product.sqlite3'),
                  COMPLAINT_DB_PATH=str(Path(test_storage.name)/'analysis.sqlite3'))
original_connect=socket.socket.connect
def blocked(*args,**kwargs):
    # Windows asyncio creates a local socketpair for wakeups; permit only stdlib's internal call.
    caller=sys._getframe(1)
    if caller.f_code.co_name in ('socketpair','_fallback_socketpair') and Path(caller.f_code.co_filename).resolve()==Path(socket.__file__).resolve():
        address=args[1] if len(args)>1 else None
        if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
            return original_connect(*args,**kwargs)
    raise RuntimeError('Network disabled by P1 offline test runner')
socket.socket.connect=blocked
socket.socket.connect_ex=blocked
socket.create_connection=blocked
import asyncio
async def blocked_async_connection(*args,**kwargs):
    raise RuntimeError('External async connections disabled by offline test runner')
asyncio.BaseEventLoop.create_connection=blocked_async_connection
# Reject writes to frozen research assets even when an accidental test calls
# a historical writer. Temporary database/export paths are unaffected.
protected=[(ROOT/p).resolve() for p in ('data/raw','data/synthetic','data/golden','outputs','docs/dissertation')]
def check_path(value):
    if isinstance(value,(str,bytes,os.PathLike)):
        path=Path(os.fsdecode(value)).resolve()
        if any(path.is_relative_to(p) for p in protected):
            raise PermissionError('P1 test attempted to modify a protected research asset')
def audit(event,args):
    if event=='open':
        path,mode,flags=args
        if (mode and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            check_path(path)
    elif event in ('os.remove','os.rmdir','os.rename','os.replace'):
        for value in args[:2]:
            check_path(value)
sys.addaudithook(audit)
if len(sys.argv)>1 and sys.argv[1]=='--portable':
    suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_portable','tests.test_p25','tests.test_p3','tests.test_p35','tests.test_p36','tests.test_p37','tests.test_p38','tests.test_p39','tests.test_urgency_context','tests.test_p39_context_live','tests.test_p39_observed_limits','tests.test_p39_continuity','tests.test_p39_continuity_report','tests.test_p39r3_causal','tests.test_p39r3_challenger','tests.test_p39_exploration','tests.test_p310','tests.test_p310_execution','tests.test_p310_report','tests.test_p310_correction','tests.test_p310_leakage','tests.test_p310_scoped_diagnostic','tests.test_product_quality','tests.test_product_workflow','tests.test_product_ui','tests.test_csv_input','tests.test_product_analysis','tests.test_p5_preflight'])
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('tests.test_copilot'))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('tests.test_p46_inbox'))
else:
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=sys.argv[1] if len(sys.argv)>1 else 'test_*.py',top_level_dir=str(ROOT))
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item.id()
ids=list(flatten(suite))
started=time.perf_counter()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if len(sys.argv)==1:
    evidence=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
                  passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),elapsed_seconds=time.perf_counter()-started,
                  network='socket connections blocked',asset_writes='audit hook blocked',test_ids=ids,
                  failure_ids=[t.id() for t,_ in result.failures+result.errors])
    # New phase evidence must never overwrite frozen P1/P2 reports.
    evidence_dir=ROOT/'.local/p4/test-evidence'/time.strftime('%Y%m%dT%H%M%S')
    evidence_dir.mkdir(parents=True,exist_ok=False)
    (evidence_dir/'test-results.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
sys.exit(not result.wasSuccessful())
