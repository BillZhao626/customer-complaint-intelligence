"""Frozen C1 targeted development regression; original B2/R3 never replaced."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b7_live import LOCAL,Budget,now,CORE
from src.evaluation.p5b_pilot import read,write_new
from src.application.p5b3_runtime import Analyzer
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.domain.contracts import EmailInput,digest
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.application.p5b2_prompt import messages
from src.application.p5b5r2_pipeline import ConversationState
from src.evaluation.p5b5r2_judge import diagnose
from src.prompts.p5b7_c1 import GUIDANCE,VERSION
from src.application.p5b7_context_checks import PROFILE

def manifest():
    # The targeted set is declared DEV, not independent holdout. Every baseline
    # contract failure plus every non-mixed intent disagreement is included.
    report=read(ROOT/'docs/p5b7/RESULTS.json')
    ids={r['email_id'] for r in report['arms']['B2']['failed']}
    ids|={r['email_id'] for r in report['intent_consistency']['rows'] if r['matches'] is False}
    paths=CORE+['scripts/p5b7_repair.py','src/application/p5b7_context_checks.py','src/prompts/p5b7_c1.py']
    return dict(version=VERSION,ids=sorted(ids),identity='DEV_TARGETED_REPAIR_NOT_HOLDOUT',at=now(),sources={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
        reason='First90 root causes: contradictions, duplicate evidence, wrong reply language, lexical false rejections and polite unresolved complaints. One general amendment, no individual answers.',
        baseline='B2 original first90 unchanged',champion='B2',promotion='NOT_PROMOTED')

def main():
    frozen=LOCAL/'C1/freeze.json'
    if not frozen.exists():
        f=manifest();write_new(frozen,f)
        import shutil
        for rel in f['sources']:
            dest=LOCAL/'C1/source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
    f=read(frozen)
    if any(sha256((ROOT/p).read_bytes()).hexdigest()!=h for p,h in f['sources'].items()):raise ValueError('C1 source drift')
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    for eid in f['ids']:
        ev=LOCAL/'C1'/eid
        if (ev/'frozen-input.json').exists():
            if not (ev/'run.json').exists():raise ValueError('UNKNOWN no redispatch')
            continue
        d=read(LOCAL/'dataset'/(eid+'.json'));email=EmailInput(email_id=eid,subject=d['subject'],body=d['body'])
        msgs=messages(email);msgs=[('system',msgs[0][1]+GUIDANCE),*msgs[1:]]
        a=Analyzer(replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000),ev,candidate=False);a.messages=lambda e,repair=False:msgs
        a.config=a.config.model_copy(update=dict(prompt_version=VERSION,prompt_hash=digest(msgs[0][1]),parameters=dict(a.config.parameters,experiment='p5b7',arm='C1',freeze_hash=digest(f),messages_hash=digest(msgs),context_check_profile=PROFILE)))
        state=ConversationState(eid);state.update('customer',email.body);runtime=dict(context=state.extract(),events=[])
        write_new(ev/'frozen-input.json',dict(email=email.model_dump(),messages=msgs,runtime=runtime,config=a.config.model_dump(),at=now(),reference_in_prompt=False))
        b=Budget(LOCAL/'budget.sqlite3');b.bind(email,a.config,msgs,'C1')
        r=AnalysisService(Repository(LOCAL/'C1/runs.sqlite3'),a,budget=b).analyze(email);write_new(ev/'run.json',r.model_dump(mode='json'))
        attempt=r.attempts[0];data=attempt.parsed_output or {};reply=data.get('suggested_reply','')
        write_new(ev/'evaluation.json',dict(case_id=eid,arm='C1',run_id=r.run_id,input_hash=email.input_hash,reply=reply,runtime=runtime,first_contract=r.status=='succeeded',error=attempt.error.error_type if attempt.error else None,diagnostic=diagnose(reply,expected_input_hash=email.input_hash)))
        print(eid+' '+r.status,flush=True)
        if r.status=='interrupted_or_unknown' or attempt.metadata.get('dispatch')!='response_received' or attempt.metadata.get('cost_cny') is None:
            b.halt('UNKNOWN_C1');raise RuntimeError('UNKNOWN no redispatch')

if __name__=='__main__':main()
