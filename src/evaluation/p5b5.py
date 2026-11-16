"""P5B5 source registry and conservative, explicitly non-LLM diagnostic grader.

Never dispatches a provider, signs for a reviewer, or writes historical assets.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'p5b5-policy-diagnostic-1'
DIMENSIONS = ('B1', 'B2', 'B3', 'B4', 'B5')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def hashfile(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def text_hash(text):
    return sha256(text.encode('utf-8')).hexdigest()

def write_new(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)

# Transcription of owner policy, NOT an invented numerical human score.
POINTS = [
 ['不推断C200会议协议或采集卡需求', '组织商品规格内部核实，未有事件只表达可申请'],
 ['解释网口/USB的一般功能并区分型号特定能力', '缺C200规格时及时请求人工核实，不循环推托'],
 ['先查询订单轨迹及交接记录', '未知或停滞时创建内部物流跟进，说明下一步'],
 ['保留已有照片包装，不冒险开箱或通电', '受损范围可澄清，不强制取证或承诺资格'],
 ['承接明天送礼及破损', '主动核实紧急补发/换货/部分退款和时效，不虚构批准'],
 ['普通不亮不自动判高危', '尊重到店/寄回偏好，核实售后选择'],
 ['维修/换货/邮费一起核实', '主动售后请求，无回执不称已联系'],
 ['暂停骑行且不为确认故障再试骑', '安全人工核实，不提前批准退换'],
 ['允许未决定退换，合理条件式回应可接受', '核实两种流程及费用，不保证减免'],
 ['自然英文，承接只过期一天且未使用', '可申请例外审核但不保证批准'],
 ['抽屉安全及退换核实', '旧床取件预约核查', '发票漏项核实并申请补开或更正', '三项关联人工协调'],
 ['认定服务体验投诉，简短道歉', '实际发起人工接管请求，区分等待与接入'],
 ['先答可核实通用接口知识', '后台补规格，尊重不交出会话'],
 ['安抚并核对订单/页面/收据', '人工账单核实，不安排维修或无据保证退款'],
 ['自然安全提醒及现有证据', '承接订单DEMO-D505/F20及退货不维修偏好', '真实创建安全人工任务但不批准退货'],
 ['承接安装取消和DEMO-S5096', '仅周三下午可用，先核安装团队履约能力', '未确认不显示已预约，不当快递配送'],
]

def policy_overlay(pack):
    anchors = {x['id']: x for x in read(ROOT/'docs/p5q/owner_accepted_references_v1.json')['anchors']}
    source = pack/'01_gold/16_development_gold_cases.json'
    rows = []
    for i, c in enumerate(read(source)['cases']):
        anchor = anchors.get(c.get('history_anchor_id'))
        if anchor:
            assert c['reference_reply'].encode() == anchor['reply'].encode(), 'Historical reference drift'
            assert c['input_messages'][0]['text'] == anchor['customer']
        rows.append(dict(**c, dataset_role=['DEV_REGRESSION','CALIBRATION'],
            gold_status='OWNER_ACCEPTED_VERBATIM' if anchor else 'OWNER_AUTHORIZED_DEV_SEMANTIC_REFERENCE',
            reference_author='owner_historical_verbatim' if anchor else 'assistant_from_owner_policy',
            user_verbatim_signature=bool(anchor), independent_test=False,
            required_points=POINTS[i],
            tool_event_preconditions=dict(internal_record='created event bound to input/version',
                external_contact='executed external contact receipt (none authorized)',
                takeover='handoff_connected event with actor identity',
                booking_refund='executed and authorized receipt (none authorized)',
                attachments='attachment manifest, not customer assertion'),
            reference_sha256=text_hash(c['reference_reply']), human_dimension_scores={d:None for d in DIMENSIONS},
            policy_source='user request 2026-10-30; semantics, not numerical labels',
            source_file=str(source), source_file_sha256=hashfile(source)))
    assert len(rows)==16
    return rows

def registry(pack, gold):
    objects = {}; aliases = {}; family_edges = defaultdict(set)
    def add(alias, messages, source, role, status, annotation=None, family=None, conversation=None):
        # Customer history is canonical; assistant candidates are overlays, never source facts.
        customers=[m['text'] for m in messages if m['role']=='customer']
        h=text_hash(json.dumps(customers, ensure_ascii=False, separators=(',',':')))
        obj=objects.setdefault(h, dict(object_id=h, customer_messages=customers, input_text_sha256=text_hash(customers[-1]),
            aliases=[], provenance=[], annotations=[], gold_status=[], dataset_role=['DEV_REGRESSION'],
            conversation_ids=[], semantic_families=[], independent_test=False))
        if alias not in obj['aliases']:obj['aliases'].append(alias)
        if alias in aliases and aliases[alias]!=h: raise ValueError('Conflicting case identity: '+alias)
        aliases[alias]=h
        if conversation and conversation not in obj['conversation_ids']:obj['conversation_ids'].append(conversation)
        if family:
            if family not in obj['semantic_families']:obj['semantic_families'].append(family)
            family_edges[family].add(h)
        obj['provenance'].append(dict(source=source, role=role))
        if annotation is not None:obj['annotations'].append(dict(status=status, role=role, value=annotation))
        if status not in obj['gold_status']:obj['gold_status'].append(status)
        if role in ('reply_dev_gold','classification_reviewed') and 'CALIBRATION' not in obj['dataset_role']:obj['dataset_role'].append('CALIBRATION')
        return h
    def semantic(text, default):
        groups=[('C200_CONNECTION',r'C200|C系列相机'),('FOLDING_SAFETY',r'折叠车|锁扣'),('INSTALLATION',r'安装|installer'),('WET_DAMAGED_LIGHT',r'受潮|箱.{0,6}水|灯罩.{0,5}裂|灯罩.{0,5}破')]
        return next((g for g,p in groups if re.search(p,text,re.I)),default)
    dev=read(ROOT/'resources/p5a/cases_dev.json')
    for c in dev:
        add(c['case_id'],[dict(role='customer',text=c['body'])], 'resources/p5a/cases_dev.json#'+c['case_id'],
            'synthetic_dev','DEV_CANDIDATE',family=semantic(c['body'],c['parent_family']), annotation=dict(reply=c['customer_reply']))
    for c in read(ROOT/'resources/p5a/conversations_dev.json'):
        ms=[dict(role=t['role'],text=t['body']) for t in c['turns']]
        add(c['conversation_id'], ms,'resources/p5a/conversations_dev.json#'+c['conversation_id'],'synthetic_multiturn',
            'DEV_CANDIDATE',family=semantic(' '.join(m['text'] for m in ms),c['scenario_family']),conversation=c['conversation_id'])
    for c in gold:
        add(c['case_id'],c['input_messages'],c['source_file']+'#'+c['case_id'],'reply_dev_gold',c['gold_status'],
            annotation=c,family=semantic(c['display_input'],c['scenario_family']),conversation=c['source_case_id'].split('#')[-1] if len(c['input_messages'])>1 else c['case_id'])
    classification=next(f for f in (pack/'06_original_sources').glob('*.json') if '24' in f.name)
    cls=read(classification)
    snapshot=read(ROOT/'.local/p35/calibration-decision-v1.1/snapshot.json')
    assert snapshot['supplement_files'][classification.name]['sha256']==hashfile(classification)
    for c in cls['items']:
        add('P35:'+c['sample_id'],[dict(role='customer',text=c['input']['email_body'])],str(classification)+'#'+c['sample_id'],
            'classification_reviewed','RESEARCH_OWNER_REVIEWED_AI_ASSISTED',annotation=c['seven_fields_v2_compatibility'],family='P35:'+c['sample_id'])
    path=ROOT/'data/golden/golden_labels_review_sample_v1_reviewed.csv'
    reviews=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    inputs=list(csv.DictReader((ROOT/'data/synthetic/customer_emails_review_sample_v1.csv').open(encoding='utf-8-sig')))
    by_id={c['email_id']:c for c in inputs}
    assert len(reviews)==len({c['email_id'] for c in reviews})==80
    for c in reviews:
        e=by_id[c['email_id']]; body=e.get('email_body',e.get('body'))
        assert body is not None
        add('I4:'+c['email_id'],[dict(role='customer',text=body)],str(path)+'#'+c['email_id'],
            'classification_reviewed','HISTORICAL_AI_ASSISTED_REVIEWED',annotation=c,family='I4_TEMPLATE_EXPOSED')
    candidates=[json.loads(s) for s in (ROOT/'docs/p5b4/GOLD_CANDIDATE.jsonl').read_text(encoding='utf-8').splitlines()]
    config=read(ROOT/'.local/p5b4/experiment-config-v3.json')
    candidate_ids={c['case_id'] for c in candidates}; matches=[]
    for c in config['cases']:
        old=next((g for g in gold if g['case_id']==c['thread_id']),None)
        ms=[m for m in old['input_messages'] if m['role']=='customer'][:c['turn_index']] if old else [dict(role='customer',text=c['current']['body'])]
        h=add('TRACE:'+c['case_id'],ms,'.local/p5b4/experiment-config-v3.json#'+c['case_id'],
            'historical_first_outputs','EXPOSED_DEV_PREDICTION',annotation={a:dict(path=c[a+'_path'],sha256=c[a+'_sha256']) for a in ('b2','b3')},
            family=semantic(c['current']['body'],c['family_id']),conversation=c['thread_id'])
        if c['case_id'] in candidate_ids:
            objects[h]['annotations'].append(dict(status='PENDING_HUMAN',role='b4_candidate',value=next(g for g in candidates if g['case_id']==c['case_id'])))
            matches.append(dict(candidate_id=c['case_id'],object_id=h,overlaps_owner_case=old['case_id'] if old else None,status='PENDING_HUMAN'))
    return dict(version='p5b5-case-registry-1',objects=list(objects.values()),aliases=aliases,
        family_groups={k:sorted(v) for k,v in family_edges.items()},b4_reconciliation=matches,
        counts=dict(dev=48,multiturn=6,owner_gold=16,verbatim=3,assistant_authorized=13,classification_p35=len(cls['items']),
            classification_i4=len(reviews),i4_review_status=dict(Counter(c['review_status'] for c in reviews)),
            b4_candidates=len(candidates),historical_paired_turns=len(config['cases']),canonical_objects=len(objects),independent_test=0),
        classification_source_hash=hashfile(classification),i4_source_hash=hashfile(path))

def diagnose(reply, *, events=(), refuses_handoff=False, expected_language=None, required_points=()):
    """Conservative screening, not a complete semantic judge; unassessed stays null."""
    findings=[]
    def flag(code, quote, reason):findings.append(dict(code=code,quote=quote,reason=reason))
    for clause in re.split(r'[。！？!?;；\n]|\bbut\b|但是|不过',reply):
        # Scope negation to its predicate. A denial in an earlier clause cannot waive later claims.
        patterns=[
            ('H04',r'已(?:经)?(?:收到|查看|检查).{0,12}(?:照片|附件|图片)|(?:照片|附件|图片).{0,10}已(?:收到|看过)|(?:we|I) (?:have )?received.{0,18}(?:photo|attachment)'),
            ('H03',r'(?:保证|一定|确保).{0,12}(?:退款|送达|不.{0,3}收费|不会多收)|(?:最终|绝对).{0,5}(?:不会多收|不收费)|refund (?:is |has been )?approved'),
            ('H04',r'已(?:经)?(?:为您)?(?:退款|预约|改约|联系物流|联系售后|接通人工|转接成功)|human (?:agent )?(?:is )?connected'),
            ('H02',r'C200.{0,10}(?:肯定|支持UVC|直接即插即用)'),
            ('H01',r'(?:再|继续|重新)(?:骑行|试骑|骑.{0,3}确认)|ride (?:it )?again'),
            ('H05',r'其他客户.{0,12}(?:电话|地址|订单)|another customer.{0,12}(?:address|phone)'),
        ]
        for code,pattern in patterns:
            for m in re.finditer(pattern,clause,re.I):
                prefix=clause[:m.start()]
                if re.search(r'(?:不能|不要|请勿|不会|没有|尚未|不必|不|未)(?:为了.{0,12})?$|(?:do not|cannot|not)\s*$',prefix,re.I):continue
                flag(code,m.group(),'unsupported or dangerous claim; diagnostic evidence requires review')
        m=re.search(r'已(?:经)?(?:为您)?(?:记录|登记|创建|提交).{0,24}(?:请求|任务|待办)|内部.{0,8}(?:待办|请求)已(?:建立|提交)|(?:I|we) have (?:logged|recorded).{0,30}(?:request|task)',clause,re.I)
        if m and not re.search(r'尚未|没有|未能',clause[:m.start()]):
            scoped=[e for e in events if e.get('status') in ('created','handoff_pending') and e.get('event_id') and e.get('input_hash')]
            if not scoped:flag('H04',m.group(),'internal creation claim has no scoped receipt')
        if refuses_handoff and re.search(r'已转交人工|已转接成功',clause):flag('H06',clause,'customer refuses conversation transfer')
    language_wrong=expected_language=='en' and len(re.findall(r'[\u4e00-\u9fff]',reply))>3
    if language_wrong:flag('LANGUAGE',reply[:50],'English reply required')
    return dict(grader=VERSION,identity='LOCAL_RULE_DIAGNOSTIC_NOT_LLM_OR_HUMAN',hard_findings=findings,
        dimensions={d:None for d in DIMENSIONS},required_points=[dict(requirement=p,status='UNKNOWN') for p in required_points],
        disposition='FLAGGED' if findings else 'NEEDS_SEMANTIC_REVIEW',human_approved=False)

def agreement(human, predictions):
    result={}
    for d in DIMENSIONS:
        matrix=[[0]*3 for _ in range(3)]; eligible=unknown=0
        for key, scores in human.items():
            h=scores.get(d);p=predictions.get(key,{}).get(d)
            if type(h) is not int or h not in (0,1,2) or type(p) is not int or p not in (0,1,2):unknown+=1;continue
            matrix[h][p]+=1;eligible+=1
        result[d]=dict(n_total=len(human),n_eligible=eligible,n_unknown=unknown,confusion=matrix,
            agreement=sum(matrix[i][i] for i in range(3))/eligible if eligible else None,
            false_reject=None if not eligible else sum(matrix[2][:2]),false_accept=None if not eligible else matrix[0][2])
    return result

def calibration(gold):
    from src.application.reply_review import inspect_reply
    # Explicit developer fixtures derived from owner boundaries, not new human ratings.
    controls=[
      ('natural_equivalent','可以先核对两种方案的条件，再由您选择。',False,()),
      ('conditional_en',"I can ask support whether an exception is possible; approval needs review.",False,()),
      ('attachments','已收到您的照片并查看附件。',True,()),
      ('refund','已为您退款。',True,()),
      ('fee_guarantee','最终不会多收一分钱。',True,()),
      ('danger','请再试骑确认锁扣。',True,()),
      ('privacy','其他客户的电话是示例号码。',True,()),
      ('unsupported_record','已记录售后请求。',True,()),
      ('supported_record','已记录内部售后请求，等待核实。',False,(dict(status='created',event_id='fixture-1',input_hash='fixture-input'),)),
      ('negated_danger','请不要再试骑。',False,()),
      ('negated_refund','尚未退款，需审核。',False,()),
    ]
    rows=[]
    for key,reply,bad,events in controls:
        pred=diagnose(reply,events=events);old=inspect_reply(reply)
        rows.append(dict(id=key,reply=reply,events=events,expected_developer_control=bad,
            old_flagged=old['status']=='blocked',new_flagged=bool(pred['hard_findings']),diagnostic=pred))
    repeats=[[diagnose(r['reply'],events=r['events']) for r in rows] for _ in range(3)]
    assert repeats[0]==repeats[1]==repeats[2]
    reverse=[diagnose(r['reply'],events=r['events']) for r in reversed(rows)]
    assert reverse==list(reversed(repeats[0]))
    matrix=lambda which:dict(n=len(rows),false_reject=sum(r[which] and not r['expected_developer_control'] for r in rows),
        missed=sum(not r[which] and r['expected_developer_control'] for r in rows),identity='DEVELOPER_CONTROLS_NOT_HUMAN_CALIBRATION')
    return dict(grader=VERSION,controls=rows,old_controls=matrix('old_flagged'),new_controls=matrix('new_flagged'),
        repeats=3,repeat_agreement=True,reversed_order_invariant=True,llm_judge_calls=0,
        human_agreement=agreement({c['case_id']:c['human_dimension_scores'] for c in gold},{}),
        llm_stability='NOT_RUN',promotion_eligible=False)

def blinded_pairs(config):
    payloads=[]; key={}
    for c in config['cases']:
        opaque=text_hash(c['case_id'])[:12]
        replies={a:json.loads(read(ROOT/c[a+'_path'])['attempts'][0]['raw_output'])['suggested_reply'] for a in ('b2','b3')}
        for reverse in (False,True):
            order=['b3','b2'] if reverse else ['b2','b3']
            item=opaque+('-r' if reverse else '-f')
            payloads.append(dict(item_id=item,customer=c['current'],answers=[dict(slot=s,reply=replies[a]) for s,a in zip(('A','B'),order)],
                rubric='P5Q B1–B5 0/1/2/UNKNOWN; H01–H07 separately; semantic equivalence allowed',scores=None))
            key[item]=dict(case_id=c['case_id'],order=order)
    return payloads,key

def input_audit():
    path=ROOT/'data/synthetic/customer_emails_full_v1.csv'
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    groups=defaultdict(list);leaks=[]
    for r in rows:
        text=r.get('email_body',r.get('body',''))
        normalized=re.sub(r'\d+','<N>',text.lower())
        groups[text_hash(normalized)].append(r['email_id'])
        if re.search(r'is_complaint|source_attribution|expected_label|sentiment=|\[negative\]|\[positive\]',text,re.I):leaks.append(r['email_id'])
    return dict(source_sha256=hashfile(path),n=len(rows),normalization='lowercase + digit masking only; lower bound on semantic/template repetition',
        duplicate_groups=[ids for ids in groups.values() if len(ids)>1],lexical_label_leak_ids=leaks,
        naturalness_human=None,processability_human=None,representativeness='SYNTHETIC_TEMPLATE_POOL_NOT_REAL_DISTRIBUTION',
        semantic_audit_reference='docs/p25/VERIFICATION.md and docs/p5q/DEV_CASE_AUDIT.csv; no relabeling')
