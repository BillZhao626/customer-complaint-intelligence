"""New explicit counterexamples. Candidate profile is offline and is not Gold."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from src.application.urgency_context_v1 import PROFILE,signals,bare_help
from src.domain.analysis_v31 import AnalysisV31
from src.domain.analysis_v31_context import ContextAnalysisV31,wire_schema,stored_context_analysis
from src.domain.contracts import EmailInput,digest
from src.application.p39_v2 import ContextOfflineService,require_comparison_approval,system,COMMON
from src.application.v31_demo import ReplayV31
from src.infrastructure.repository import Repository
from src.infrastructure.dashboard_sources import ReadOnlyRepository
from src.infrastructure.p39_envelope import P39Envelope
from src.infrastructure.context_repository import ContextRepository,ReadOnlyContextRepository
from tests.test_p38 import one


def fixture(body,urgency,basis,risk='none'):
    email,data=one(body,urgency,risk,basis,'health or safety issue' if risk in ('minor','severe') else 'none')
    if any('\u4e00'<=c<='\u9fff' for c in body):
        data.update(reply_language='zh',suggested_reply='感谢说明，请提供需要补充的信息以便核查。')
    return email,data


CASES=[
 ('bare_en','I need help. Please contact me.','medium','general_help','none'),
 ('bare_zh','我需要帮助。请联系我。','medium','general_help','none'),
 ('camera','Does this camera support a wired connection? Nothing is broken.','low','other','none'),
 ('watch','Can this watch show two time zones?','low','other','none'),
 ('printer_zh','这台打印机支持双面打印吗？','low','other','none'),
 ('hours_en','What time does the branch close on Sundays?','low','other','none'),
 ('hours_zh','请问周日几点关门？','low','other','none'),
 ('fault','My desk lamp stopped working. There is no heat, smoke or smell.','low','other','none'),
 ('fault_zh','我的咖啡机不能启动，没有发热或异味。','medium','other','none'),
 ('urgent','Please process my repair request ASAP.','high','explicit_urgent','none'),
 ('urgent_zh','请尽快处理维修请求。','high','explicit_urgent','none'),
 ('negated','Do not treat this as ASAP. What is the display size?','low','other','none'),
 ('quoted','A forwarded notice says "ASAP". I only ask for the opening hours.','low','other','none'),
 ('quoted_zh','转发标题写着“尽快处理”。我只是想问营业时间。','low','other','none'),
 ('relaxed','No rush. What is the capacity of this kettle?','low','explicit_relaxed','none'),
 ('relaxed_zh','不着急，方便时告诉我尺寸就好。','low','explicit_relaxed','none'),
 ('repeated','Three callbacks were promised and none arrived.','medium','repeated_failure','none'),
 ('repeated_zh','多次承诺回电但一直未兑现。','medium','repeated_failure','none'),
 ('deadline','They missed the promised reply twice. A response before court closes today is essential.','high','repeated_failure','none'),
 ('repeat_relaxed','My appointment was cancelled twice. No rush.','low','repeated_failure','none'),
 ('calm_risk','I am calm. The battery is swollen and smoking. No one was injured.','high','safety','severe'),
 ('calm_risk_zh','我不着急。电池正在膨胀并冒烟，目前无人受伤。','high','safety','severe'),
 ('conflict','Please deal with it ASAP, but no rush. I cannot say which request is current.','unknown','unknown','none'),
 ('insufficient','Something happened, but I cannot describe the item or the problem.','unknown','unknown','unknown'),
 ('contrast','I did not ask for ASAP, but please process it as soon as possible.','high','explicit_urgent','none'),
 ('hypothetical','The manual says if sparks appear near the socket, stop. No such event happened.','low','other','none'),
 ('no_risk_zh','插座没有冒火花，我只询问插头规格。','low','other','none'),
 ('repeat_resolved','My appointment was cancelled twice but it is now resolved.','low','other','none'),
]


class UrgencyContextTests(unittest.TestCase):
    def test_multilingual_counterexamples(self):
        for name,body,u,basis,risk in CASES:
            with self.subTest(name=name):
                e,d=fixture(body,u,basis,risk);v=ContextAnalysisV31.model_validate(d).validate_input(e)
                self.assertEqual(v.urgency,u);self.assertEqual(v.issues[0].urgency,u)

    def test_source_schema_field_bounds_and_legacy_behavior_preserved(self):
        self.assertEqual(digest(wire_schema()),digest(AnalysisV31.model_json_schema()))
        def expand(schema):
            defs=schema.get('$defs',{})
            def walk(n):
                if isinstance(n,list):return [walk(x) for x in n]
                if not isinstance(n,dict):return n
                if '$ref' in n:return walk(defs[n['$ref'].split('/')[-1]])
                return {k:walk(v) for k,v in n.items() if k not in ('title','$defs')}
            return walk(schema)
        self.assertEqual(expand(ContextAnalysisV31.model_json_schema()),expand(AnalysisV31.model_json_schema()))
        self.assertEqual(set(ContextAnalysisV31.model_fields),set(AnalysisV31.model_fields))
        e,d=fixture('A forwarded note says "ASAP". What are the opening hours?','low','other')
        with self.assertRaisesRegex(ValueError,'Email urgency contradicts explicit policy anchor'):AnalysisV31.model_validate(d).validate_input(e)
        ContextAnalysisV31.model_validate(d).validate_input(e)
        d['issues']=[]
        with self.assertRaises(ValueError):ContextAnalysisV31.model_validate(d)

    def test_general_help_not_a_generic_question_or_politeness_label(self):
        for body in ('Does this scanner work with a tablet?','Please tell me the opening hours.','我的平板不能开机，请帮助我。'):
            self.assertFalse(bare_help(body))
            e,d=fixture(body,'medium','general_help')
            with self.assertRaisesRegex(ValueError,'undifferentiated'):ContextAnalysisV31.model_validate(d).validate_input(e)

    def test_current_failure_not_repaired_or_reinterpreted(self):
        e,d=fixture('Can this thermostat display Fahrenheit? Nothing is broken.','low','general_help')
        raw=copy.deepcopy(d)
        with self.assertRaises(ValueError):ContextAnalysisV31.model_validate(d).validate_input(e)
        self.assertEqual(d,raw)

    def test_quoted_or_negated_urgent_cannot_launder_evidence(self):
        for body,quote in [('The old note says "ASAP". What is the weight?','ASAP'),('Do not process this ASAP. What is the weight?','Do not process this ASAP.')]:
            e,d=fixture(body,'high','explicit_urgent');start=body.index(quote)
            d['issues'][0]['urgency_evidence']=[dict(field='body',start=start,end=start+len(quote),quote=quote)]
            with self.assertRaisesRegex(ValueError,'active, nonquoted'):ContextAnalysisV31.model_validate(d).validate_input(e)

    def test_override_must_be_in_evidence_not_only_elsewhere(self):
        body='They missed the promised reply twice. A response before closing today is essential.'
        e,d=fixture(body,'high','repeated_failure');quote=body.split('. ')[0]
        d['issues'][0]['urgency_evidence']=[dict(field='body',start=0,end=len(quote),quote=quote)]
        with self.assertRaisesRegex(ValueError,'independent context'):ContextAnalysisV31.model_validate(d).validate_input(e)

    def test_all_exact_evidence_checks_remain(self):
        e,d=fixture('Please handle my booking ASAP.','high','explicit_urgent')
        for key in ('evidence','urgency_evidence'):
            bad=copy.deepcopy(d);bad['issues'][0][key][0]['quote']='invented'
            with self.assertRaises(ValueError):ContextAnalysisV31.model_validate(bad).validate_input(e)

    def test_severe_safety_never_downgraded_by_calm_or_unknown(self):
        body='No rush. The battery is swollen and smoking. No one was injured.'
        for u,risk,basis in [('low','severe','safety'),('medium','none','other'),('unknown','unknown','unknown')]:
            e,d=fixture(body,u,basis,risk)
            with self.assertRaises(ValueError):ContextAnalysisV31.model_validate(d).validate_input(e)

    def test_basis_still_requires_actual_facts(self):
        for basis in ('explicit_urgent','explicit_relaxed','repeated_failure','safety','unknown'):
            e,d=fixture('Does this monitor have a second input?','low',basis)
            with self.subTest(basis=basis),self.assertRaises(ValueError):ContextAnalysisV31.model_validate(d).validate_input(e)

    def test_original_non_urgency_guards_not_removed(self):
        e,d=fixture('Does this monitor have a second input?','low','other')
        for change in ({'risk_rationale':''},{'extraction_basis':'v2_projection'},{'handling_priority':1,'priority_rationale':None},
                       {'responsibility':'verified'},{'customer_importance':'primary','importance_evidence':[]}):
            bad=copy.deepcopy(d);bad['issues'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):ContextAnalysisV31.model_validate(bad).validate_input(e)

    def test_shared_prompt_and_human_gate(self):
        self.assertIn(COMMON,system('A'));self.assertTrue(system('B').startswith(system('A')))
        self.assertNotIn('Elm Store',system('A'));self.assertNotIn('p25-product',system('B'))
        with self.assertRaises(PermissionError):require_comparison_approval({'manifest_hash':'fixture'},None)
        class Live:
            backend='deepseek_live'
        with self.assertRaises(PermissionError):ContextOfflineService(None,Live())

    def test_offline_service_raw_sqlite_reload_and_profile_identity(self):
        e,d=fixture('A forwarded note says "ASAP". What are the opening hours?','low','other')
        with tempfile.TemporaryDirectory() as td:
            a=ReplayV31({e.input_hash:d});a.config=a.config.model_copy(update={'parameters':dict(a.config.parameters,urgency_validation_profile=PROFILE)})
            path=Path(td)/'runs.sqlite3';s=ContextOfflineService(ContextRepository(path),a);r=s.analyze(e)
            self.assertEqual(r.status,'succeeded');self.assertEqual(s.analyze(e).run_id,r.run_id)
            reread=ReadOnlyContextRepository(path).get(r.run_id);self.assertEqual(stored_context_analysis(reread).urgency,'low')
            with self.assertRaises(ValueError):
                from src.domain.analysis_v31 import stored_analysis
                stored_analysis(reread)


def prior_fixture(path):
    with closing(sqlite3.connect(path)) as c,c:
        c.executescript('CREATE TABLE policy(manifest TEXT,halted TEXT);CREATE TABLE reservations(id INTEGER PRIMARY KEY,run_id TEXT,attempt_no INT,input_hash TEXT,reserved_cny REAL,completed INT);CREATE TABLE lease(run_id TEXT)')
        c.execute('INSERT INTO policy VALUES(?,?)',(json.dumps(dict(authorization=dict(requests=72,cny=10),experiment=dict(manifest_hash='fixture-parent'))),'failure_requires_review'))
        c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,completed) VALUES(?,?,?,?,?)',('original',1,'fixture-input',.04,1))


class EnvelopeTests(unittest.TestCase):
    def build(self,td):
        root=Path(td);old=root/'old.sqlite3';prior_fixture(old)
        m=dict(manifest_hash='fixture-new',parent_v1_manifest_hash='fixture-parent')
        req=dict(user_evidence='OFFLINE FIXTURE ONLY',user_evidence_sha256=sha256(b'OFFLINE FIXTURE ONLY').hexdigest(),combined_planned_requests=65,explicit_extra_allowance=1,offline_test_fixture=True)
        b=P39Envelope.create(root/'new.sqlite3',old,m,req)
        review=dict(status='researcher_approved_comparison_change',reviewer='OFFLINE FIXTURE',manifest_hash='fixture-new',user_approval_evidence='SIMULATED OFFLINE TEST')
        return b,old,review

    def test_inherited_request_cost_exclusive_file_and_pending_approval(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td);before=sha256(old.read_bytes()).hexdigest()
            self.assertEqual(b.summary()['shared_requests'],1);self.assertEqual(b.summary()['shared_reserved_upper_cny'],.04)
            with self.assertRaises(PermissionError):b.reserve('new',.04)
            self.assertEqual(sha256(old.read_bytes()).hexdigest(),before)
            self.assertFalse(b.summary()['comparison_approved'])

    def test_concurrent_restart_and_smoke_gate_do_not_spend_extra7(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td);b.approve(review);b.reserve('smoke0',.04)
            restart=P39Envelope(b.path)
            with self.assertRaises(PermissionError):restart.reserve('concurrent',.04)
            b.finish('smoke0')
            for i in range(1,8):b.reserve('smoke'+str(i),.04);b.finish('smoke'+str(i))
            self.assertEqual(b.summary()['shared_requests'],9)
            with self.assertRaises(PermissionError):b.reserve('remaining',.04)
            self.assertEqual(b.summary()['new_reserved_requests'],8)

    def test_currency_cap_and_original_ledger_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td);b.approve(review)
            with self.assertRaises(PermissionError):b.reserve('over-budget',9.99)
            with closing(sqlite3.connect(old)) as c,c:c.execute('UPDATE reservations SET reserved_cny=0')
            with self.assertRaises(PermissionError):b.reserve('tampered',.01)

    def test_forged_approval_binding_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td);review['manifest_hash']='different'
            with self.assertRaises(PermissionError):b.approve(review)

    def test_65_plan_ceiling_keeps_remaining7_unused_even_after_fake_gates(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td);b.approve(review)
            # Explicit temporary fixture for a future validated smoke importer; no real approval.
            with b.connection() as c:c.execute('INSERT INTO approvals VALUES(?,?)',('smoke','OFFLINE TEST FIXTURE ONLY'))
            for n in range(64):b.reserve('planned'+str(n),.04);b.finish('planned'+str(n))
            self.assertEqual(b.summary()['shared_requests'],65)
            with self.assertRaises(PermissionError):b.reserve('unapproved-extra',.04)
            self.assertAlmostEqual(b.summary()['shared_reserved_upper_cny'],.04*65)

    def test_production_allowance_cannot_be_cloned_to_another_path(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td)
            with b.connection() as c:
                m=json.loads(c.execute('SELECT manifest FROM root').fetchone()[0]);req=json.loads(c.execute('SELECT request FROM root').fetchone()[0])
            req['offline_test_fixture']=False
            target=Path(td)/'clone.sqlite3'
            with self.assertRaises(PermissionError):P39Envelope.create(target,old,m,req)
            self.assertFalse(target.exists())

    def test_offline_candidate_revision_is_append_only_and_preserves_spend(self):
        with tempfile.TemporaryDirectory() as td:
            b,old,review=self.build(td)
            with b.connection() as c:
                original=c.execute('SELECT manifest FROM root').fetchone()[0];m=json.loads(original);req=json.loads(c.execute('SELECT request FROM root').fetchone()[0])
            m['manifest_hash']='fixture-revision';b.register_candidate(m,req)
            self.assertEqual(b.summary()['shared_requests'],1);self.assertEqual(b.summary()['current_candidate_manifest_hash'],'fixture-revision')
            with b.connection() as c:self.assertEqual(c.execute('SELECT manifest FROM root').fetchone()[0],original)
            with self.assertRaises(PermissionError):b.approve(review)
            review['manifest_hash']='fixture-revision';b.approve(review)
            with self.assertRaises(PermissionError):b.register_candidate(m,req)
