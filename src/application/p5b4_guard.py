"""Opt-in replay guard. The incumbent validator and product policies are unchanged."""
from pathlib import Path
import re
import sqlite3
import json
from contextlib import closing
from src.application.reply_review import inspect_reply, BOUNDARY
from src.application.product_quality import inspect as product_inspect
from src.domain.contracts import digest

VERSION = 'p5b4-event-guard-1'
OWNERS = {'knowledge_request':'product_support', 'logistics_followup':'logistics',
          'aftersales_followup':'aftersales', 'service_followup':'customer_support',
          'handoff_request':'customer_support'}
SCOPE = {'knowledge_request':r'产品|规格|知识|接口|product|specification|knowledge',
         'logistics_followup':r'物流|配送|logistics|delivery',
         'aftersales_followup':r'售后|aftersales|after.sales',
         'service_followup':r'服务|账务|发票|service|billing',
         'handoff_request':r'人工|human|handoff'}

def receipts(path, input_hash):
    """Read durable event evidence; never trust model-supplied action_results."""
    if path is None:
        return []
    uri = Path(path).resolve().as_uri()+'?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT t.task_id,t.input_hash,t.decision,e.event_id,e.payload FROM tasks t JOIN events e USING(task_id) WHERE t.input_hash=? AND e.kind='task_created'", (input_hash,)).fetchall()
    result = []
    for row in rows:
        d, p = json.loads(row['decision']), json.loads(row['payload'])
        if d.get('owner') != OWNERS.get(d.get('kind')) or p.get('status') != 'PENDING' or p.get('local_only') is not True:
            continue
        result.append(dict(task_id=row['task_id'], event_id=row['event_id'], input_hash=row['input_hash'], decision=d, status='PENDING', external_execution=False))
    return result

def _clauses(text):
    start = 0
    for m in BOUNDARY.finditer(text):
        yield start, m.start(), text[start:m.start()]
        start = m.end()
    yield start, len(text), text[start:]

def _supported(clause, trusted):
    # Intentionally narrow: only internal recording, never processing or completion.
    record = re.search(r'(?:已|已经)(?:为您|将|把)?[^。！？;；，,]{0,32}记录|\b(?:we|i)\s+(?:have\s+)?(?:already\s+)?(?:logged|recorded)\b', clause, re.I)
    internal = re.search(r'内部|后台|internal|local', clause, re.I)
    pending = re.search(r'待核实|待处理|待确认|待接管|pending|awaiting', clause, re.I)
    terminal = re.search(r'已完成|已解决|已核实|已联系|已退款|已批准|已安排|已发送|已收到|approved|refunded|completed|resolved|sent|contacted|received|confirmed', clause, re.I)
    matches = [r for r in trusted if re.search(SCOPE[r['decision']['kind']], clause, re.I)]
    return bool(record and internal and pending and not terminal and matches), matches

def lexical(reply, trusted=(), *, event_guard=False):
    old = inspect_reply(reply)
    findings = []
    for f in old['findings']:
        g = dict(f)
        if event_guard and f['kind'] == 'executed_action':
            clause = next((c for a,b,c in _clauses(reply) if a <= f['start'] and f['end'] <= b), '')
            allowed, evidence = _supported(clause, trusted)
            if allowed:
                g.update(severity='review', reason='Durable local task creation supports internal pending record only; human wording review required.', receipt_ids=[r['event_id'] for r in evidence])
        findings.append(g)
    return findings

def inspect(email, data, *, structured_ok, journal_path=None, event_guard=False, safety_synonyms=False, attachment_guard=False):
    trusted = receipts(journal_path, email.input_hash)
    reply = data.get('suggested_reply', '')
    lexical_findings = lexical(reply, trusted, event_guard=event_guard)
    base = product_inspect(email, data, reply, accepted=structured_ok)
    original_lexical = inspect_reply(reply)['findings']
    findings = [dict(f) for f in base['findings'] if not any(f['code']==o['kind'] and f['quote']==o['quote'] and f['reason']==o['reason'] for o in original_lexical)]
    findings += [dict(code=f['kind'], severity=f['severity'], scope='reply', quote=f['quote'], reason=f['reason'], receipt_ids=f.get('receipt_ids', [])) for f in lexical_findings]
    if safety_synonyms:
        electrical = bool(re.search(r'电|火花|冒烟|electric|spark|smok', email.subject+'\n'+email.body, re.I))
        stop = bool(re.search(r'保持断电|保持总开关关闭|不要再触碰|勿触碰|切勿通电|keep.{0,12}unplugged|do not touch', reply, re.I))
        if electrical and stop:
            findings = [f for f in findings if f['code'] != 'missing_stop_use_advice']
    if attachment_guard:
        # Text-only replay fixture has no attachment manifest. A report is not receipt.
        for clause in re.split(r'[。！？;；\n.!?]', reply):
            m = re.search(r'(?:照片|图片|附件).{0,12}(?:已(?:经)?收到|已经接收)|(?:已(?:经)?收到).{0,12}(?:照片|图片|附件)|we.{0,12}(?:received|have).{0,20}(?:photos|pictures|attachments)|(?:photos|pictures|attachments).{0,15}(?:received|on file)', clause, re.I)
            if m and not re.search(r'未收到|没有收到|尚未|未能|not received|haven.t received|you (?:said|report)|您(?:说|提到|表示)', clause, re.I):
                findings.append(dict(code='attachment_receipt_without_manifest', severity='block', scope='reply', quote=m.group(), reason='Text-only fixture: customer report does not establish attachment receipt.'))
    for f in findings:
        f['finding_id'] = digest(f)
    return dict(version=VERSION, status='blocked' if any(f['severity']=='block' for f in findings) else 'review_required', findings=findings, receipts=trusted, human_approved=False, safety_review_required=base['safety_review_required'], semantic_status='SEMANTIC_PROVISIONAL')
