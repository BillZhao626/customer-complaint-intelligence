"""Public explicit fixtures. Offline assertions do not measure model accuracy."""
import copy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.domain.contracts import EmailInput,digest,RunConfigV31
from src.domain.analysis_v31 import AnalysisV31,IssueV31,to_v2,stored_analysis,POLICY,PROJECTION
from src.application.research_policy_v2 import assess,language,requested_language,LEDGER,POLICY_HASH
from src.application.v31_demo import EMAIL,fixture,ReplayV31
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository

ROOT=Path(__file__).resolve().parents[1]


def one(body='I need help. Please contact me.',urgency='medium',risk='unknown',basis='general_help',reason='unknown',reply='Thank you. What help do you need?'):
    email=EmailInput(email_id='explicit-policy-fixture',subject='Synthetic policy fixture',body=body)
    ev=dict(field='body',start=0,end=len(body),quote=body)
    d=fixture().model_dump();i=d['issues'][0]
    i.update(issue_id='one',object_name='unknown',category='unknown',reason=reason,urgency=urgency,issue_kind='unknown',
        resolution='unknown',evidence=[ev],business_process='unknown',routing_team='unassigned',attribution_certainty='unknown',
        risk_level=risk,risk_evidence=[ev] if risk in ('minor','severe') else [],risk_rationale='Explicit offline fixture assessment',
        urgency_basis=basis,urgency_evidence=[ev],handling_priority=None,priority_rationale=None)
    d.update(issues=[i],urgency=urgency,complaint_status='unknown',suggested_reply=reply,summary='Explicit fixture, not model analysis.',reply_language='en')
    return email,d


def fake_candidate(id,body,quarantine=False):
    email=EmailInput(email_id=id,subject='Synthetic adoption fixture '+id,body=body)
    return dict(dataset_id='explicit-adoption-fixture',sample_id=id,subject=email.subject,body=body,input_hash=email.input_hash,
        generation_source='explicit_test_fixture',generation_method='explicit authored fixture',generation_version='fixture-1',
        scenarios=['engineering'],language='en',template_family=id,semantic_family=id,split='quarantine' if quarantine else 'development',
        exposure='development_exposed',review_status='pending',reference_basis=None,reference=None,quality_flags=[],exclusion_reason='fixture quarantine' if quarantine else None)


def adoption_inputs():
    from src.dataset.adoption_v3 import APPROVED
    ids=list(APPROVED)+['P35-073']+['retain-'+str(i) for i in range(20)]+['pending-'+str(i) for i in range(128)]+['quarantine-'+str(i) for i in range(12)]
    rows=[fake_candidate(id,'Synthetic issue for '+id,id.startswith('quarantine')) for id in ids]
    reviews=[];proposals=[]
    for row in rows[:32]:
        id=row['sample_id'];rec='revise' if id in APPROVED else 'quarantine_recommended' if id=='P35-073' else 'retain'
        reviews.append(dict(sample_id=id,input_hash=row['input_hash'],original={k:row[k] for k in ('subject','body')},source_record_hash=digest(row),recommendation=rec,business_and_evidence='Explicit test revision rationale'))
        if id in APPROVED:
            new=fake_candidate('new-'+id,'Different synthetic revised issue for '+id)
            proposals.append(dict(parent_sample_id=id,parent_input_hash=row['input_hash'],candidate=new,new_input_hash=new['input_hash']))
    return rows,reviews,proposals


def ab_manifest():
    from src.dataset.adoption_v3 import build
    from src.evaluation.p38_ab import SELECTED,build_manifest
    rows,reviews,proposals=adoption_inputs()
    # Add approved fictional candidates to this explicit experiment fixture.
    for n,id in enumerate(SELECTED):
        if id not in {r['sample_id'] for r in rows}:
            row=fake_candidate(id,'Fictional A/B input '+id);rows.append(row)
    for row in rows:row['generation_source']='codex_authored_synthetic'
    for p in proposals:p['candidate']['generation_source']='codex_authored_synthetic'
    by_id={r['sample_id']:r for r in rows}
    for review in reviews:review['source_record_hash']=digest(by_id[review['sample_id']])
    d=build(rows,reviews,proposals)
    for r in d['records']:
        if r['logical_id'] in SELECTED:
            r['quality_status']='owner_adopted'
    d.pop('manifest_hash');d['manifest_hash']=digest(d)
    # Counts change only quality_pending; recalculate before rehashing.
    from src.dataset.adoption_v3 import counts
    d['counts']=counts(d);d.pop('manifest_hash');d['manifest_hash']=digest(d)
    frozen=[]
    for i in range(24):
        e=EmailInput(email_id='frozen-'+str(i),subject='Synthetic frozen test',body=EMAIL.body if i==0 else 'Explicit fictional input '+str(i))
        frozen.append(dict(email=e.model_dump(),input_hash=e.input_hash,fictional_provenance={'kind':'explicit_test_fixture'},expected=fixture_expected()))
    return build_manifest(d,frozen)


def fixture_expected():
    return dict(sentiment='unknown',urgency='unknown',is_complaint=False,store_location='unknown',product_category='unknown',complaint_reason='none',source_attribution='none')


def fixture_references(m):
    return {r['email']['email_id']:dict(email=r['email'],input_hash=r['input_hash'],fictional_provenance={'kind':'explicit_test_fixture'},expected=fixture_expected()) for r in m['inputs'][:24]}


def authorization(m,requests=72,cny=10):
    return dict(status='researcher_explicitly_authorized',researcher='OFFLINE TEST FIXTURE',authorization_evidence='Explicit fake provider test only; no real calls',
        experiment_hash=m['manifest_hash'],requests=requests,cny=cny,prices_verified_at=datetime.now(timezone.utc).isoformat(),
        price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',model='deepseek-flash',model_availability_verified=True,
        prices=dict(input_cny_per_million=2,output_cny_per_million=8))


class PolicyTests(unittest.TestCase):
    def test_owner_ledger_eight_rules_no_gold(self):
        self.assertEqual(len(LEDGER['rules']),8);self.assertEqual(POLICY_HASH,digest(LEDGER));self.assertFalse(LEDGER['human_gold_approval'])

    def test_general_help_medium_not_unknown(self):
        e,d=one();self.assertEqual(AnalysisV31.model_validate(d).validate_input(e).urgency,'medium')
        d['urgency']='unknown';d['issues'][0]['urgency']='unknown'
        with self.assertRaises(ValueError):AnalysisV31.model_validate(d)

    def test_general_default_does_not_override_specific_problem_or_resolved_history(self):
        self.assertIsNone(assess('My shoe has a loose stitch. I need help.')['urgency'])
        self.assertIsNone(assess('The appointment was cancelled twice, but it is now resolved.')['urgency'])

    def test_explicit_urgency_and_relaxed(self):
        for body,want,basis in [('Please contact me ASAP.','high','explicit_urgent'),('Please contact me when convenient, no rush.','low','explicit_relaxed'),('请立即处理','high','explicit_urgent'),('不着急，方便时处理。','low','explicit_relaxed')]:
            with self.subTest(body=body):self.assertEqual(assess(body)['urgency'],want)

    def test_negated_urgent_and_contrast(self):
        self.assertIsNone(assess('Do not contact me ASAP.')['urgency'])
        self.assertEqual(assess('I did not say ASAP, but please contact me as soon as possible.')['urgency'],'high')

    def test_contradictory_timing_abstains(self):
        self.assertTrue(assess('Please handle this ASAP, but no rush.')['ambiguous'])

    def test_cold_saucepan_high_even_no_injury(self):
        body='The saucepan handle detached while it was empty and cold. Nobody was hurt.'
        self.assertEqual(assess(body)['urgency'],'high')
        e,d=one(body,'high','severe','safety','health or safety issue');AnalysisV31.model_validate(d).validate_input(e)
        d['issues'][0]['risk_level']='minor'
        with self.assertRaises(ValueError):AnalysisV31.model_validate(d).validate_input(e)

    def test_sparks_high_even_calm(self):
        self.assertEqual(assess('No rush. There were sparks near the socket while the kettle was on.')['urgency'],'high')
        self.assertEqual(assess('水壶使用时插座附近冒火花。我不着急。')['urgency'],'high')

    def test_negated_and_hypothetical_safety_not_high(self):
        for body in ('There were no sparks near the socket.','The manual says if sparks appear near the socket, stop.','说明书提醒如果插座冒火花立即停用，现在没有冒火花。'):
            with self.subTest(body=body):self.assertIsNone(assess(body)['risk'])

    def test_repeated_failure_medium(self):
        self.assertEqual(assess('My appointment was cancelled twice.')['urgency'],'medium')

    def test_mixed_language_explicit_request(self):
        self.assertEqual(requested_language('我的发票写错了，请用英文回复。'),'en')
        self.assertEqual(requested_language('The invoice is wrong; please reply in Chinese.'),'zh')
        self.assertEqual(language('你好 hello help thanks'),'bilingual')

    def test_wrong_reply_language_rejected(self):
        e,d=one(reply='感谢来信，请说明需要什么帮助。')
        with self.assertRaisesRegex(ValueError,'language'):AnalysisV31.model_validate(d).validate_input(e)

    def test_negated_refund_and_post_contrast_promise(self):
        from src.application.reply_review import inspect_reply
        self.assertEqual(inspect_reply('We cannot guarantee payment tomorrow.')['status'],'no_lexical_signal')
        self.assertEqual(inspect_reply('We cannot guarantee payment, but we will refund tomorrow.')['status'],'blocked')
        self.assertEqual(inspect_reply('无法保证明天付款，但我们会退款。')['status'],'blocked')


class ContractTests(unittest.TestCase):
    def test_schema_matches_published_and_legacy_unchanged(self):
        from src.domain.analysis_v3 import EmailAnalysis
        self.assertEqual(AnalysisV31.model_json_schema(),json.loads((ROOT/'docs/p38/analysis-v3.1.schema.json').read_text(encoding='utf8')))
        self.assertEqual(EmailAnalysis.model_json_schema(),json.loads((ROOT/'docs/p35/analysis-v3.schema.json').read_text(encoding='utf8')))

    def test_minor_drawer_medium_old_v3_still_rejects(self):
        from src.domain.analysis_v3 import Issue
        i=fixture().issues[0];self.assertEqual(i.urgency,'medium')
        old=i.model_dump(exclude={'risk_level','risk_evidence','risk_rationale','urgency_basis','urgency_evidence'})
        with self.assertRaisesRegex(ValueError,'high urgency'):Issue.model_validate(old)

    def test_severe_cannot_downgrade(self):
        d=fixture().model_dump();d['issues'][0]['risk_level']='severe'
        with self.assertRaisesRegex(ValueError,'high urgency'):AnalysisV31.model_validate(d)

    def test_risk_urgency_quotes_are_input_bound(self):
        for field in ('risk_evidence','urgency_evidence'):
            d=fixture().model_dump();d['issues'][0][field][0]['quote']='invented'
            with self.assertRaises(ValueError):AnalysisV31.model_validate(d).validate_input(EMAIL)

    def test_two_independent_events_and_one_restatement(self):
        e,d=one('The promised callback did not happen. My warranty question remains unanswered.','medium','none','other')
        a,b=e.body.split('. ');d['issues'][0]['evidence']=[dict(field='body',start=0,end=len(a),quote=a)]
        j=copy.deepcopy(d['issues'][0]);j.update(issue_id='second',object_name='warranty answer',evidence=[dict(field='body',start=len(a)+2,end=len(e.body),quote=b)])
        d['issues'].append(j);self.assertEqual(len(AnalysisV31.model_validate(d).validate_input(e).issues),2)
        d['issues'][1]['evidence']=copy.deepcopy(d['issues'][0]['evidence'])
        with self.assertRaisesRegex(ValueError,'Independent events'):AnalysisV31.model_validate(d)
        d['issues']=d['issues'][:1];self.assertEqual(len(AnalysisV31.model_validate(d).validate_input(e).issues),1)

    def test_together_is_not_equal(self):
        d=fixture().model_dump();d['issues'][0].update(customer_importance='equal',importance_evidence=[dict(field='body',start=140,end=len(EMAIL.body),quote=EMAIL.body[140:])])
        with self.assertRaisesRegex(ValueError,'equal importance'):AnalysisV31.model_validate(d).validate_input(EMAIL)

    def test_three_issues_order_does_not_make_customer_primary(self):
        v=fixture();self.assertEqual(len(v.issues),3);self.assertEqual({i.customer_importance for i in v.issues},{'unspecified'})
        self.assertEqual([i.handling_priority for i in v.issues],[1,2,3]);self.assertEqual(v.relations,[])

    def test_invoice_lossy_projection_not_refund_or_fault(self):
        d=fixture().model_dump();d['issues']=[d['issues'][2]];v=AnalysisV31.model_validate(d)
        p,notes=to_v2(v);self.assertEqual((p.complaint_reason,p.source_attribution),('other','unclear'))
        self.assertTrue(any('billing/invoice' in n for n in notes))
        self.assertEqual(v.issues[0].routing_team,'customer_support')

    def test_invoice_wrong_team_rejected(self):
        d=fixture().model_dump();d['issues'][2]['routing_team']='refunds'
        with self.assertRaises(ValueError):AnalysisV31.model_validate(d)

    def test_old_projection_policy_rejected_for_new_version(self):
        with self.assertRaises(ValueError):to_v2(fixture(),'customer-primary-v1')

    def test_v31_cannot_masquerade_as_v3(self):
        from src.domain.analysis_v3 import AnalysisV3
        with self.assertRaises(ValueError):AnalysisV3.model_validate(fixture().model_dump())


class ServiceTests(unittest.TestCase):
    def test_save_reopen_idempotency_and_email_issue_denominators(self):
        from src.application.v3_statistics import snapshot
        from src.infrastructure.dashboard_sources import ReadOnlyRepository
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run.sqlite3';a=ReplayV31({EMAIL.input_hash:fixture().model_dump()});service=AnalysisService(Repository(path),a)
            r=service.analyze(EMAIL);self.assertEqual(r.status,'succeeded');self.assertEqual(service.analyze(EMAIL).run_id,r.run_id)
            reopened=ReadOnlyRepository(path).get(r.run_id);self.assertEqual(stored_analysis(reopened),fixture())
            report=snapshot([reopened],r.cohort_id,a.config.parameters['dataset_id'])
            self.assertEqual((report['current_complaints']['numerator'],report['issue_count']),(1,3))

    def test_raw_output_and_projection_hash_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            r=AnalysisService(Repository(Path(td)/'run.sqlite3'),ReplayV31({EMAIL.input_hash:fixture().model_dump()})).analyze(EMAIL)
            for updates in ({'analysis_v31_hash':'bad'},{'projection_hash':'bad'},{'prediction_kind':'derived'}):
                with self.subTest(updates=updates),self.assertRaises(ValueError):stored_analysis(r.model_copy(update={'metadata':dict(r.metadata,**updates)}))
            bad=r.attempts[0].model_copy(update={'raw_output':'{}'})
            with self.assertRaises(ValueError):stored_analysis(r.model_copy(update={'attempts':[bad]}))

    def test_missing_policy_config_fails_without_relabeling(self):
        with tempfile.TemporaryDirectory() as td:
            a=ReplayV31({EMAIL.input_hash:fixture().model_dump()});a.config=a.config.model_copy(update={'parameters':{}})
            r=AnalysisService(Repository(Path(td)/'run.sqlite3'),a).analyze(EMAIL)
            self.assertEqual(r.status,'failed');self.assertIsNotNone(r.attempts[0].raw_output)

    def test_schema_cohorts_do_not_mix(self):
        from src.application.v3_statistics import snapshot
        from src.application.v3_demo import DEMO_EMAIL,demo_result,ReplayV3
        with tempfile.TemporaryDirectory() as td:
            repo=Repository(Path(td)/'run.sqlite3');a=ReplayV31({EMAIL.input_hash:fixture().model_dump()});r=AnalysisService(repo,a).analyze(EMAIL)
            old=AnalysisService(repo,ReplayV3({DEMO_EMAIL.input_hash:demo_result().model_dump()})).analyze(DEMO_EMAIL)
            with self.assertRaises(ValueError):snapshot([r,old],r.cohort_id,a.config.parameters['dataset_id'])


class DatasetTests(unittest.TestCase):
    def test_actual_state_transition_counts_from_records(self):
        from src.dataset.adoption_v3 import build
        m=build(*adoption_inputs());c=m['counts']
        self.assertEqual((c['history_records'],c['current_versions'],c['natural_candidates'],c['adversarial_candidates'],c['quality_quarantine'],c['superseded_versions']),(183,172,159,1,12,11))
        self.assertEqual(c['natural_quality_pending'],128);self.assertEqual(c['natural_semantic_review_pending'],159)

    def test_eleven_rewrites_distinct_hash_and_no_inheritance(self):
        from src.dataset.adoption_v3 import build
        m=build(*adoption_inputs());revised=[r for r in m['records'] if r['supersedes']]
        self.assertEqual(len(revised),11)
        for r in revised:
            self.assertNotEqual(r['input_hash'],r['supersedes']['input_hash']);self.assertIsNone(r['reference']);self.assertIsNone(r['prediction']);self.assertIsNone(r['output_hash'])

    def test_hash_tamper_or_old_reference_cannot_enter_rewrite(self):
        from src.dataset.adoption_v3 import build
        rows,reviews,proposals=adoption_inputs();proposals[0]['parent_input_hash']='bad'
        with self.assertRaises(ValueError):build(rows,reviews,proposals)

    def test_exact_near_lineage_and_frozen_contamination_components(self):
        from src.dataset.adoption_v3 import build,leakage_audit
        m=build(*adoption_inputs());r=m['records'][0];c=r['source_record'];e=EmailInput(email_id='frozen-fixture',subject=c['subject'],body=c['body'])
        audit=leakage_audit(m,[dict(email=e.model_dump(),input_hash=e.input_hash)])
        self.assertTrue(audit['frozen_candidate_links']);self.assertTrue(audit['exact_duplicates'])
        self.assertTrue(any(edge['kind']=='supersedes_rewrite' for edge in audit['edges']))

    def test_adversarial_excluded_from_natural_import(self):
        from src.dataset.adoption_v3 import build,current_candidates
        m=build(*adoption_inputs());rows=current_candidates(m)
        self.assertNotIn('P35-073',[r['sample_id'] for r in rows]);self.assertEqual(len(rows),159)


class ABTests(unittest.TestCase):
    def test_fake_provider_formal_live_path_and_paired_evaluator(self):
        from src.infrastructure.p38_budget import P38Budget
        from src.infrastructure.deepseek import DeepSeekAnalyzer
        from src.infrastructure.v3_live_settings import V3PilotSettings
        from src.evaluation.p38_ab import evaluate
        m=ab_manifest();auth=authorization(m);auth['prices']={'input_cny_per_million':4,'output_cny_per_million':12}
        email=EmailInput.model_validate(m['inputs'][0]['email'])
        async def fake(*args):return fixture().model_dump_json(),dict(resolved_model='OFFLINE_FIXTURE',total_tokens=30,input_tokens=20,output_tokens=10)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);b=P38Budget.create(root/'budget.sqlite3',m,auth)
            a=DeepSeekAnalyzer(V3PilotSettings('fixture-key',True,max_tokens=4000,max_attempts=1),provider=fake,prompt_profile='multi-issue-v31-A')
            a.config=RunConfigV31.model_validate(m['configs']['A'])
            run=AnalysisService(Repository(root/'runs.sqlite3'),a,budget=b).analyze(email)
            self.assertEqual(run.status,'succeeded');self.assertEqual(run.metadata['cost_cny'],.0002)
            self.assertEqual(run.metadata['prices'],auth['prices'])
            report=evaluate(m,[run]);self.assertEqual(report['arms']['A']['accepted'],1)
            self.assertEqual(report['arms']['A']['states']['missing'],31);self.assertEqual(report['arms']['A']['latency_n'],1)
            missing_cost=run.attempts[0].model_copy(update={'metadata':dict(run.attempts[0].metadata,cost_cny=None)})
            unknown=evaluate(m,[run.model_copy(update={'attempts':[missing_cost]})])
            self.assertIsNone(unknown['arms']['A']['estimated_cost_cny']);self.assertEqual(unknown['arms']['A']['cost_unknown_attempts'],1)

    def test_same_schema_two_prompts_zero_authorization(self):
        from src.evaluation.p38_ab import preflight
        m=ab_manifest();p=preflight(m)
        self.assertEqual(p['authorized_requests'],0);self.assertFalse(p['paid_dispatch_allowed'])
        self.assertEqual(m['configs']['A']['schema_version'],m['configs']['B']['schema_version'])
        self.assertNotEqual(m['configs']['A']['prompt_hash'],m['configs']['B']['prompt_hash'])

    def test_reference_not_in_provider_payload(self):
        from src.application.v31_prompt import messages
        payload=json.loads(messages(EMAIL,'B')[1][1])
        self.assertEqual(set(payload),{'email_id','subject','body','input_hash','evidence_catalog'})

    def test_budget_zero_rejects_before_file_creation(self):
        from src.infrastructure.p38_budget import P38Budget
        m=ab_manifest()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'new'/'budget.sqlite3'
            with self.assertRaises(ValueError):P38Budget.create(p,m,None)
            with self.assertRaises(ValueError):P38Budget.create(p,m,authorization(m,requests=0,cny=0))
            self.assertFalse(p.parent.exists())

    def test_live_missing_authorization_does_not_initialize(self):
        from src.application.p38_execution import run_live
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'runtime'
            with self.assertRaises(PermissionError):run_live(ab_manifest(),None,out)
            self.assertFalse(out.exists())

    def test_identity_drift_and_schedule_tamper(self):
        from src.evaluation.p38_ab import preflight
        for field in ('schema_hash','processing_chain_hash'):
            m=ab_manifest();m[field]='bad';m.pop('manifest_hash');m['manifest_hash']=digest(m)
            with self.assertRaises(ValueError):preflight(m)
        m=ab_manifest();m['schedule'][0]['arm']=m['schedule'][1]['arm'];m.pop('manifest_hash');m['manifest_hash']=digest(m)
        with self.assertRaises(ValueError):preflight(m)

    def test_missing_outputs_keep_all_paired_denominators(self):
        from src.evaluation.p38_ab import evaluate
        m=ab_manifest();report=evaluate(m,[],fixture_references(m))
        for arm in ('A','B'):
            self.assertEqual(report['arms'][arm]['input_denominator'],32);self.assertEqual(report['arms'][arm]['accepted'],0)
            self.assertEqual(report['arms'][arm]['old_seven_consistency']['denominator'],168)
        self.assertEqual(len(report['pairs']),32)

    def test_budget_hard_cap_restart_and_unknown_lease(self):
        from src.infrastructure.p38_budget import P38Budget
        from src.application.v31_prompt import messages
        from src.infrastructure.deepseek import LiveError
        m=ab_manifest();auth=authorization(m,requests=1)
        e=EmailInput.model_validate(m['inputs'][0]['email'])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'budget.sqlite3';b=P38Budget.create(path,m,auth)
            b.acquire('one',e.input_hash);b.reserve('one',1,e.input_hash,messages(e,'A'),4000)
            self.assertEqual(P38Budget(path).summary()['reserved_attempts'],1)
            with self.assertRaises(LiveError):P38Budget(path).acquire('two',e.input_hash)
            with self.assertRaises(FileExistsError):P38Budget.create(path,m,auth)

    def test_live_adapter_profile_is_bound_to_v31(self):
        from src.infrastructure.deepseek import DeepSeekAnalyzer
        from src.infrastructure.v3_live_settings import V3PilotSettings
        for arm in ('A','B'):
            a=DeepSeekAnalyzer(V3PilotSettings('offline-fixture-key',True,max_tokens=4000,max_attempts=1),provider=lambda *a:None,prompt_profile='multi-issue-v31-'+arm)
            self.assertEqual(a.config.schema_version,'analysis-v3.1');self.assertEqual(a.config.parameters['projection_policy'],PROJECTION)


class UITests(unittest.TestCase):
    def test_actual_app_v31_fixture_saved_reopen_and_labels(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'COMPLAINT_V31_DB_PATH':str(Path(td)/'ui.sqlite3'),'COMPLAINT_P38_PREPARED':str(Path(td)/'absent')}):
            app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=40).run()
            app.button(key='v31_analyze').click().run();self.assertFalse(app.exception)
            id=app.session_state['v31_run_id'];self.assertTrue(any('1封邮件 / 3个Issue' in x.value for x in app.info))
            self.assertTrue(any('未审核、未发送' in x.value for x in app.warning))
            fresh=AppTest.from_file(str(ROOT/'app.py'),default_timeout=40).run()
            fresh.text_input(key='v31_lookup').set_value(id);fresh.button(key='v31_load').click().run()
            self.assertFalse(fresh.exception);self.assertTrue(any('原始预测hash' in x.value for x in fresh.caption))
