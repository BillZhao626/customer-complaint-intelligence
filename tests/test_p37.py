"""Scenario-independent offline regressions; no local research mail in fixtures."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.application.v3_demo import DEMO_EMAIL,demo_result,ReplayV3
from src.application.analysis_service import AnalysisService
from src.domain.analysis_v3 import AnalysisV3,stored_analysis,to_v2,from_v2
from src.domain.contracts import digest
from src.infrastructure.repository import Repository
from src.application.v3_remediation import derive,verify_derived,order_equal_ties,HANDLING_POLICY
from src.application.reply_review import inspect_reply,VERSION
from src.evaluation.semantic_review import build_review,validate_review,DIMENSIONS


def value(**updates):
    data=demo_result().model_dump()
    data.update(updates)
    return AnalysisV3.model_validate(data)


class SafeProjectionTests(unittest.TestCase):
    def test_uncertain_store_is_masked_only_in_new_policy(self):
        v=value(mentioned_store='Possible branch',store_verification='uncertain_mention')
        old=to_v2(v,'owner-operational-v1')[0]
        new,notes=to_v2(v,'owner-operational-v2-safe')
        self.assertEqual(old.store_location,'Possible branch');self.assertEqual(new.store_location,'unknown')
        self.assertEqual(v.mentioned_store,'Possible branch');self.assertTrue(any('masked' in n for n in notes))

    def test_reported_store_kept_but_not_called_verified(self):
        v=value(mentioned_store='Reported branch',store_verification='mentioned_only')
        new,notes=to_v2(v,'owner-operational-v2-safe')
        self.assertEqual(new.store_location,'Reported branch')
        self.assertTrue(any('never verified' in n for n in notes))

    def test_unclear_and_inferred_source_independent_of_route(self):
        for certainty,want in [('unclear','unclear'),('inferred','unclear'),('unknown','unknown'),('reported','product issue')]:
            data=demo_result().model_dump();data['issues']=data['issues'][:1];data['relations']=[]
            data['issues'][0]['attribution_certainty']=certainty
            data['issues'][0]['routing_team']='logistics'
            v=AnalysisV3.model_validate(data)
            self.assertEqual(to_v2(v,'owner-operational-v1')[0].source_attribution,'product issue')
            self.assertEqual(to_v2(v,'owner-operational-v2-safe')[0].source_attribution,want)

    def test_unknown_store_state_cannot_announce_named_store(self):
        v=value(mentioned_store='Unverified text',store_verification='unknown')
        self.assertEqual(to_v2(v,'customer-primary-v2-safe')[0].store_location,'unknown')

    def test_multiple_unranked_customer_domains_do_not_inherit_operational_source(self):
        data=demo_result().model_dump();data['relations']=[]
        for i in data['issues']:i.update(customer_importance='unspecified',importance_evidence=[],attribution_certainty='reported')
        v=AnalysisV3.model_validate(data)
        self.assertEqual(to_v2(v,'owner-operational-v1')[0].source_attribution,'product issue')
        self.assertEqual(to_v2(v,'owner-operational-v2-safe')[0].source_attribution,'unclear')
        data['issues'][0].update(customer_importance='primary',importance_evidence=demo_result().issues[0].importance_evidence)
        v=AnalysisV3.model_validate(data)
        self.assertEqual(to_v2(v,'owner-operational-v2-safe')[0].source_attribution,'product issue')

    def test_no_complaint_source_stays_none(self):
        data=demo_result().model_dump()
        data['complaint_status']='no_complaint'
        for i in data['issues']:i.update(issue_kind='inquiry',resolution='not_applicable',reason='none')
        v=AnalysisV3.model_validate(data)
        self.assertEqual(to_v2(v,'owner-operational-v2-safe')[0].source_attribution,'none')

    def test_size_fit_not_wrong_item_and_missing_primary_not_fabricated(self):
        data=demo_result().model_dump();data['issues'][0]['reason']='size/fit issue'
        v=AnalysisV3.model_validate(data)
        self.assertEqual(to_v2(v,'owner-operational-v2-safe')[0].complaint_reason,'other')
        self.assertEqual(to_v2(v,'customer-primary-v2-safe')[0].product_category,'unknown')

    def test_v2_origin_roundtrip_all_four_policies(self):
        from src.domain.contracts import AnalysisResult
        from tests.fixtures import VALID
        original=AnalysisResult.model_validate(VALID)
        for policy in ('customer-primary-v1','owner-operational-v1','customer-primary-v2-safe','owner-operational-v2-safe'):
            self.assertEqual(to_v2(from_v2(original),policy)[0],original)

    def test_original_defaults_and_contract_still_strict(self):
        v=demo_result();self.assertEqual(to_v2(v),to_v2(v,'customer-primary-v1'))
        with self.assertRaises(ValueError):to_v2(v,'not-approved')
        data=v.model_dump();data['issues'][0]['responsibility']='verified'
        with self.assertRaises(ValueError):AnalysisV3.model_validate(data)


class DerivedViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        data=demo_result().model_dump()
        for i in data['issues']:i['handling_priority']=1;i['attribution_certainty']='reported'
        self.original=AnalysisV3.model_validate(data)
        self.repo=Repository(self.root/'runs.sqlite3')
        self.run=AnalysisService(self.repo,ReplayV3({DEMO_EMAIL.input_hash:data})).analyze(DEMO_EMAIL)
    def tearDown(self):self.tmp.cleanup()

    def test_explicit_policy_resolves_equal_tie_without_changing_importance(self):
        v,changes,notes=order_equal_ties(self.original,HANDLING_POLICY)
        self.assertEqual([i.handling_priority for i in v.issues],[1,2])
        self.assertEqual([i.customer_importance for i in v.issues],['equal','equal'])
        self.assertEqual(v.relations,self.original.relations)
        self.assertTrue(changes)
        self.assertEqual([i.handling_priority for i in self.original.issues],[1,1])

    def test_no_policy_no_tie_breaker_and_unknown_policy_rejected(self):
        self.assertEqual(order_equal_ties(self.original)[0],self.original)
        with self.assertRaises(ValueError):order_equal_ties(self.original,'make-up-policy')

    def test_renamed_ids_and_reversed_array_have_same_business_order(self):
        data=self.original.model_dump();data['issues'].reverse();data['relations']=[]
        for n,i in enumerate(data['issues']):i['issue_id']=f'arbitrary-{n}'
        got=order_equal_ties(AnalysisV3.model_validate(data),HANDLING_POLICY)[0]
        ranks={i.business_process:i.handling_priority for i in got.issues}
        self.assertEqual(ranks,{'product issue':1,'store service issue':2})

    def test_undeclared_or_same_process_not_arbitrarily_sorted(self):
        for process in ('delivery/logistics issue','product issue'):
            data=self.original.model_dump();data['issues'][1]['business_process']=process
            v=AnalysisV3.model_validate(data)
            self.assertEqual(order_equal_ties(v,HANDLING_POLICY)[0],v)

    def test_high_risk_precedes_product_before_store_preference(self):
        data=self.original.model_dump();data['urgency']='high';data['issues'][1]['urgency']='high'
        v=order_equal_ties(AnalysisV3.model_validate(data),HANDLING_POLICY)[0]
        self.assertEqual({i.business_process:i.handling_priority for i in v.issues}, {'product issue':2,'store service issue':1})

    def test_non_equal_customer_priorities_not_rewritten(self):
        data=self.original.model_dump();data['issues'][0]['customer_importance']='primary';data['relations']=[]
        v=AnalysisV3.model_validate(data)
        self.assertEqual(order_equal_ties(v,HANDLING_POLICY)[0],v)

    def test_new_identity_logs_changes_and_parent_sqlite_unchanged(self):
        before=self.repo.path.read_bytes();original_hash=self.run.metadata['analysis_v3_hash']
        packet=derive(self.run,'owner-operational-v2-safe',HANDLING_POLICY)
        self.assertNotEqual(packet['analysis_hash'],original_hash)
        self.assertEqual(packet['model_calls'],0)
        self.assertEqual(verify_derived(self.run,packet),packet)
        self.assertEqual(before,self.repo.path.read_bytes())
        self.assertEqual(self.repo.get(self.run.run_id),self.run)
        self.assertEqual(len(self.repo.list_runs()),1)

    def test_tamper_parent_projection_change_log_or_identity_rejected(self):
        packet=derive(self.run,'owner-operational-v2-safe',HANDLING_POLICY)
        for key,bad in [('parent_run_id','bad'),('projection_hash','bad'),('changes',[]),('derived_id','bad')]:
            with self.assertRaises(ValueError):verify_derived(self.run,dict(packet,**{key:bad}))


class ReplyGateV3Tests(unittest.TestCase):
    def test_negative_claims_and_contrastive_positive_claims(self):
        for text in ('我们无法保证明天付款。','We cannot guarantee payment tomorrow.',
                     'We cannot confirm that a manager approved compensation.','退款尚未批准。'):
            self.assertEqual(inspect_reply(text)['status'],'no_lexical_signal',text)
        for text in ('我们无法保证今天到账，但保证明天付款。',
                     'We cannot guarantee payment today, but we guarantee payment tomorrow.',
                     'We did not pay yesterday; we will pay tomorrow.'):
            self.assertEqual(inspect_reply(text)['status'],'blocked',text)


class ReviewAndReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.repo=Repository(self.root/'run.sqlite3')
        self.run=AnalysisService(self.repo,ReplayV3({DEMO_EMAIL.input_hash:demo_result().model_dump()})).analyze(DEMO_EMAIL)
        self.opinions={k:('low','Explicit engineering fixture opinion; not a semantic reference.',[('input.body',DEMO_EMAIL.body)]) for k in DIMENSIONS}
        self.packet=build_review(self.run,self.opinions)
    def tearDown(self):self.tmp.cleanup()

    def test_eight_dimensions_unsigned_bound_and_exact(self):
        self.assertEqual(validate_review(self.run,self.packet),self.packet)
        self.assertEqual(len(self.packet['dimensions']),8)
        self.assertIsNone(self.packet['human_reviewer'])
        self.assertTrue(all(d['human_score'] is None for d in self.packet['dimensions'].values()))
        self.assertIsNone(self.packet['official_semantic_accuracy'])

    def test_reference_does_not_accept_fabricated_quote_or_ai_signature(self):
        bad=copy.deepcopy(self.opinions);bad['summary_facts']=('high','fixture',[('input.body','absent quotation')])
        with self.assertRaises(ValueError):build_review(self.run,bad)
        for mutate in (lambda p:p.update(human_reviewer='invented'),
                       lambda p:p['dimensions']['reply_requests'].update(human_score=2),
                       lambda p:p.update(input_hash='wrong'),
                       lambda p:p['dimensions']['evidence_support']['evidence'][0].update(start=2)):
            p=copy.deepcopy(self.packet);mutate(p);p.pop('packet_hash');p['packet_hash']=digest(p)
            with self.assertRaises(ValueError):validate_review(self.run,p)

    def test_failed_output_not_scored_or_derived(self):
        r=AnalysisService(self.repo,ReplayV3({DEMO_EMAIL.input_hash:'invalid'})).analyze(DEMO_EMAIL)
        packet=build_review(r);validate_review(r,packet)
        self.assertTrue(all(d['applicability']=='unaccepted_output' for d in packet['dimensions'].values()))
        with self.assertRaises((ValueError,KeyError)):derive(r)

    def test_readonly_repository_rejects_writes_and_preserves_bytes(self):
        from src.infrastructure.dashboard_sources import ReadOnlyRepository
        import sqlite3
        before=self.repo.path.read_bytes();repo=ReadOnlyRepository(self.repo.path)
        self.assertEqual(repo.get(self.run.run_id),self.run)
        with repo.connect() as conn:
            with self.assertRaises(sqlite3.OperationalError):conn.execute('DELETE FROM runs')
        self.assertEqual(self.repo.path.read_bytes(),before)

    def test_readonly_ui_original_derived_and_pending_review(self):
        from streamlit.testing.v1 import AppTest
        source=self.root/'.local/p36';(source/'draft-v3').mkdir(parents=True)
        db=source/'draft-v3/runs.sqlite3';db.write_bytes(self.repo.path.read_bytes())
        review=self.root/'pending.json';review.write_text(json.dumps([self.packet]),encoding='utf8')
        before=db.read_bytes()
        code=f"from pathlib import Path\nfrom src.app.semantic_workspace import render_semantic_workspace\nrender_semantic_workspace(Path({self.root.as_posix()!r}))"
        with patch.dict(os.environ,{'COMPLAINT_P37_SOURCE':str(source),'COMPLAINT_P37_REVIEW':str(review),'COMPLAINT_ENABLE_LIVE':'false'}):
            app=AppTest.from_string(code,default_timeout=30).run();self.assertFalse(app.exception)
            self.assertEqual(app.radio(key=f'review_view_{self.run.run_id}').value,'原始模型输出')
            app.radio(key=f'review_view_{self.run.run_id}').set_value('保守兼容视图').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('确定性派生视图' in x.value for x in app.info))
            self.assertEqual(len(app.get('download_button')),2)
            app.selectbox(key='p37_queue').set_value('有AI候选风险').run()
            self.assertTrue(any('此队列没有记录' in x.value for x in app.info))
            review.write_text(json.dumps([{'run_id':self.run.run_id}]),encoding='utf8')
            app.selectbox(key='p37_queue').set_value('全部历史输出').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('拒绝展示' in x.value for x in app.error))
        self.assertEqual(db.read_bytes(),before)

    def test_executed_actions_in_both_languages(self):
        for text in ('We have already forwarded your case.','We have logged your complaint.',
                     '我们已为您安排处理。','已将问题转交相关团队。','您的退款已批准。'):
            self.assertEqual(inspect_reply(text)['status'],'blocked',text)

    def test_vague_material_promises_require_review(self):
        for text in ('预计明天到账。','我们争取三天内退款。','We expect to refund tomorrow.','We may offer compensation.'):
            self.assertEqual(inspect_reply(text)['status'],'review_required',text)
        self.assertEqual(inspect_reply('We will review the information you provide.')['status'],'no_lexical_signal')

    def test_reported_and_conditional_approval_is_not_automatic_authorization(self):
        for text in ('You said the refund is approved.','If approved, we will refund tomorrow.'):
            self.assertNotEqual(inspect_reply(text)['status'],'no_lexical_signal',text)

    def test_default_gate_keeps_old_version_and_new_version_explicit(self):
        from src.application.v3_safety import check_reply,GATE_VERSION
        v=demo_result().model_copy(update={'suggested_reply':'预计明天到账。'})
        check_reply(v,GATE_VERSION)
        with self.assertRaises(ValueError):check_reply(v,VERSION)
        with self.assertRaises(ValueError):check_reply(v,'unknown-gate')

    def test_formal_service_accepts_explicit_policy_and_gate_offline(self):
        with tempfile.TemporaryDirectory() as td:
            analyzer=ReplayV3({DEMO_EMAIL.input_hash:demo_result().model_dump()})
            analyzer.config=analyzer.config.model_copy(update={'parameters':dict(analyzer.config.parameters,
                projection_policy='owner-operational-v2-safe',reply_gate_version=VERSION)})
            run=AnalysisService(Repository(Path(td)/'runs.sqlite3'),analyzer).analyze(DEMO_EMAIL)
            self.assertEqual(run.status,'succeeded');self.assertEqual(stored_analysis(run),demo_result())

    def test_negation_does_not_hide_not_only_or_different_action(self):
        for text in ('We not only guarantee payment tomorrow, we guarantee delivery.',
                     '我们不能确认订单，但已为您安排退款。'):
            self.assertEqual(inspect_reply(text)['status'],'blocked',text)


class HistoricalAuditTests(unittest.TestCase):
    def test_fake_provider_fixture_replay_matches_bytes_and_rejects_tamper(self):
        from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
        from src.infrastructure.p36_budget import DevelopmentBudget
        from src.evaluation.p36_report import development_comparison
        from src.evaluation.p37_replay import audit_p36,export_replay
        from src.evaluation.e2e_v3 import SEVEN
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source';source.mkdir()
            result=to_v2(demo_result(),'owner-operational-v1')[0]
            inputs=dict(inputs=[dict(email=DEMO_EMAIL.model_dump(),input_hash=DEMO_EMAIL.input_hash,
                expected={k:getattr(result,k) for k in SEVEN},reference_hash='explicit-fixture',exclude_clean=False)])
            (source/'inputs-v1.json').write_text(json.dumps(inputs),encoding='utf8')
            budget=DevelopmentBudget.create(source/'budget.sqlite3',[DEMO_EMAIL.input_hash],
                {'authorization':'P3.6-40-requests-15-CNY-fictional-development-only','inputs_hash':digest(inputs),'limits':{'requests':40,'cny':15}})
            async def provider(*args):return demo_result().model_dump_json(),dict(resolved_model='explicit-offline-fixture',provider_response_id='fixture-id',input_tokens=10,output_tokens=10,total_tokens=20)
            allruns={}
            for name in ('baseline-v1','catalog-v2','draft-v3'):
                folder=source/name;folder.mkdir()
                a=DeepSeekAnalyzer(LiveSettings('fixture',True,max_attempts=1),provider,prompt_profile='multi-issue-v3')
                a.config=a.config.model_copy(update={'parameters':dict(a.config.parameters,experiment_id=name,projection_policy='owner-operational-v1')})
                manifest=dict(config=a.config.model_dump(),inputs_hash=digest(inputs),schema_hash=digest(AnalysisV3.model_json_schema()),prompt_hash=a.config.prompt_hash)
                (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
                # Actual system string LF, snapshot intentionally CRLF on every OS.
                (folder/'prompt.txt').write_bytes(a.messages(DEMO_EMAIL)[0][1].replace('\n','\r\n').encode('utf8'))
                budget.register(a.config,digest(manifest))
                r=AnalysisService(Repository(folder/'runs.sqlite3'),a,budget=budget).analyze(DEMO_EMAIL)
                self.assertEqual(r.status,'succeeded')
                (folder/f'run-{r.run_id}.json').write_text(r.model_dump_json(),encoding='utf8');allruns[name]=r
            budget.halt('authorization_limit')
            (source/'draft-v3/comparison24-v1.json').write_text(json.dumps(development_comparison(inputs['inputs'],[allruns['draft-v3']])),encoding='utf8')
            before={p:p.read_bytes() for p in source.rglob('*') if p.is_file()}
            audit,groups=audit_p36(source);self.assertEqual(audit['runs'],3)
            self.assertEqual(export_replay(source,root/'replay')['derived_views'],3)
            self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))
            with self.assertRaises(ValueError):export_replay(source,source/'forbidden')
            with self.assertRaises(FileExistsError):export_replay(source,root/'replay')
            path=next((source/'draft-v3').glob('run-*.json'));packet=json.loads(path.read_text(encoding='utf8'))
            packet['email']['body']='tampered';path.write_text(json.dumps(packet),encoding='utf8')
            with self.assertRaises(ValueError):export_replay(source,root/'bad')
            self.assertFalse((root/'bad').exists())
            packet=allruns['draft-v3'].model_dump();packet['cohort_id']='tampered-cohort'
            path.write_text(json.dumps(packet),encoding='utf8')
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(source/'draft-v3/runs.sqlite3')) as conn,conn:
                conn.execute('UPDATE runs SET cohort_id=?',('tampered-cohort',))
            with self.assertRaisesRegex(ValueError,'identity'):audit_p36(source)

    def test_zero_budget_guard_blocks_socket_and_historical_writes(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'.local/p36';folder.mkdir(parents=True)
            path=folder/'fixture.sqlite3';Repository(path)
            before=path.read_bytes()
            code=f'''from pathlib import Path
import sqlite3,socket
import scripts.p37 as p
p.ROOT=Path({root.as_posix()!r})
p.guard()
path=Path({path.as_posix()!r})
for action in (lambda:sqlite3.connect(str(path)),lambda:sqlite3.connect(path.as_uri()+'?mode=rw',uri=True),lambda:path.write_bytes(b'bad'),lambda:(path.parent/'child').mkdir(),lambda:socket.create_connection(('example.com',443))):
    try: action()
    except (PermissionError,RuntimeError): pass
    else: raise AssertionError('guard did not block')
with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as conn: assert conn.execute('PRAGMA user_version').fetchone()[0]==2
'''
            proc=subprocess.run([sys.executable,'-B','-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=15)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(path.read_bytes(),before)

    def test_material_action_variants_and_denials(self):
        for text in ('We will process your refund tomorrow.','Your refund has been processed.','我们会尽快退款。'):
            self.assertEqual(inspect_reply(text)['status'],'blocked',text)
        for text in ('Your refund should be processed tomorrow.','We may be able to offer a refund.'):
            self.assertEqual(inspect_reply(text)['status'],'review_required',text)
        for text in ('We have not refunded your payment.','我们尚未转交您的资料。','We will not process your refund tomorrow.'):
            self.assertEqual(inspect_reply(text)['status'],'no_lexical_signal',text)
