"""Frozen unseen synthetic scenario check, once per arm, never a human Gold.

Run only after candidate code is final. Scenario requirements never enter prompts.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b5r2_live import LOCAL,freeze,generate_one
from src.application.p5b5r2_pipeline import ConversationStore
from src.domain.contracts import EmailInput
from src.evaluation.p5b5 import read,write_new,hashfile

EXPECTED='961b6cf6cd7f7120469d62848f96b98bb61b1f8a82c6ecaa34f9c504dabd1888'

def generate(arm):
    assert arm in ('B2-SCENARIO','FINAL')
    p=LOCAL/'scenario-holdout.json';assert hashfile(p)==EXPECTED
    cases=read(p)
    if isinstance(cases,dict):cases=cases['cases']
    out=LOCAL/arm;f=freeze(arm,'Final frozen one-pass synthetic scenario evaluation. No tuning on these cases; non-human truth.')
    store=ConversationStore(out/'conversation.sqlite3');rows=[]
    for g in cases:
        history=[];turn=0
        for m in g['input_messages']:
            if m['role']!='customer':continue
            turn+=1;state=store.update(g['case_id'],'customer',m['text'],g['case_id']+f'-T{turn}-customer')
            body=m['text'] if not history else '\n\n'.join(history)+'\n\n[customer · current message]\n'+g['title']+'\n'+m['text']
            e=EmailInput(email_id=g['case_id']+f'-T{turn}',subject=g['title'],body=body)
            run,row=generate_one(e,state,arm,out,f);row['turn']=turn;rows.append(row)
            store.update(g['case_id'],'assistant',row['reply'],g['case_id']+f'-T{turn}-assistant')
            history.extend([f'[customer · turn-{turn} · SYNTHETIC_SCENARIO]\n{g["title"]}\n{m["text"]}',f'[assistant · turn-{turn} · REAL_FIRST_UNSENT]\n{row["reply"]}'])
    write_new(out/'results.json',rows)

def judge():
    from scripts.p5b5r2_live import raw_judge
    from src.evaluation.p5b5r2_judge import JUDGE_SYSTEM_V31,payload_for_pair
    p=LOCAL/'scenario-holdout.json';assert hashfile(p)==EXPECTED
    cases=read(p);cases=cases['cases'] if isinstance(cases,dict) else cases
    gold={g['case_id']:g for g in cases};left=read(LOCAL/'B2-SCENARIO/results.json');right=read(LOCAL/'FINAL/results.json')
    for i,(a,b) in enumerate(zip(left,right,strict=True)):
        payload,order=payload_for_pair(gold[a['case_id']],a,b,reverse=bool(i%2))
        identity=f'SCENARIO-{a["case_id"]}-T{a["turn"]}'
        write_new(LOCAL/'judge-keys'/(identity+'.json'),dict(order=order,case_id=a['case_id'],turn=a['turn'],purpose='INDEPENDENT_TEST',truth='FROZEN_SYNTHETIC_GOALS_NOT_HUMAN_GOLD'))
        raw_judge(payload,identity,JUDGE_SYSTEM_V31)

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='generate':generate(sys.argv[2])
    elif sys.argv[1:]==['judge']:judge()
    else:raise SystemExit('generate B2-SCENARIO|FINAL or judge')
