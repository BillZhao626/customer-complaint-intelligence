"""Local internal requests, immutable events, and scoped simulated knowledge input.

These records prove local work only. They never contact a merchant or carrier.
"""
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from pydantic import BaseModel, ConfigDict
from src.domain.contracts import digest
from src.application.product_workflow import Conflict, timestamp
from src.application.service_triage import explicit_human_request

VERSION='p5b3-local-actions-1'

class CustomerContext(BaseModel):
    model_config=ConfigDict(extra='forbid')
    input_hash: str
    current_request: str
    customer_history: str
    known_identifiers: list[str]
    existing_material_reported: bool
    wants_human: bool
    refuses_human: bool

class ActionDecision(BaseModel):
    kind: str
    owner: str
    priority: str
    question: str
    source_quote: str

class ActionResult(BaseModel):
    task_id: str
    event_id: str
    input_hash: str
    decision: ActionDecision
    status: str='PENDING'
    external_contact: bool=False
    actual_takeover: bool=False

def context(email):
    current=email.body.rsplit('[customer · current message]\n',1)[-1]
    # Exclude assistant text from rule decisions, while preserving it in model history.
    history=re.sub(r'\[assistant[^\]]*\][\s\S]*?(?=\[customer|$)','',email.body)
    return CustomerContext(input_hash=email.input_hash,current_request=current,customer_history=history,
        known_identifiers=re.findall(r'\b[A-Z][A-Z0-9]*-[A-Z0-9-]+\b',history),
        existing_material_reported=bool(re.search(r'照片|photos?|pictures?',history,re.I)),
        wants_human=explicit_human_request(current),
        refuses_human=bool(re.search(r'(?:不用|不想|不要|不需要).{0,6}人工|don.t transfer|no human',current,re.I)))

def decide(ctx, *, has_known_answer=False):
    text=ctx.customer_history; current=ctx.current_request
    out=[]
    def add(kind,owner,question,pattern):
        hit=re.search(pattern,text,re.I)
        out.append(ActionDecision(kind=kind,owner=owner,question=question,
            priority='high' if re.search(r'明天|次日|tomorrow|摔|火花|冒烟|受伤|紧急',text,re.I) else 'normal',
            source_quote=hit.group() if hit else current[:160]))
    if ctx.wants_human: add('handoff_request','customer_support','直接请求人工接管并携带现有上下文；无需先补齐投诉详情',r'人工|human|agent')
    if not has_known_answer and not ctx.wants_human and re.search(r'C200|接口|兼容|规格|支持.{0,8}(?:吗|么)|compatible|specification',text,re.I):
        add('knowledge_request','product_support','仅核实客户所述型号、接口/兼容能力及使用目标；提供有版本的有效规格依据。客户原问：'+current[:220],r'C200|接口|兼容|规格|compatible')
    if re.search(r'物流|快递|揽收|包裹|配送|签收|送达|tracking|parcel|courier|delivery|delivered',text,re.I):
        add('logistics_followup','logistics','核对订单的出库、交接、轨迹和当前配送诉求；有期限时核实加急可行性，不保证日期。客户原问：'+current[:220],r'物流|快递|包裹|tracking|parcel|delivery|delivered')
    if re.search(r'售后|坏|破|裂|漏|少了|缺|不亮|退款|退货|换货|维修|运费|邮费|断音|锁扣|火花|冒烟|refund|return|broken|missing|damaged',text,re.I):
        add('aftersales_followup','aftersales','核实所述故障/缺件、适用处理资格与费用；沿用已有资料，尊重退修偏好；有期限时联合物流核实可行时间。客户原问：'+current[:220],r'售后|坏|破|裂|缺|退款|退货|维修|锁扣|refund|return|broken|missing')
    if re.search(r'预约|安装|取件|收费|收据|发票|扣款|invoice|charged|appointment|collection',text,re.I):
        add('service_followup','customer_support','协调服务/账务责任方核对客户所有未决事项与最新时间限制，核实后再确认，不创建实际预约或退款。客户原问：'+current[:220],r'预约|安装|收费|发票|扣款|invoice|charged|appointment|collection')
    return out

class TaskJournal:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY,input_hash TEXT NOT NULL,decision TEXT NOT NULL, UNIQUE(input_hash,decision))')
            c.execute('CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(task_id),kind TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,operation_id TEXT UNIQUE NOT NULL)')
            for table in ('tasks','events'):
                for op in ('UPDATE','DELETE'):
                    c.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable action evidence'); END")
    def connect(self):
        from contextlib import contextmanager
        @contextmanager
        def conn():
            with closing(sqlite3.connect(self.path,timeout=10)) as c:
                c.row_factory=sqlite3.Row
                c.execute('PRAGMA foreign_keys=ON')
                with c: yield c
        return conn()
    def prepare(self,email,*,has_known_answer=False):
        ctx=context(email)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            for decision in decide(ctx,has_known_answer=has_known_answer):
                data=json.dumps(decision.model_dump(),ensure_ascii=False,sort_keys=True)
                if c.execute('SELECT 1 FROM tasks WHERE input_hash=? AND decision=?',(email.input_hash,data)).fetchone():continue
                task_id,event_id=str(uuid4()),str(uuid4())
                c.execute('INSERT INTO tasks VALUES(?,?,?)',(task_id,email.input_hash,data))
                c.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(event_id,task_id,'task_created',json.dumps(dict(status='PENDING',local_only=True,version=VERSION)),timestamp(),'create:'+task_id))
        return ctx,self.list(email.input_hash)
    def list(self,input_hash):
        with self.connect() as c:
            rows=[]
            for t in c.execute('SELECT * FROM tasks WHERE input_hash=? ORDER BY task_id',(input_hash,)):
                ev=[dict(e,payload=json.loads(e['payload'])) for e in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY rowid',(t['task_id'],))]
                result=ActionResult(task_id=t['task_id'],event_id=ev[0]['event_id'],input_hash=input_hash,decision=ActionDecision.model_validate_json(t['decision'])).model_dump()
                result.update(events=ev,status='KNOWLEDGE_SUPPLIED_SIMULATION' if any(e['kind']=='knowledge_supplied' for e in ev) else 'PENDING')
                rows.append(result)
            return rows
    def supply(self,task_id,*,body,source,operation_id):
        if not body.strip() or not source.strip() or len(body)>4000:raise ValueError('Scoped knowledge and source required')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            task=c.execute('SELECT * FROM tasks WHERE task_id=?',(task_id,)).fetchone()
            if not task or json.loads(task['decision'])['kind']!='knowledge_request':raise ValueError('Not a knowledge task')
            payload=json.dumps(dict(body=body,source=source,scope_input_hash=task['input_hash'],identity='demo_test',authority='INTERNAL_SIMULATED_KNOWLEDGE',merchant_approval=False),ensure_ascii=False,sort_keys=True)
            old=c.execute('SELECT task_id,payload FROM events WHERE operation_id=?',(operation_id,)).fetchone()
            if old and tuple(old)!=(task_id,payload):raise Conflict('Knowledge operation mismatch')
            if not old:c.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(str(uuid4()),task_id,'knowledge_supplied',payload,timestamp(),operation_id))
        return self.list(task['input_hash'])

def journal(store):return TaskJournal(store.path.with_name(store.path.stem+'-actions.sqlite3'))

def execute(store,case_id):
    case=store.get(case_id)
    tasks=journal(store).list(case['run'].input_hash)
    if any(t['decision']['kind']=='handoff_request' for t in tasks) and not any(e['action']=='request_handoff' for e in case['events']):
        store.act(case_id,'request_handoff',expected_revision=case['revision'],actor='p5b3_rule',actor_type='demo_test',reason='客户明确请求；本地待办已建立，尚未接管',operation_id='b3-handoff:'+case_id)
    return tasks
