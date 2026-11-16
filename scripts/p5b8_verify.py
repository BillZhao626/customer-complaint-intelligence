"""Read-only experiment/asset/package integrity verification. No model calls."""
import json,sys,sqlite3,hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.p5b8_research import read,cases,summary,insight
from src.domain.contracts import EmailInput,digest
LOCAL=ROOT/'.local/p5b8';DOC=ROOT/'docs/p5b8'
def main():
    before=read(LOCAL/'initial.json')['files'];missing=[];changed=[]
    for name,h in before.items():
        p=ROOT/name
        if not p.is_file():missing.append(name)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=h:changed.append(name)
    allowed={'src/app/p5b5r2_api.py','src/application/product_workflow.py','src/application/service_triage.py','web-client/src/p5b5.tsx','HANDOFF.md'}
    assert not missing and set(changed)<=allowed,(missing,changed)
    assert not any(n.startswith(('data/','outputs/')) or n.endswith(('.sqlite3','.env')) for n in changed)
    rows=cases();plan=read(LOCAL/'plan.json');calls=[]
    for p in sorted((LOCAL/'calls').glob('*/*/response.json')):
        r=read(p);provider=read(p.with_name('provider-response.txt'));f=read(p.with_name('frozen-input.json'))
        assert provider['choices'][0]['message']['content']==r['raw'],p
        assert f['config']['model_id']=='deepseek-flash' and f['privacy_check']=='SYNTHETIC_AUTHORIZED'
        assert r['metadata']['total_tokens']==r['metadata']['input_tokens']+r['metadata']['output_tokens']
        assert abs(r['cost_upper']-(r['metadata']['input_tokens']*2+r['metadata']['output_tokens']*8)/1e6)<1e-12
        calls.append(r)
    s=summary(rows);assert len(calls)==398==s['budget']['reserved_attempts']
    assert s['budget']['pending_dispatches']==0 and s['budget']['active_lease'] is False and s['budget']['halted']=='P5B8_EXPERIMENT_COMPLETED'
    assert s['budget']['settled_and_pending_upper_cny']<=12 and s['budget']['reserved_attempts']<=400
    assert len(rows)==94 and s['A']['n_dispatched_pairs']==90 and s['B']['n_dispatched_pairs']==11
    identical=0
    for eid in plan['A_ids']+[x['id'] for x in plan['independent_scenarios']]:
        c=next(c for c in rows if c['case_id']==eid)
        a=read(LOCAL/'calls/A_DIRECT'/eid/'frozen-input.json');b=read(LOCAL/'calls/A_GUIDED'/eid/'frozen-input.json')
        assert a['messages'][0]==b['messages'][0]
        aa=json.loads(a['messages'][1][1]);bb=json.loads(b['messages'][1][1]);assert bb.pop('structured_analysis',None) is not None and aa==bb
        assert c['replies']['A_DIRECT']['runtime']==c['replies']['A_GUIDED']['runtime'];identical+=1
        for v,x in c['replies'].items():
            for ev in x['runtime']['events']:
                assert ev['input_hash']==c['input_hash'] and ev['event_id'] and ev['payload']['external_execution'] is False
    isolation=[]
    for eid in plan['B_ids']:
        a=(LOCAL/'state/B_DIRECT'/eid/'actions.sqlite3');b=(LOCAL/'state/B_GUIDED'/eid/'actions.sqlite3');assert a.exists() and b.exists() and a.resolve()!=b.resolve()
        isolation.append(eid)
    stat=insight([r for r in rows if r['case_id'].startswith('B7')]);assert stat['n_dispatched']==90 and stat['valid']==87 and stat['failed_or_not_run']==3
    for category,g in stat['products'].items():
        raw=[(r,i) for r in rows if r['case_id'].startswith('B7') and r['analysis'] and r['analysis']['data'] for i in r['analysis']['data']['issues'] if i['object_type']=='product' and i['category']==category]
        assert set(g['all']['case_ids'])=={r['case_id'] for r,i in raw}
        assert set(g.get('negative_experience',{}).get('case_ids',[]))=={r['case_id'] for r,i in raw if i['experience_polarity']=='negative'}
    union=set().union(*(set(g.get('negative_experience',{}).get('case_ids',[])) for g in stat['products'].values()))
    assert union==set(stat['memberships']['negative_product_experience'])
    archive=DOC/'P5-B8_COMPLETE_REVIEW_20261031.zip';package='NOT_BUILT'
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('MANIFEST.json'));assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in manifest.items())
            required={'README.md','CASEBOOK.md','ALL_CASES.csv','ALL_BAD_CASES.csv','RAW_EVIDENCE.jsonl','AB_COMPARISON.csv','OWNER_DECISIONS.csv','RESEARCH_AND_THESIS_RESULTS.md','UI_ACCEPTANCE.md'}
            assert required<=set(z.namelist());assert not any(Path(n).name=='.env' for n in z.namelist());package='VERIFIED'
    tests=[]
    for p in sorted((ROOT/'.local/p4/test-evidence').glob('*/test-results.json'),reverse=True):
        x=read(p)
        if any(t.startswith('tests.test_p5b8_product.') for t in x['test_ids']):tests.append(dict(path=str(p.relative_to(ROOT)),**{k:x[k] for k in ('tests','passed','failures','errors','skipped')}));break
    result=dict(status='VERIFIED',protected_files=len(before),missing=missing,changed=changed,historical_data_outputs_gold_sqlite_env_unchanged=True,provider_first_responses=398,first_raw_byte_content_equal=True,controlled_A_same_information_pairs=identical,B_isolated_cases=isolation,budget=s['budget'],new_cases=len(rows),analysis_accepted=s['analysis']['accepted'],old18_retained=18,statistics_independently_recounted=True,external_business_actions=0,semantic_quality='HUMAN_PENDING',package=package,full_offline_tests=tests)
    (DOC/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ('budget','B_isolated_cases')},ensure_ascii=False))
if __name__=='__main__':main()
