"""R11 identities and human materials; never calls a model."""
import csv
from html import escape
import json
from pathlib import Path
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.r11_audit import LOCAL,DOCS,read,save,sha
from src.domain.contracts import digest

def main():
    old=ROOT/'.local/r10-quality-20261109-v1'
    for revision in ('fixed-v3','diagnostic-v4'):
        target=LOCAL/'historical-source'/revision
        if not target.exists():
            with zipfile.ZipFile(old/f'{revision}-source.zip') as z:
                for info in z.infolist():
                    dest=(target/info.filename).resolve()
                    assert dest.is_relative_to(target.resolve())
                z.extractall(target)
    manifest=read(old/'dev-cases.json')
    for c in manifest['cases']:
        p=old/'traces/fixed-v3'/c['case_id']/'GUIDED-reply.json'
        c.update(r10_trace=p.relative_to(ROOT).as_posix(),r10_trace_sha256=sha(p))
    save(LOCAL/'dev-cases.json',manifest)
    history=[]
    files=[old/'dev-cases.json',ROOT/'.local/r9-quality-20261109-v1/holdout-v1-cases.json',
           ROOT/'.local/r9-quality-20261109-v1/holdout-v4-cases.json',old/'holdout-v3-cases.json',old/'controls.json']
    for p in files:
        rows=read(p)
        if isinstance(rows,dict): rows=rows['cases']+rows.get('diagnostics',[])
        for c in rows:
            from src.domain.contracts import EmailInput
            email=EmailInput.model_validate(c['email'])
            history.append(dict(case_id=email.email_id,input_hash=email.input_hash,family=c['family'],
                                email=email.model_dump(),source=p.relative_to(ROOT).as_posix(),
                                exposure='EXPOSED_DEVELOPMENT',text_hash=digest(email.body)))
    save(LOCAL/'exposure-registry.json',history)
    plan=dict(authorization_scope='R11-20261109-ONE-LEDGER',planned_requests=1200,proposed_cny_cap=30,
              allowed_call_ids=[f'R11-{i:04}' for i in range(1,1201)],
              pricing=dict(input_cny_per_million=2,output_cny_per_million=8,checked='2026-11-09',
                           source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                           basis='peak cache-miss upper estimate, actual debit unknown'))
    save(LOCAL/'plan.json',plan)
    save(LOCAL/'authorization.json',dict(scope=plan['authorization_scope'],cny=30,provider_requests=1200,
        plan_hash=digest(plan),historical_authorization_reused=False,
        user_approval_verbatim='本次新建独立账本，授权上限人民币30元、最多1,200次底层Provider请求，以先到者为准，不复用R10旧账本，也不自动超额。'))
    cards=[];key=[]
    original=read(ROOT/'docs/r10-quality-20261109-v1/human-review/blind-inputs.json')
    cases={c['case_id']:c for c in read(old/'holdout-v3-cases.json')}
    # Withheld family labels are never used to tune the candidate Judge.
    cal_ids={'R10H-005','R10H-009','R10H-013','R10H-020','R10H-021','R10H-024'}
    unblind=read(old/'human-unblinding-key.json')
    for item in original:
        cid=next(k['case_id'] for k in unblind if k['blind']==item['id'])
        for a in item['answers']:
            cards.append(dict(email=cases[cid]['email'],reply=a['reply'],events=a['events'],facts=item['facts'],
                required_points=item['goals'],forbidden_claims=item['prohibited'],family=cases[cid]['family'],
                split='CALIBRATION_DEV' if cid in cal_ids else 'JUDGE_INDEPENDENT_VALIDATION'))
            key.append(dict(case_id=cid,source=next(k['source'] for k in unblind if k['blind']==item['id'] and k['slot']==a['label'])))
    for c in manifest['cases']:
        if c['case_id'] not in manifest['owner_ids']:continue
        record=read(ROOT/c['r10_trace'])
        cards.append(dict(email=c['email'],reply=record['slot']['reply'],events=record['runtime']['events'],
                          facts=record['slot']['facts'],family=c['family'],required_points='Assess current goals individually against the full source.',
                          forbidden_claims='No unsupported facts, actions or unnecessary sensitive intake.',split='CALIBRATION_DEV'))
        key.append(dict(case_id=c['case_id'],source='R10_FIXED_V3_MODEL_FIRST',owner_historical=c.get('owner')))
    for cid in ('R10H-010','R10H-014','R10H-023'):
        c=cases[cid];record=read(old/'traces/holdout-v3'/cid/'GUIDED-reply.json')
        cards.append(dict(email=c['email'],reply=record['slot']['reply'],events=record['runtime']['events'],facts=record['slot']['facts'],
                          family=c['family'],required_points=c['required'],forbidden_claims=c['forbidden'],split='CALIBRATION_DEV'))
        key.append(dict(case_id=cid,source='R10_TRANSFER_MODEL_FIRST'))
    for c in read(old/'controls.json')[:6]:
        for s in c['slots']:
            cards.append(dict(email=c['email'],reply=s['reply'],events=s['events'],facts=s.get('facts',{}),family=c['family'],
                              required_points='Assess current goals and distinguish proposal, created and completed.',
                              forbidden_claims='Unsupported execution and dangerous advice.',split='CALIBRATION_DEV'))
            key.append(dict(case_id=c['email']['email_id'],source='RESEARCHER_AUTHORED_CONTROL_NOT_GOLD'))
    assert 36<=len(cards)<=60
    lines=['<!doctype html><meta charset="utf-8"><title>R11 Human review</title><style>body{font:17px/1.6 system-ui;max-width:1050px;margin:auto;padding:32px;background:#f4f4f5}article{background:white;margin:24px 0;padding:24px}pre{white-space:pre-wrap;font:inherit}textarea{width:100%;height:130px}</style>',
           '<h1>Independent review of customer service replies</h1><p>Score attitude, helpfulness, action accuracy, reliability and information density 0–2, or N/A with a reason. Record PASS/PARTIAL/FAIL/UNKNOWN, exact source and reply evidence, and missing essential next steps. Local created tasks remain pending. Complete judgments independently. Blank fields are not Gold. Save your own CSV using the provided form; no ratings are sent externally.</p>']
    for i,c in enumerate(cards,1):
        c['review_id']=f'R11-B{i:03}'
        key[i-1].update(review_id=c['review_id'],split=c['split'],family=c['family'])
        lines.append(f'<article><h2>{c["review_id"]}</h2><h3>Customer email</h3><pre>{escape(c["email"]["subject"]+chr(10)+c["email"]["body"])}</pre><h3>Reply</h3><pre>{escape(c["reply"])}</pre><h3>Available local evidence</h3><pre>{escape(json.dumps(dict(events=c["events"],facts=c["facts"]),ensure_ascii=False,indent=2))}</pre><p><b>Required checks:</b> {escape(c["required_points"])}<br><b>Prohibited:</b> {escape(c["forbidden_claims"])}</p><p>Human opinion and evidence (unfilled)</p><textarea></textarea></article>')
    save(LOCAL/'human-unblinding-key.json',key)
    save(DOCS/'human-review/blind-inputs.json',cards)
    save(DOCS/'human-review/split-manifest.json',[dict(review_id=c['review_id'],family=c['family'],split=c['split'],human_gold=None) for c in cards])
    (DOCS/'human-review/blind-review.html').write_text('\n'.join(lines),'utf8')
    path=DOCS/'human-review/reviewer_blank.csv'
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['reviewer','review_id','attitude','helpfulness','action_accuracy','reliability','information_density','verdict','hard_error','source_quote','reply_quote','reason'])
        w.writerows([['',c['review_id']]+['']*10 for c in cards])
    save(DOCS/'human-review/status.json',dict(candidates=len(cards),scenarios=len({k['case_id'] for k in key}),
        human_completed=0,independent_human_gold=0,second_reviewer=None,agreement=None,kappa=None))
    print(f'{len(cards)} blinded responses prepared; human Gold 0')

if __name__=='__main__':main()
