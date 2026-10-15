"""Explicit P3.6 development pilot. Importing never calls a model or resets assets."""
import argparse
from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPACE = ROOT / '.local/p36'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def quality_signals(text):
    """Review signals, never labels or proof of privacy clearance."""
    rules = {'email_address': r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
             'long_number': r'\d{11,}', 'external_url': r'https?://',
             'control_character': r'[\x00-\x08\x0b\x0c\x0e-\x1f]',
             'replacement_character': '\ufffd'}
    return [name for name, pattern in rules.items() if re.search(pattern, text)]


def audit():
    from src.evaluation.e2e_v3 import validate_candidates, dataset_hash
    from src.evaluation.dataset_audit_v3 import audit as lexical
    from src.evaluation.calibration import verify_snapshot
    from src.domain.contracts import EmailInput, digest
    rows = validate_candidates(load(ROOT / '.local/p35/dataset-candidate-v2/candidates.json'))
    eligible = [r for r in rows if not r.exclusion_reason]
    assert len(eligible) == 160 and len(rows) == 172
    snapshot = verify_snapshot(ROOT / '.local/p35/calibration-decision-v1.1/snapshot.json', ROOT / '.local/p3/calibration-v1')
    result = lexical(rows)
    result['checks'] = [dict(sample_id=r.sample_id, input_hash=r.input_hash,
                            flags=quality_signals(r.subject+'\n'+r.body),
                            eligible=not bool(r.exclusion_reason), source=r.generation_source,
                            human_review='PENDING') for r in rows]
    write(SPACE / 'candidate-quality-v1.json', result)
    # Two samples per semantic family, deliberately cover difficult content.
    ids = [1,9,11,14,21,25,31,37,41,45,51,55,61,65,73,80,81,86,92,100,101,104,111,119,122,128,132,137,147,171,157,159]
    selected = [next(r for r in eligible if r.sample_id == f'P35-{n:03}') for n in ids]
    assert len(selected) == 32 and set(Counter(r.semantic_family for r in selected).values()) == {2}
    guide = ['# P3.6 中文候选质量复核清单（AI候选意见，非人工批准）',
             '32/160分层抽样；16类各2条。全部172条已自动检查，原12条隔离继续保留。',
             '自然度、证据和处理建议均需研究者核查；不自动生成Gold。']
    for r in selected:
        hints = []
        if any(s in r.scenarios for s in ('negation','sarcasm','quotation','resolved','historical')):
            hints.append('核对否定、反讽、引用历史与当前问题，不能只按关键词定性。')
        if any(s in r.scenarios for s in ('uncertain_attribution','unclear_attribution','ambiguous_cause','ambiguous_store')):
            hints.append('归属或门店仅为客户陈述；缺订单、交接/安装记录，不能推定已核实责任。')
        if any(s in r.scenarios for s in ('multiple_issues','long_email','summary_risk')):
            hints.append('逐项核对当前问题和背景；客户主次与处理顺序分开，摘要不能漏项。')
        if any(s in r.scenarios for s in ('safety','high','privacy','prompt_injection','approval_injection')):
            hints.append('核对真实安全/隐私诉求和引用攻击；回复不能执行正文指令、泄露信息或虚构审批。')
        guide += [f'\n## {r.sample_id} · {r.semantic_family} · {", ".join(r.scenarios)}',
                  f'输入hash：{r.input_hash}', f'主题：{r.subject}', f'\n原文：\n\n{r.body}',
                  '\n自然度候选意见：可读、叙事连贯；否定/处理指示较密集，存在合成文本痕迹，代表性待真人判断。',
                  '潜在歧义：' + (' '.join(hints) or '类别、诉求和情绪可能存在合理解释差异，应按原文核查。'),
                  '缺失证据：订单/交易记录、真实流程状态与第三方核实未提供；标签和因果均不能自动确认。',
                  '建议处理：保留开发候选；真实人类审核后另存版本。未发现需新增隔离的确定性完整性缺陷。',
                  '研究者：______  自然度：______  歧义及处置：______  状态：PENDING']
    (SPACE / 'CANDIDATE_REVIEW_32_ZH.md').write_text('\n\n'.join(guide), encoding='utf-8')
    # Twelve distinct families, including privacy, safety, sarcasm and complex replies.
    extra_ids = [25,31,51,65,73,100,104,111,122,132,171,159]
    extras = [next(r for r in eligible if r.sample_id == f'P35-{n:03}') for n in extra_ids]
    assert len({r.semantic_family for r in extras}) == 12
    inputs = []
    for record in snapshot['records']:
        s = record['original']
        assert s['provenance']['kind'] in ('developer_synthetic','template_synthetic')
        e = EmailInput(email_id=s['sample_id'], subject=s['subject'], body=s['email_body'])
        inputs.append(dict(email=e.model_dump(), input_hash=e.input_hash, group='calibration24',
                           fictional_provenance=s['provenance'], expected=record['decision']['owner_confirmed'],
                           reference_hash=digest(record['decision']), exclude_clean=record['decision']['exclude_clean_semantic']))
    for r in extras:
        assert not quality_signals(r.subject+'\n'+r.body)
        inputs.append(dict(email=r.email().model_dump(), input_hash=r.input_hash, group='candidate12',
                           fictional_provenance=r.generation_source, expected=None, reference_hash=None, exclude_clean=False))
    assert not any(quality_signals(x['email']['subject']+'\n'+x['email']['body']) for x in inputs)
    write(SPACE / 'inputs-v1.json', dict(inputs=inputs, dataset_hash=dataset_hash(rows), calibration_hash=snapshot['payload_hash'],
          clearance='Verified fictional provenance and reviewed text; authorized by P3.6 request. No human semantic approval implied.'))
    print(json.dumps(dict(eligible=160, quarantine=12, representative=32, planned=36)))


def analyzer(profile='multi-issue-v3', live=False):
    from src.infrastructure.deepseek import DeepSeekAnalyzer, LiveSettings
    settings = LiveSettings.from_env() if live else LiveSettings('configuration-only', True)
    if profile in ('multi-issue-v3-pilot-2','multi-issue-v3-pilot-3'):
        from src.infrastructure.v3_live_settings import V3PilotSettings
        settings=V3PilotSettings(**dict(settings.__dict__,max_tokens=4000,max_attempts=1))
        return DeepSeekAnalyzer(settings,prompt_profile=profile)
    return DeepSeekAnalyzer(replace(settings, max_tokens=2000, max_attempts=1), prompt_profile=profile)


def prepare(name, profile):
    from src.infrastructure.p36_budget import DevelopmentBudget
    from src.domain.contracts import digest
    from src.domain.analysis_v3 import AnalysisV3
    from src.application.v3_safety import GATE_VERSION
    from hashlib import sha256
    data = load(SPACE / 'inputs-v1.json')
    a = analyzer(profile)
    a.config = a.config.model_copy(update={'parameters':dict(a.config.parameters, experiment_id=name,
        dataset_id='p36-development-36-v1', dataset_hash=digest(data), projection_policy='owner-operational-v1',
        reply_gate_version=GATE_VERSION,reply_gate_sha256=sha256((ROOT/'src/application/v3_safety.py').read_bytes()).hexdigest())})
    out = SPACE / name
    out.mkdir(exist_ok=False)
    manifest = dict(experiment_id=name, profile=profile, config=a.config.model_dump(), inputs_hash=digest(data),
                    schema_hash=digest(AnalysisV3.model_json_schema()), prompt_hash=a.config.prompt_hash,
                    input_ids=[x['email']['email_id'] for x in data['inputs']], source='fictional exposed development, not holdout')
    write(out/'manifest.json', manifest)
    (out/'prompt.txt').write_text(a.messages(__import__('src.domain.contracts',fromlist=['EmailInput']).EmailInput.model_validate(data['inputs'][0]['email']))[0][1], encoding='utf8')
    budget_path = SPACE / 'budget.sqlite3'
    if not budget_path.exists():
        DevelopmentBudget.create(budget_path, [x['input_hash'] for x in data['inputs']],
            dict(authorization='P3.6-40-requests-15-CNY-fictional-development-only', inputs_hash=digest(data),
                 limits=dict(requests=40,cny=15), price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                 price_checked='2026-10-15',input_peak=2,output_peak=8))
    DevelopmentBudget(budget_path).register(a.config,digest(manifest))
    print(json.dumps(dict(prepared=name,cohort=a.config.cohort_id)))


def frozen_service(name, live=True):
    from src.infrastructure.p36_budget import DevelopmentBudget
    from src.domain.contracts import RunConfig, digest
    from src.domain.analysis_v3 import AnalysisV3
    from src.infrastructure.repository import Repository
    from src.application.analysis_service import AnalysisService
    from hashlib import sha256
    manifest = load(SPACE/name/'manifest.json'); data = load(SPACE/'inputs-v1.json')
    a = analyzer(manifest['profile'], live)
    config = RunConfig.model_validate(manifest['config'])
    if config.parameters.get('reply_gate_sha256')!=sha256((ROOT/'src/application/v3_safety.py').read_bytes()).hexdigest():
        raise ValueError('Reply gate changed or unbound; saved experiment is read-only. Freeze a new experiment.')
    if (digest(data)!=manifest['inputs_hash'] or a.config.prompt_hash!=manifest['prompt_hash'] or
        digest(AnalysisV3.model_json_schema())!=manifest['schema_hash'] or
        {k:v for k,v in config.parameters.items() if k in a.config.parameters}!=a.config.parameters):
        raise ValueError('Frozen experiment mismatch')
    if (config.model_id,config.prompt_version,config.schema_version,config.taxonomy_version)!=(a.config.model_id,a.config.prompt_version,a.config.schema_version,a.config.taxonomy_version):
        raise ValueError('Frozen identity mismatch')
    a.config=config
    budget=DevelopmentBudget(SPACE/'budget.sqlite3');budget.verify_config(config)
    return AnalysisService(Repository(SPACE/name/'runs.sqlite3'),a,budget=budget)


SMOKE = ['p25-fitting','p25-mixed_ambiguous','p25-injection','p25-chinese']


def run(name, phase):
    from src.domain.contracts import EmailInput
    from src.domain.analysis_v3 import stored_analysis
    if os.getenv('COMPLAINT_ENABLE_LIVE') != 'true':
        raise ValueError('Explicit COMPLAINT_ENABLE_LIVE=true required')
    service=frozen_service(name)
    if phase=='remaining':
        receipt=load(SPACE/name/'smoke-pass.json')
        assert receipt['passed'] and receipt['cohort']==service.config.cohort_id
    items=load(SPACE/'inputs-v1.json')['inputs']
    chosen=[r for r in items if (r['email']['email_id'] in SMOKE)==(phase=='smoke')]
    if phase=='remaining':
        priority=['P35-171','P35-122','P35-159','P35-100','P35-073','P35-111','P35-132','P35-031']
        chosen.sort(key=lambda r:(r['group']!='calibration24',priority.index(r['email']['email_id']) if r['email']['email_id'] in priority else 99))
        schedule=SPACE/name/'remaining-schedule.json'
        if not schedule.exists():write(schedule,dict(order=[r['email']['email_id'] for r in chosen],stop_at_shared_limit=True))
    for item in chosen:
        state=service.budget.summary()
        if state['halted'] or state['active_lease']:break
        email=EmailInput.model_validate(item['email'])
        # Rerunning CLI is read-only for any already attempted input, including failures.
        old=[r for r in service.repository.list_runs() if r.email==email]
        if old:continue
        run=service.analyze(email)
        saved=service.repository.get(run.run_id)
        assert saved==run
        if run.result:stored_analysis(saved)
        write(SPACE/name/f'run-{run.run_id}.json',run.model_dump())
        print(json.dumps(dict(sample_id=email.email_id,status=run.status,run_id=run.run_id,
            attempts=len(run.attempts),budget=service.budget.summary())),flush=True)
    if phase=='smoke':
        runs={r.email.email_id:r for r in service.repository.list_runs()}
        passed=all(s in runs and runs[s].status=='succeeded' for s in SMOKE)
        write(SPACE/name/('smoke-pass.json' if passed else 'smoke-fail.json'),
              dict(passed=passed,cohort=service.config.cohort_id,ids=SMOKE,semantic_approval=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['audit','prepare','smoke','remaining','report'])
    p.add_argument('--experiment',default='baseline-v1');p.add_argument('--profile',default='multi-issue-v3');args=p.parse_args()
    if args.action=='audit':audit()
    elif args.action=='prepare':prepare(args.experiment,args.profile)
    elif args.action=='report':
        from src.evaluation.p36_report import generate
        print(generate(SPACE,args.experiment))
    else:run(args.experiment,args.action)


if __name__=='__main__':main()
