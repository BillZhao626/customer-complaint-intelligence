"""B2 candidate composition: scoped facts, active local work, explicit receipts.

This module has no provider credentials, network client, or external executor.
The injectable Runnable ends at a caller-supplied model; preparing is not generation.
"""
from contextlib import closing, contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3
from uuid import uuid4
from src.domain.contracts import digest

VERSION='p5b5-b2-actions-facts-1'

def now():return datetime.now(timezone.utc).isoformat()

@dataclass
class ConversationState:
    conversation_id: str
    messages: list = field(default_factory=list)
    identifiers: list = field(default_factory=list)
    preferred_outcome: str|None = None
    availability: str|None = None
    refuses_handoff: bool = False

    def update(self, role, text):
        self.messages.append(dict(role=role,text=text))
        if role!='customer':return
        ids=re.findall(r'\b(?:DEMO-[A-Z0-9-]+|F\d{2,}|L\d{2,}|C\d{2,})\b',text,re.I)
        # Explicit correction replaces order identifiers; assistant assertions never do.
        if re.search(r'写错|更正|号码不对|wrong (?:order|number)|correction',text,re.I) and ids:
            self.identifiers=[x for x in self.identifiers if not x.upper().startswith('DEMO-')]
        self.identifiers=list(dict.fromkeys(self.identifiers+ids))
        if re.search(r'更想退|想退|退掉|退货|refund|return it',text,re.I):self.preferred_outcome='return'
        if re.search(r'改成换|还是换|换货|exchange instead',text,re.I):self.preferred_outcome='exchange'
        if re.search(r'不想修|不要维修|不.{0,3}维修',text):
            if self.preferred_outcome is None:self.preferred_outcome='no_repair'
        if re.search(r'周[一二三四五六日天]|Wednesday|afternoon',text,re.I):self.availability=text
        if re.search(r'不要转人工|不用转人工|不想.{0,3}人工|no human|do not transfer|don.t transfer',text,re.I):self.refuses_handoff=True
        elif re.search(r'我要人工|现在转人工|human please|speak to an agent',text,re.I):self.refuses_handoff=False

    @property
    def customers(self):return '\n'.join(m['text'] for m in self.messages if m['role']=='customer')

    def extract(self):
        text=self.customers;latest=next((m['text'] for m in reversed(self.messages) if m['role']=='customer'),'')
        rules=[('product_knowledge',r'C200|接口|规格|兼容|USB|webcam|specification'),
          ('logistics',r'物流|快递|揽收|包裹|配送|tracking|parcel|courier|delivery'),
          ('aftersales',r'台灯|耳机|灯罩|断音|不亮|坏|破|退货|换货|邮费|维修|refund|return|repair|exchange'),
          ('safety',r'锁扣|差点摔|冒烟|火花|漏电|进水|受潮|电源袋.{0,5}湿|抽屉.{0,20}(?:滑|磕)|latch|spark|smoke'),
          ('pickup',r'取旧|取件|旧床|collection|pickup'),
          ('invoice',r'发票|invoice'),('billing',r'多收|收费|扣款|收据|charged|billing'),
          ('installation',r'安装|installer|installation|appointment')]
        issues=[dict(kind=k,source_quote=m.group(),source='customer_report') for k,p in rules if (m:=re.search(p,text,re.I))]
        wants=bool(re.search(r'我要人工|要人工客服|人工客服接手|human please|speak to an agent',latest,re.I)) and not self.refuses_handoff
        # Billing installation inquiry does not mean requesting an installation appointment.
        kinds={x['kind'] for x in issues}
        if 'billing' in kinds and not re.search(r'取消|排期|预约|改约|cancel|reschedul',text,re.I):issues=[x for x in issues if x['kind']!='installation']
        if re.search(r'产品正常|不需要维修|别.{0,6}维修',text):issues=[x for x in issues if x['kind']!='aftersales']
        return dict(issues=issues,latest_request=latest,identifiers=self.identifiers,preferred_outcome=self.preferred_outcome,
            availability=self.availability,refuses_handoff=self.refuses_handoff,wants_human=wants,
            service_complaint=wants and bool(re.search(r'没人|自动回复|反复|again|ignored',text,re.I)),
            urgent=bool(re.search(r'明天|紧急|tomorrow|urgent',text,re.I)))

def plan(state):
    ctx=state.extract();kinds={x['kind'] for x in ctx['issues']};actions=[]
    def add(kind,owner,question):
        actions.append(dict(kind=kind,owner=owner,question=question,priority='high' if 'safety' in kinds or ctx['urgent'] else 'normal'))
    if 'product_knowledge' in kinds:add('knowledge_lookup','product_support','查授权规格及通用知识；C200特定协议未知时保留未知')
    if 'logistics' in kinds:add('logistics_lookup','logistics','查订单交接记录与最新物流，不把客户页面当承运商确认')
    if 'installation' in kinds:
        add('installer_schedule_lookup','installation_service','核实安装团队履约及最新可用时间：'+str(ctx['availability']))
        add('installation_request','installation_service','登记安装协调及可用时间，未确认不创建预约')
    if 'pickup' in kinds:add('pickup_lookup','collection_service','核查旧物取件预约与未履约情况')
    if 'invoice' in kinds:add('invoice_request','billing','核实订单漏项与发票更正授权')
    if 'billing' in kinds:add('billing_request','billing','对照订单、页面、票据，核实正当费用与差额，不承诺退款')
    if 'aftersales' in kinds or 'safety' in kinds:
        add('aftersales_request','aftersales','核实售后、寄回/到店、运费及退换选择；紧急时核实补发/部分退款可行性；偏好：'+str(ctx['preferred_outcome']))
    if ctx['wants_human'] or 'safety' in kinds or len(kinds & {'pickup','invoice','aftersales','safety'})>=3:
        add('handoff_request','customer_support','携带本会话全部诉求申请安全/人工协调；仅请求不等于接管')
    elif 'product_knowledge' in kinds:
        add('human_input_request','product_support','后台核实型号规格，保持AI持有会话；客户拒绝接管：'+str(ctx['refuses_handoff']))
    return ctx,actions

class LocalFacts:
    """Only explicitly supplied scope-bound fixture facts. Default is UNKNOWN."""
    def __init__(self,facts=()):self.facts=list(facts)
    def lookup(self,action,input_hash):
        valid=[]
        for f in self.facts:
            if f.get('input_hash')!=input_hash or f.get('kind')!=action['kind']:continue
            if not all(f.get(k) for k in ('source_url','version','quote','observed_at')):raise ValueError('Incomplete fact provenance')
            if f.get('authority') not in ('AUTHORIZED_FIXTURE','PUBLIC_GENERAL_KNOWLEDGE'):raise ValueError('Unapproved fact')
            valid.append(f)
        return dict(status='KNOWN' if valid else 'UNKNOWN',facts=valid,source_kind='LOCAL_FIXTURE_LOOKUP',external_query=False)

class ActionStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,input_hash TEXT NOT NULL,conversation_id TEXT NOT NULL,operation_id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(operation_id,status))')
            for op in ('UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_events_{op} BEFORE {op} ON events BEGIN SELECT RAISE(ABORT,'immutable'); END")
    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path,timeout=10)) as c:
            c.row_factory=sqlite3.Row
            with c:yield c
    def list(self,input_hash):
        with self.connect() as c:return [dict(r,payload=json.loads(r['payload'])) for r in c.execute('SELECT * FROM events WHERE input_hash=? ORDER BY rowid',(input_hash,))]
    def execute(self,state,input_hash,*,facts=None):
        facts=facts or LocalFacts();ctx,actions=plan(state)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            def record(action,status,payload,operation):
                c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),input_hash,state.conversation_id,operation,action['kind'],status,json.dumps(payload,ensure_ascii=False),now()))
            for a in actions:
                op=digest(dict(input_hash=input_hash,action=a,version=VERSION))
                if c.execute('SELECT 1 FROM events WHERE operation_id=?',(op,)).fetchone():continue
                record(a,'requested',dict(action=a,context=ctx,local_only=True),op)
                if a['kind'].endswith('_lookup'):
                    try:result=facts.lookup(a,input_hash)
                    except Exception as exc:
                        record(a,'failed',dict(error=type(exc).__name__,local_only=True),op);continue
                    record(a,'executed',dict(result=result,local_only=True,external_execution=False),op)
                    if a['kind']=='logistics_lookup' and result['status']=='UNKNOWN':
                        follow=dict(kind='logistics_followup',owner='logistics',question='本地无可用轨迹，内部跟进待核实；没有承运商联系',priority=a['priority'])
                        record(follow,'created',dict(action=follow,context=ctx,local_only=True,external_execution=False),op+'followup')
                else:record(a,'handoff_pending' if a['kind']=='handoff_request' else 'created',dict(action=a,context=ctx,local_only=True,external_execution=False),op)
        return dict(context=ctx,events=self.list(input_hash),version=VERSION,identity='LOCAL_ACTIONS_NOT_EXTERNAL_EXECUTION')

def candidate_messages(email,runtime,experiment='E1'):
    from src.application.p5b2_prompt import messages
    if experiment not in ('E1','E2','E3'):raise ValueError('Unknown experiment')
    original=messages(email)
    # Preserve B2 system prompt and output contract. The extra system block is versioned.
    extra='Runtime receipts are trusted local events. created = internal task only; handoff_pending is not a human connected. Never claim carrier contact, refund, booking or attachment receipt without matching executed evidence. General connector knowledge must be separated from model-specific specifications. Respect latest preferences and all issues. Reply in the latest customer language.'
    payload=dict(customer_context=runtime['context'],action_receipts=runtime['events'])
    if experiment in ('E2','E3'):
        extra+=' Use only provenance-bearing facts in local lookup results, and keep UNKNOWN. Customer reports and assistant history are not merchant evidence. Installation scheduling is not parcel delivery.'
    if experiment=='E3':
        extra+=' Return every schema field on every issue. Be concise and natural; no mechanical restatement or technical reproduction jargon. Ordinary lamp faults need proportionate advice. Conditional return/exception options are allowed; never guarantee approval. Be active with the actual pending tasks, not repetitive disclaimers.'
    return [original[0],('system',extra+'\n'+json.dumps(payload,ensure_ascii=False)),*original[1:]]

def runnable(model,store,experiment='E1'):
    """Actual LangChain composition, caller must separately authorize a paid model."""
    from langchain_core.runnables import RunnableLambda
    def prepare(data):
        email,state=data['email'],data['state']
        runtime=store.execute(state,email.input_hash)
        return candidate_messages(email,runtime,experiment)
    return RunnableLambda(prepare) | model

def dispatch_disabled(*args,**kwargs):
    raise PermissionError('LIVE_DISPATCH_DISABLED: new immutable budget and authorization required')
