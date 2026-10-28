"""Compatible email thread slice: immutable links beside the existing P4 DB.

Only saved simulated receipts count as outgoing messages. Context is explicit
data for an authored fixture/unknown probe, never a live model conversation.
"""
import json
import sqlite3
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import Conflict, timestamp
from src.application.copilot_demo import CopilotFake, SCENARIOS, FOLLOWUP, FOLLOWUP_SUBJECT, example
from src.application.v31_demo import pipeline_probe, span
from src.domain.contracts import EmailInput, digest
from src.infrastructure.repository import Repository


def message(role, body, subject, at, case, source):
    result = dict(role=role, body=body, subject=subject, at=at, case_id=case['case_id'],
                  issue_ids=[i['issue_id'] for i in (case['analysis'] or {}).get('issues', [])], source=source)
    return dict(result, hash=digest(result))


def assemble_context(messages, subject, body):
    """Stable role-marked text, identity-bound in the analyzer configuration."""
    history = '\n\n'.join(f"[{m['role']} · {m['at']} · {m['source']}]\n{m['subject']}\n{m['body']}" for m in messages)
    return history + f'\n\n[customer · current message]\n{subject}\n{body}'


class MailThreads:
    def __init__(self, store):
        self.store = store
        self.path = store.path.with_name(store.path.stem + '-threads.sqlite3')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = c.execute('PRAGMA user_version').fetchone()[0]
            # v0 with this exact table is the initial P4.5 development layout.
            # No unrelated database is initialized or silently migrated here.
            if version not in (0, 1) or tables not in (set(), {'thread_links'}):
                raise Conflict('不是兼容的独立邮件线程库；未执行迁移')
            c.execute('''CREATE TABLE IF NOT EXISTS thread_links (
                child_id TEXT PRIMARY KEY, parent_id TEXT UNIQUE NOT NULL,
                context_json TEXT NOT NULL, context_hash TEXT NOT NULL,
                current_json TEXT NOT NULL, current_hash TEXT NOT NULL,
                parent_receipt_hash TEXT NOT NULL, created_at TEXT NOT NULL)''')
            for action in ('UPDATE', 'DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_links_{action.lower()} BEFORE {action} ON thread_links BEGIN SELECT RAISE(ABORT,'thread messages immutable'); END")
            c.execute('PRAGMA user_version=1')

    def connect(self):
        from contextlib import closing, contextmanager
        @contextmanager
        def connection():
            with closing(sqlite3.connect(self.path, timeout=10)) as c:
                c.row_factory = sqlite3.Row
                with c:
                    yield c
        return connection()

    def link(self, case_id):
        with self.connect() as c:
            row = c.execute('SELECT * FROM thread_links WHERE child_id=?', (case_id,)).fetchone()
        if row:
            row = dict(row)
            for field in ('context', 'current'):
                row[field] = json.loads(row.pop(field + '_json'))
                if digest(row[field]) != row[field + '_hash']:
                    raise Conflict('邮件上下文校验失败')
            for m in row['context']:
                if digest({k: v for k, v in m.items() if k != 'hash'}) != m['hash']:
                    raise Conflict('历史消息身份校验失败')
            parent = self.store.get(row['parent_id'])
            child = self.store.get(case_id)
            expected_body = assemble_context(row['context'], **row['current'])
            if (not parent or not child or digest(parent['receipt']) != row['parent_receipt_hash']
                    or child['run'].config.parameters.get('context_hash') != row['context_hash']
                    or child['run'].email.body != expected_body):
                raise Conflict('邮件关联与原始分析身份不一致')
        return row

    def messages(self, case_id):
        case = self.store.get(case_id)
        if not case:
            raise Conflict('案例不存在')
        link = self.link(case_id)
        current = link['current'] if link else dict(body=case['run'].email.body, subject=case['run'].email.subject)
        result = list(link['context']) if link else []
        result.append(message('customer', current['body'], current['subject'], case['created_at'], case, case['source_kind']))
        if case['receipt']:
            receipt = case['receipt']
            result.append(message('assistant_simulation', receipt['body'], '模拟客服回复', receipt['created_at'], case, 'simulation_only'))
        return result

    def child(self, parent_id):
        with self.connect() as c:
            row = c.execute('SELECT child_id FROM thread_links WHERE parent_id=?', (parent_id,)).fetchone()
        return row[0] if row else None

    def follow_up(self, parent_id, subject, body):
        parent = self.store.get(parent_id)
        if not parent or parent['state'] != 'simulated_sent' or not parent['receipt']:
            raise Conflict('请先完成上一封回复的审核与模拟发送')
        if parent['quality']['status'] == 'blocked':
            raise Conflict('分析阻断不能通过新邮件绕过')
        new_input = EmailInput(email_id='follow-up', subject=subject, body=body)
        current = dict(subject=new_input.subject, body=new_input.body)
        existing = self.child(parent_id)
        if existing:
            if self.link(existing)['current'] != current:
                raise Conflict('此邮件已有后续消息，请打开后续案例继续处理')
            return self.store.get(existing)
        messages = self.messages(parent_id)
        context_hash = digest(messages)
        email = EmailInput(email_id='thread-' + digest(dict(parent=parent_id, **current))[:24], subject=subject,
                           body=assemble_context(messages, subject, body))
        initial, data = example(SCENARIOS[0])
        is_authored = (parent['source_kind'] == 'offline_fake'
                      and parent['run'].email == initial and body == FOLLOWUP and subject == FOLLOWUP_SUBJECT)
        scenario = SCENARIOS[0] if is_authored else SCENARIOS[6]
        if is_authored:
            # Current-turn evidence spans bind to the assembled input, not an
            # unrelated old message. Known facts remain customer-reported.
            ev = span(email, body)
            data['issues'][0].update(evidence=[ev], urgency_evidence=[ev],
                customer_requests=['核实 DemoCam C200 有线连接能力'],
                missing_evidence=['商家提供的 DemoCam C200 官方连接规格；型号仍为客户提供'])
            data.update(summary='新增事实：客户提供型号 DemoCam C200。功能仍待官方规格核实；咨询尚未解决。',
                suggested_reply='Thank you for providing the model, DemoCam C200. The model name alone does not establish wired connection support. The official connection specifications for this model are still needed to confirm that capability. There is no verified specification available in this demo, so I cannot confirm support or advise purchasing an adapter.')
        else:
            data = pipeline_probe(email).model_dump()
        repository = Repository(self.store.path.with_name(self.store.path.stem + '-analysis.sqlite3'))
        analyzer = CopilotFake(email, scenario, context_hash=context_hash, data=data)
        case = ProductAnalysis(AnalysisService(repository, analyzer), self.store).submit(email)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing = c.execute('SELECT child_id,current_hash FROM thread_links WHERE parent_id=?', (parent_id,)).fetchone()
            if existing:
                if existing['current_hash'] != digest(current):
                    raise Conflict('后续消息已由另一操作保存；当前分析保留，未覆盖线程')
                return self.store.get(existing['child_id'])
            c.execute('INSERT INTO thread_links VALUES(?,?,?,?,?,?,?,?)',
                      (case['case_id'], parent_id, json.dumps(messages, ensure_ascii=False), context_hash,
                       json.dumps(current, ensure_ascii=False), digest(current), digest(parent['receipt']), timestamp()))
        return case
