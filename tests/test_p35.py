"""P3.5 portable engineering regressions; no semantic/model quality claims."""
import unittest
import copy
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from src.domain.contracts import EmailInput,RunConfig,digest
from src.domain.analysis_v3 import AnalysisV3,EmailAnalysis,from_v2,to_v2,stored_analysis
from src.application.v3_demo import DEMO_EMAIL,demo_result,ReplayV3
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.evaluation.e2e_v3 import Candidate,evaluate,dataset_hash


def candidate(email=DEMO_EMAIL,reference=True):
    return Candidate(dataset_id='fixture-v3',sample_id=email.email_id,subject=email.subject,body=email.body,input_hash=email.input_hash,
        generation_source='explicit_test_fixture',generation_method='explicit fixture',generation_version='1',scenarios=['equal_importance'],
        language='en',template_family=email.email_id,semantic_family=email.email_id,split='development',
        review_status='test_fixture' if reference else 'pending',reference_basis='Engineering assertions, not human labels' if reference else None,
        reference=demo_result(email) if reference else None)


class V3AvailabilityTests(unittest.TestCase):
    def test_v3_contract_available(self):
        from src.domain.analysis_v3 import AnalysisV3
        self.assertEqual(AnalysisV3.model_fields['schema_version'].default, 'analysis-v3')

    def test_calibration_verifier_available(self):
        from src.evaluation.calibration import verify_snapshot
        self.assertTrue(callable(verify_snapshot))

    def test_e2e_v3_available(self):
        from src.evaluation.e2e_v3 import evaluate
        self.assertTrue(callable(evaluate))


class V3ContractTests(unittest.TestCase):
    def test_schema_artifact_matches_runtime(self):
        schema=json.loads((Path(__file__).resolve().parents[1]/'docs/p35/analysis-v3.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(schema,EmailAnalysis.model_json_schema())

    def test_strict_types_unknown_extra_and_duplicate_ids(self):
        base=demo_result().model_dump()
        for mutate in (lambda d:d.update(extra='bad'),lambda d:d['issues'][0].update(handling_priority='1'),
                       lambda d:d['issues'][0].update(reason='wrong size'),lambda d:d['issues'][1].update(issue_id='jacket'),
                       lambda d:d['issues'][0].update(responsibility='verified')):
            data=copy.deepcopy(base);mutate(data)
            with self.subTest(data=data),self.assertRaises(ValueError):AnalysisV3.model_validate(data)

    def test_evidence_offsets_subject_and_unicode(self):
        data=demo_result().model_dump();data['issues'][0]['evidence'][0]['start']=1
        with self.assertRaises(ValueError):AnalysisV3.model_validate(data).validate_input(DEMO_EMAIL)
        e=EmailInput(email_id='unicode',subject='你好',body=DEMO_EMAIL.body)
        data=demo_result().model_dump();data['issues'][0]['evidence']=[dict(field='subject',start=0,end=2,quote='你好')]
        AnalysisV3.model_validate(data).validate_input(e)

    def test_equal_importance_is_not_operational_priority(self):
        value=demo_result();v2,diag=to_v2(value)
        self.assertEqual([i.customer_importance for i in value.issues],['equal','equal'])
        self.assertEqual([i.handling_priority for i in value.issues],[1,2])
        self.assertEqual(v2.product_category,'unknown')
        self.assertEqual(value.relations[0].kind,'equal_importance')
        self.assertTrue(any('No unique' in d for d in diag))
        lossy,diag=to_v2(value,'owner-operational-v1')
        self.assertEqual(lossy.product_category,'Clothing')
        self.assertEqual([i.customer_importance for i in value.issues],['equal','equal'])

    def test_invalid_relation_status_priority_and_high_urgency(self):
        for mutate in (lambda d:d['relations'][0].update(to_issue='missing'),lambda d:d.update(complaint_status='resolved'),
                       lambda d:d['issues'][0].update(priority_rationale=None),lambda d:d['issues'][0].update(urgency='high'),
                       lambda d:d['issues'][0].update(customer_importance='primary',importance_evidence=[])):
            data=demo_result().model_dump();mutate(data)
            with self.assertRaises(ValueError):AnalysisV3.model_validate(data)

    def test_size_fit_never_wrong_item(self):
        data=demo_result().model_dump();data['issues']=data['issues'][:1];data['relations']=[]
        data['issues'][0]['reason']='size/fit issue'
        self.assertEqual(to_v2(AnalysisV3.model_validate(data))[0].complaint_reason,'other')

    def test_v2_lossless_roundtrip_no_invented_evidence(self):
        from tests.fixtures import VALID
        from src.domain.contracts import AnalysisResult
        original=AnalysisResult.model_validate(VALID);up=from_v2(original)
        self.assertEqual(to_v2(up)[0],original)
        self.assertEqual(up.issues[0].evidence,[])
        self.assertEqual(up.contact_channel,'unavailable')
        self.assertEqual(up.complaint_status,'unknown')

    def test_reply_false_commitment_gate(self):
        from src.application.v3_safety import check_reply
        for text in ('The manager approved compensation.','We will pay tomorrow.','您的退款已批准，明日到账。'):
            with self.assertRaises(ValueError):check_reply(demo_result().model_copy(update={'suggested_reply':text}))
        check_reply(demo_result())


class V3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=Repository(self.root/'run.sqlite3')
        self.rows=[candidate()]
    def tearDown(self):self.tmp.cleanup()
    def service(self,output=None):
        return AnalysisService(self.repo,ReplayV3({DEMO_EMAIL.input_hash:output if output is not None else demo_result().model_dump()},'fixture-v3',dataset_hash(self.rows)))

    def test_service_save_reload_idempotency_and_projection(self):
        s=self.service();r=s.analyze(DEMO_EMAIL)
        self.assertEqual(r.status,'succeeded');self.assertEqual(stored_analysis(r),demo_result())
        self.assertEqual(Repository(self.repo.path).get(r.run_id),r)
        self.assertEqual(s.analyze(DEMO_EMAIL).run_id,r.run_id)
        self.assertEqual(len(self.repo.list_runs()),1)

    def test_failed_json_contract_and_unsafe_reply_persist(self):
        for output in ('bad','{}','{"a":1,"a":2}',dict(demo_result().model_dump(),suggested_reply='We will pay tomorrow.')):
            run=self.service(output).analyze(DEMO_EMAIL)
            self.assertEqual(run.status,'failed');self.assertIsNone(run.result)
            self.assertIsNotNone(run.attempts[-1].error)

    def test_hash_and_version_tampering_rejected(self):
        run=self.service().analyze(DEMO_EMAIL)
        for changed in ({'analysis_v3_hash':'bad'},{'analysis_v3':dict(run.metadata['analysis_v3'],urgency='medium')}):
            with self.assertRaises(ValueError):stored_analysis(run.model_copy(update={'metadata':dict(run.metadata,**changed)}))
        with self.assertRaises(ValueError):AnalysisService(self.repo,ReplayV3({}),RunConfig(schema_version='analysis-v3'))

    def test_email_and_issue_denominators_and_source_isolation(self):
        from src.application.v3_statistics import snapshot
        run=self.service().analyze(DEMO_EMAIL);s=snapshot([run],run.cohort_id,'fixture-v3')
        self.assertEqual((s['email_revisions'],s['issue_count']),(1,2))
        self.assertEqual(s['issue_groups']['category']['Clothing']['denominator'],2)
        self.assertEqual(s['current_complaints']['denominator'],1)
        self.assertEqual(s['members'][0]['body'],DEMO_EMAIL.body)
        with self.assertRaises(ValueError):snapshot([run],run.cohort_id,'another')
        with self.assertRaises(ValueError):snapshot([run,run],run.cohort_id,'fixture-v3')

    def test_evaluation_missing_prediction_keeps_denominator(self):
        r=evaluate(self.rows,[])
        self.assertEqual((r['eligible'],r['attempted'],r['pending']),(1,0,1))
        self.assertEqual(r['metrics']['issue_count'],{'correct':0,'denominator':1,'rate':0.0})
        self.assertIsNone(r['independent_accuracy'])

    def test_evaluation_success_failure_and_pending_reference(self):
        run=self.service().analyze(DEMO_EMAIL);r=evaluate(self.rows,[run])
        self.assertEqual(r['metrics']['issue_details']['correct'],1)
        self.assertEqual(r['content']['reply']['pending'],1)
        self.assertEqual(r['reference_pending'],0)
        pending=[candidate(reference=False)]
        r=evaluate(pending,[])
        self.assertEqual(r['reference_pending'],1);self.assertIsNone(r['metrics']['sentiment']['rate'])
        bad=self.service('bad').analyze(DEMO_EMAIL)
        # Different fixture config bound to the same dataset is an independent run cohort.
        r=evaluate(self.rows,[bad]);self.assertEqual(r['failed'],1);self.assertEqual(r['metrics']['sentiment']['denominator'],1)

    def test_reordered_issue_ids_do_not_change_matching(self):
        data=demo_result().model_dump();data['issues'].reverse()
        for i in data['issues']:i['issue_id']='new-'+i['issue_id']
        for r in data['relations']:
            r['from_issue']='new-'+r['from_issue'];r['to_issue']='new-'+r['to_issue']
        run=self.service(data).analyze(DEMO_EMAIL)
        self.assertEqual(evaluate(self.rows,[run])['metrics']['issue_details']['correct'],1)

    def test_dataset_hash_duplicate_and_cross_split_rejected(self):
        from src.evaluation.e2e_v3 import validate_candidates
        row=self.rows[0].model_dump();row['sample_id']='other';row['split']='regression'
        with self.assertRaises(ValueError):validate_candidates([self.rows[0],row])
        with self.assertRaises(ValueError):validate_candidates([self.rows[0],self.rows[0]])
        run=self.service().analyze(DEMO_EMAIL)
        altered=[self.rows[0].model_copy(update={'generation_version':'changed'})]
        with self.assertRaises(ValueError):evaluate(altered,[run])

    def test_content_review_binding_and_critical_gate(self):
        run=self.service().analyze(DEMO_EMAIL)
        review=dict(sample_id=DEMO_EMAIL.email_id,kind='reply',run_id=run.run_id,input_hash=run.input_hash,cohort_id=run.cohort_id,
            output_hash=run.metadata['analysis_v3_hash'],status='approved',reviewer='unit-test-only',evidence=['fixture'],
            rubric_version='p35-content-rubric-v1',scores={k:2 for k in ('facts','requests','all_important_issues','no_invention','safety')},critical_errors=['fixture critical failure'])
        self.assertEqual(evaluate(self.rows,[run],[review])['content']['reply']['status'],'BLOCKED')
        with self.assertRaises(ValueError):evaluate(self.rows,[run],[dict(review,output_hash='bad')])

    def test_live_profile_fake_provider_retry_and_version_binding(self):
        from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
        from src.infrastructure.pilot_budget import PilotBudget
        calls=[]
        async def provider(payload,timeout):
            calls.append(payload)
            self.assertEqual(json.loads(payload[1][1])['body'],DEMO_EMAIL.body)
            return ('bad' if len(calls)==1 else demo_result().model_dump_json()),dict(resolved_model='fake-alias',input_tokens=1,output_tokens=1,total_tokens=2)
        analyzer=DeepSeekAnalyzer(LiveSettings('fixture',True),provider,prompt_profile='multi-issue-v3')
        budget=PilotBudget.create(self.root/'budget.sqlite3',[DEMO_EMAIL.input_hash],{'config':analyzer.config.model_dump()})
        run=AnalysisService(self.repo,analyzer,budget=budget).analyze(DEMO_EMAIL)
        self.assertEqual(run.status,'succeeded');self.assertEqual(len(calls),2)
        self.assertEqual(stored_analysis(run),demo_result())
        self.assertEqual(budget.summary()['reserved_attempts'],2)

    def test_actual_app_v3_submit_and_reopen(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ,{'COMPLAINT_DB_PATH':str(self.root/'v2.sqlite3'),'COMPLAINT_V3_DB_PATH':str(self.repo.path)}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            app.button(key='v3_analyze').click().run();self.assertFalse(app.exception)
            run=self.repo.list_runs()[0]
            self.assertTrue(any(x.value=='Analysis-v3: issue details' for x in app.subheader))
            app.text_input(key='v3_lookup').set_value(run.run_id)
            app.button(key='v3_load').click().run();self.assertFalse(app.exception)
            self.assertEqual(len(self.repo.list_runs()),1)

    def test_real_langchain_mock_http_v3(self):
        import asyncio
        import httpx
        from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
        from src.infrastructure.pilot_budget import PilotBudget
        requests=[];transports=[]
        analyzer=DeepSeekAnalyzer(LiveSettings('fixture',True),prompt_profile='multi-issue-v3')
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200,headers={'x-request-id':'v3-http-fixture'},json=dict(id='v3-completion',object='chat.completion',created=1,
                model='mock-v3-returned-alias',choices=[dict(index=0,message=dict(role='assistant',content=demo_result().model_dump_json()),finish_reason='stop')],
                usage=dict(prompt_tokens=10,completion_tokens=20,total_tokens=30)))
        original=analyzer.make_client
        def client_factory(timeout):
            client,unused=original(timeout);transports.append(unused)
            transport=httpx.AsyncClient(transport=httpx.MockTransport(handler));client.root_async_client._client=transport
            return client,transport
        budget=PilotBudget.create(self.root/'http-budget.sqlite3',[DEMO_EMAIL.input_hash],{'config':analyzer.config.model_dump()})
        try:
            with patch.object(analyzer,'make_client',side_effect=client_factory):run=AnalysisService(self.repo,analyzer,budget=budget).analyze(DEMO_EMAIL)
        finally:
            for t in transports:asyncio.run(t.aclose())
        self.assertEqual(run.status,'succeeded');self.assertEqual(len(requests),1)
        self.assertEqual(json.loads(requests[0]['messages'][1]['content'])['input_hash'],DEMO_EMAIL.input_hash)
        self.assertIn('analysis-v3',requests[0]['messages'][0]['content'])
        self.assertEqual(run.metadata['resolved_model'],'mock-v3-returned-alias')
        self.assertEqual(run.attempts[0].metadata['request_id'],'v3-http-fixture')

    def test_tampered_database_refuses_v3_read(self):
        run=self.service().analyze(DEMO_EMAIL)
        with self.repo.connect() as conn:
            metadata=dict(run.metadata,analysis_v3_hash='tampered')
            conn.execute('UPDATE runs SET metadata_json=? WHERE run_id=?',(json.dumps(metadata),run.run_id))
        with self.assertRaises(ValueError):self.repo.get(run.run_id)

    def test_statistics_latest_retry_and_fallback(self):
        from src.application.v3_statistics import snapshot
        run=self.service().analyze(DEMO_EMAIL)
        latest=run.model_copy(update=dict(run_id='later',created_at='2099-01-01T00:00:00+00:00',metadata=dict(run.metadata,fallback=True)))
        s=snapshot([run,latest],run.cohort_id,'fixture-v3')
        self.assertEqual((s['email_revisions'],s['issue_count']),(1,0))
        self.assertEqual(s['states'],{'fallback':1});self.assertEqual(s['superseded_run_ids'],[run.run_id])

    def test_audit_detects_duplicates_and_historical_leakage(self):
        from src.evaluation.dataset_audit_v3 import audit
        row=self.rows[0].model_copy(update={'sample_id':'another'})
        a=audit([self.rows[0],row],[dict(sample_id='history',body=DEMO_EMAIL.body)])
        self.assertEqual(len(a['exact_normalized_body_duplicates']),1)
        self.assertEqual(len(a['historical_near_matches']),2)

    def test_actual_candidate_review_ui_is_pending(self):
        from streamlit.testing.v1 import AppTest
        path=self.root/'candidates.json'
        row=self.rows[0].model_copy(update={'split':'quarantine','exclusion_reason':'explicit quality exclusion fixture'})
        path.write_text(json.dumps([row.model_dump()]),encoding='utf-8')
        with patch.dict(os.environ,{'COMPLAINT_DB_PATH':str(self.root/'v2.sqlite3'),'COMPLAINT_V3_DB_PATH':str(self.repo.path),'COMPLAINT_V3_CANDIDATES':str(path)}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key='v3_candidate').value,DEMO_EMAIL.email_id)
            self.assertTrue(any('Human review pending' in w.value for w in app.warning))
            self.assertTrue(any('Excluded from clean semantic evaluation' in w.value for w in app.warning))
