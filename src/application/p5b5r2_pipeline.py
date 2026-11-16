"""R2 corrections to existing local workflow; no external business executors."""
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from src.application.p5b5_state_v3 import ConversationState as Previous
from src.application.p5b5_pipeline import ActionStore as PreviousStore, LocalFacts, plan as previous_plan, now
from src.domain.contracts import digest

VERSION = 'p5b5r2-state-actions-1'

class ConversationState(Previous):
    def update(self,role,text):
        previous=list(self.identifiers)
        super().update(role,text)
        if role!='customer':return
        ids=re.findall(r'(?<![A-Za-z0-9-])(?:DEMO-[A-Z0-9-]+|[A-Z]{1,6}-[A-Z0-9-]+|[FLC]\d{2,})(?![A-Za-z0-9-])',text,re.I)
        # Remove malformed partial IDs inherited from Unicode word-boundary matching.
        old=[x for x in previous if not any(y.endswith(x) and y!=x for y in ids)]
        if re.search(r'写错|更正|号码不对|wrong (?:order|number)|correction',text,re.I) and ids:
            old=[x for x in old if re.fullmatch(r'[FLC]\d{2,}',x,re.I)]
        self.identifiers=list(dict.fromkeys(old+ids))

    def extract(self):
        ctx = super().extract()
        latest = ctx['latest_request']
        # Resolution/cancellation is customer state, never inferred from assistant text.
        for kind, pattern in [('aftersales', r'(?:售后|维修|退换货|耳机|台灯).{0,8}(?:已解决|解决了|不用处理|修好了)|不需要售后|(?:repair|aftersales).{0,12}(?:resolved|sorted)'),
                              ('logistics', r'(?:物流|包裹|快递).{0,8}(?:已解决|收到了|已收到)|parcel has arrived')]:
            active=True
            for m in self.messages:
                if m['role']!='customer':continue
                if re.search(pattern,m['text'],re.I):active=False
                elif re.search((r'重新.{0,5}(?:售后|维修)|又坏|坏了' if kind=='aftersales' else r'新包裹|另一个包裹|重新.{0,5}查物流'),m['text'],re.I):active=True
            if not active:
                ctx['issues'] = [i for i in ctx['issues'] if i['kind'] != kind]
        cancel=False
        for m in self.messages:
            if m['role']!='customer':continue
            if re.search(r'(?:我要|我想|请|帮我|现在|决定)(?:把)?取消.{0,8}(?:安装|预约)|(?:取消安装|取消预约)[，,。 ]*(?:不要|不用|不再)|(?:please |I want to |I would like to )cancel.{0,12}(?:installation|appointment)',m['text'],re.I):cancel=True
            elif re.search(r'重新.{0,6}(?:安装|预约)|恢复安装|rebook|reschedule again',m['text'],re.I):cancel=False
        ctx['installation_cancelled'] = cancel
        ctx['deadline_negated'] = bool(re.search(r'不是.{0,5}(?:今天|明天).{0,5}(?:一定|必须).{0,3}到|not asking.{0,15}(?:arrive|today)', latest, re.I))
        ctx['source_messages']=[m for m in self.messages if m['role']=='customer']
        for i in ctx['issues']:
            i['issue_id'] = 'issue-' + i['kind']
        return ctx

def plan(state):
    ctx, actions = previous_plan(state)
    ctx = state.extract()
    allowed = {i['kind'] for i in ctx['issues']}
    mapping = {'knowledge_lookup':'product_knowledge','human_input_request':'product_knowledge',
        'logistics_lookup':'logistics','installer_schedule_lookup':'installation','installation_request':'installation',
        'pickup_lookup':'pickup','invoice_request':'invoice','billing_request':'billing','aftersales_request':'aftersales'}
    actions = [a for a in actions if mapping.get(a['kind']) in allowed or a['kind']=='handoff_request' or (a['kind']=='aftersales_request' and 'safety' in allowed)]
    if ctx['installation_cancelled']:
        actions = [a for a in actions if a['kind'] not in ('installer_schedule_lookup','installation_request')]
        actions.append(dict(kind='installation_cancellation_request',owner='installation_service',question='客户取消安装；登记内部取消核实，外部预约未被修改',priority='normal'))
    for a in actions:
        kinds = [mapping[a['kind']]] if a['kind'] in mapping else sorted(allowed)
        if a['kind']=='aftersales_request' and 'safety' in allowed:kinds=list(set(kinds+['safety']))
        a['issue_ids'] = ['issue-'+k for k in kinds if k in allowed]
        a['customer_goal'] = ctx['latest_request']
        a['order_identifiers'] = ctx['identifiers']
    return ctx, actions

class ActionStore(PreviousStore):
    def execute(self, state, input_hash, *, facts=None):
        # Reuse immutable event storage and lookup contract; no historical migration.
        facts = facts or LocalFacts()
        ctx, actions = plan(state)
        from uuid import uuid4
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            def record(a,status,payload,op):
                c.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),input_hash,state.conversation_id,op,a['kind'],status,json.dumps(payload,ensure_ascii=False),now()))
            # Old requests remain auditable; this is a local revision, not external cancellation.
            old = c.execute("SELECT * FROM events WHERE conversation_id=? AND input_hash<>? AND status IN ('created','handoff_pending')",(state.conversation_id,input_hash)).fetchall()
            for row in old:
                p=json.loads(row['payload']);a=p['action']
                if p.get('context') != ctx:
                    record(a,'superseded',dict(previous_event_id=row['event_id'],replacement_input_hash=input_hash,local_only=True,external_execution=False),row['operation_id'])
            for a in actions:
                op=digest(dict(input_hash=input_hash,action=a,version=VERSION))
                if c.execute('SELECT 1 FROM events WHERE operation_id=?',(op,)).fetchone():continue
                payload=dict(action=a,context=ctx,local_only=True,external_execution=False)
                record(a,'requested',payload,op)
                if a['kind'].endswith('_lookup'):
                    try:result=facts.lookup(a,input_hash)
                    except Exception as exc:
                        record(a,'failed',dict(error=type(exc).__name__,local_only=True),op);continue
                    record(a,'executed',dict(result=result,action=a,context=ctx,local_only=True,external_execution=False),op)
                    if result['status']=='UNKNOWN' and a['kind'] in ('logistics_lookup','pickup_lookup'):
                        follow=dict(a,kind='logistics_followup' if a['kind']=='logistics_lookup' else 'pickup_followup',question='本地查询无可用结果，登记内部核实；尚未联系外部服务')
                        record(follow,'created',dict(payload,action=follow),op+'followup')
                else:record(a,'handoff_pending' if a['kind']=='handoff_request' else 'created',payload,op)
        return dict(context=ctx,events=self.list(input_hash),version=VERSION,identity='LOCAL_ACTIONS_NOT_EXTERNAL_EXECUTION')

class ConversationStore:
    """Append-only local customer/assistant state, replayed after process restart."""
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute('CREATE TABLE IF NOT EXISTS messages(sequence INTEGER PRIMARY KEY,conversation_id TEXT,role TEXT,text TEXT,operation_id TEXT UNIQUE)')
    def update(self,conversation_id,role,text,operation_id):
        if role not in ('customer','assistant'):raise ValueError('Invalid role')
        with closing(sqlite3.connect(self.path)) as c,c:
            old=c.execute('SELECT conversation_id,role,text FROM messages WHERE operation_id=?',(operation_id,)).fetchone()
            if old and old!=(conversation_id,role,text):raise ValueError('Operation identity conflict')
            c.execute('INSERT OR IGNORE INTO messages(conversation_id,role,text,operation_id) VALUES(?,?,?,?)',(conversation_id,role,text,operation_id))
        return self.load(conversation_id)
    def load(self,conversation_id):
        state=ConversationState(conversation_id)
        with closing(sqlite3.connect(self.path)) as c:
            for role,text in c.execute('SELECT role,text FROM messages WHERE conversation_id=? ORDER BY sequence',(conversation_id,)):state.update(role,text)
        return state

def messages(email,runtime,experiment='R1'):
    if experiment in ('UI-R3','UI-FOLLOWUP'):experiment='R3'
    from scripts.p5b5_e4 import messages as e4
    msgs=e4(email,runtime,'E4')
    extra='''
R2 correction (trusted receipts scoped to this exact input):
1. A question about repair OR exchange is not an outcome choice. Explain both pending routes and cost verification; do not choose for the customer.
2. A cracked/damaged lamp is NOT safe to power for diagnosis. Do not ask whether it can be powered or ask the customer to test it. Ask only for already-known safe evidence, or the damaged part if necessary, without handling/opening/testing. Ordinary undamaged lamp failure alone needs no emergency warning.
3. A negated delivery demand ('不是催今天一定到') does not mean '不急'. Use urgency_basis other unless independent affirmative urgency evidence exists. Do not classify product recurrence alone as repeated service failure.
4. When the customer changes/cancels a request, only current active issues should be advanced. Cancellation_request is a local pending request, never a cancelled external booking. Superseded events are historical, never current completed work.
5. Each created task includes issue_ids, customer_goal and order_identifiers. Mention concrete useful next steps and actual pending team action naturally, without exposing internal field names or JSON. Answer known lookup facts directly; UNKNOWN must stay unconfirmed. No future callback/contact promise.
6. For wet packaging with damaged lamp: recommend avoiding power if moisture could affect electrical parts. Do not demand opening the box or new photos. Safety language must agree with analysis risk/evidence; no guarantee of eligibility, schedule, fees or outcome.
'''
    if experiment in ('R2','R3','UI','FINAL'):
        extra+='''
R2 second-round correction based on actual R1 failures (same contract and policy):
- complaint_status current_unresolved REQUIRES at least one issue_kind complaint with resolution unresolved. If the text is purely an inquiry and you choose inquiry issues, use no_complaint instead; never contradict your own issue array. For tracking stalled on a page, complaint versus inquiry requires source evidence, not the negated deadline alone.
- Rain-soaked or damaged delivery WITHOUT timing failure is reason other, business_process delivery/logistics issue; do not label it delivery delay or infer a manufacturing cause. Use exact source quotes. Safe reply does not excuse contradictory analysis.
- A created local task is pending, NOT evidence a team is already working or will send a later message. Say 已登记…核实请求，具体…仍待确认. Remove promises 核实后会同步/收到后会说明/we will update/contact. Describe what the task asks to verify; do not promise external steps.
- For ordinary aftersales keep the answer short: a brief acknowledgment, useful options subject to verification, the matching pending request, and at most ONE missing item necessary now. Do not demand a model already known or a checklist of order + receipt + model + channel. Don't ask again for a deadline date the customer already gave. Never mechanically repeat every reported detail.
- Never ask the customer to move a wet/damaged electrical box or open damaged parts for checking. Give no-power/no-test precautions and use safe existing evidence. A multi-issue drawer hazard requires advice to stop using the affected furniture, not bicycle advice.
'''
    if experiment in ('R3','FINAL'):
        # Exact, deterministic input evidence hints address the observed partial
        # safety-span failure; they are not Gold labels or repaired predictions.
        from src.application.product_quality import load_failure
        source_hints=[]
        for m in runtime['context'].get('source_messages',[]):
            if m['role']!='customer' or not load_failure(m['text']):continue
            quote=m['text'];start=email.body.find(quote)
            if start>=0:source_hints.append(dict(field='body',start=start,end=start+len(quote),quote=quote))
        extra+='''
R3 evidence construction: partial phrases like 锁扣突然打开 omit the load-bearing object, so they cannot establish the full safety anchor. When exact source spans below exist, use the full supplied CUSTOMER span on the severe/high issue, including on follow-up; never substitute an assistant summary. These are input offsets, not a model answer. Keep other issue evidence independently scoped.
Produce one valid JSON object. Every property name, including quote, must be double-quoted. No markdown, comments or bare keys. Keep structure concise and avoid unnecessary duplicate issues to reduce serialization errors.
'''+json.dumps(dict(exact_load_bearing_customer_spans=source_hints),ensure_ascii=False)
    return [('system',msgs[0][1]+extra),*msgs[1:]]
