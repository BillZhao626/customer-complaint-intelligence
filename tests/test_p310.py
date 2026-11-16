"""Explicit offline fixtures for recovery; never provider quality measurements."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_urgency_context import fixture,CASES
from src.application import urgency_context_v1 as old
from src.application import urgency_context_recovery as new
from src.application import p310_prompt
from src.domain.analysis_v31_context import ContextAnalysisV31
from src.domain.analysis_v31_recovery import RecoveryAnalysisV31
from src.domain.contracts import EmailInput,digest
from src.evaluation.p310_audit import diagnostics,acceptance,normalized_dimension,build


class RecoveryTests(unittest.TestCase):
    def test_existing_positive_context_cases_preserved(self):
        for name,body,u,basis,risk in CASES:
            with self.subTest(case=name):
                e,d=fixture(body,u,basis,risk)
                RecoveryAnalysisV31.model_validate(d).validate_input(e)

    def test_service_repeat_paraphrases_and_languages(self):
        positives=('Three promised replies, zero answers.',
                   'No reply after several support messages.',
                   'My dental appointment was cancelled twice.',
                   '多次承诺回电但一直未兑现。')
        for text in positives:
            with self.subTest(text=text):self.assertTrue(new.signals(text)['repeated_failure'])
        self.assertFalse(old.signals(positives[0])['repeated_failure'])
        self.assertFalse(old.signals(positives[1])['repeated_failure'])

    def test_opposite_resolved_quoted_negated_product_repetition(self):
        negatives=('The printer jammed twice.', 'One dental appointment was cancelled.',
                   'The latch failed twice and I pushed it back twice.',
                   'I did not send several support messages. There is no reply yet.',
                   'The visits were not cancelled twice.',
                   'No appointments were cancelled twice.',
                   'The manual says "Three promised replies, zero answers."',
                   'My appointment was cancelled twice but it is now resolved.',
                   'I operated the switch twice. One appointment was cancelled.',
                   '抽屉多次滑出来，但只有一次预约无人到场。')
        for text in negatives:
            with self.subTest(text=text):self.assertFalse(new.signals(text)['repeated_failure'])

    def test_relaxed_paraphrases_and_negative_scope(self):
        for text in ('No hurry; I can wait for the guide.', 'Later is fine.',
                     '这个晚一点补也可以。','那份说明迟一点也没关系。'):
            with self.subTest(text=text):self.assertTrue(new.signals(text)['relaxed'])
        for text in ('It is not true that later is fine.', 'I did not say no hurry.',
                     'The old message says "No hurry".', '这个不可以晚一点补也可以。'):
            with self.subTest(text=text):self.assertFalse(new.signals(text)['relaxed'])

    def test_span_cannot_remove_left_negation_or_reporting(self):
        for body,quote,basis,u in [('Do not process this ASAP.','ASAP','explicit_urgent','high'),
                                    ('The manual says ASAP.','ASAP','explicit_urgent','high'),
                                    ('I did not say no hurry.','no hurry','explicit_relaxed','low')]:
            e,d=fixture(body,u,basis);start=body.index(quote)
            d['issues'][0]['urgency_evidence']=[dict(field='body',start=start,end=start+len(quote),quote=quote)]
            with self.subTest(body=body),self.assertRaises(ValueError):
                RecoveryAnalysisV31.model_validate(d).validate_input(e)

    def test_relaxation_does_not_override_severe_risk(self):
        e,d=fixture('No hurry. The battery is swollen and smoking.','high','safety','severe')
        RecoveryAnalysisV31.model_validate(d).validate_input(e)
        d['urgency']='low';d['issues'][0]['urgency']='low'
        with self.assertRaises(ValueError):RecoveryAnalysisV31.model_validate(d)

    def test_profile_delta_is_explicit_and_does_not_mutate_input(self):
        e,d=fixture('Three promised replies, zero answers.','medium','repeated_failure')
        before=copy.deepcopy(d)
        with self.assertRaises(ValueError):ContextAnalysisV31.model_validate(d).validate_input(e)
        RecoveryAnalysisV31.model_validate(d).validate_input(e)
        self.assertEqual(d,before)
        self.assertEqual(set(RecoveryAnalysisV31.model_fields),set(ContextAnalysisV31.model_fields))

    def test_all_independent_errors_not_just_first(self):
        e,d=fixture('The charger cannot power on. Please help.','medium','general_help')
        d['mentioned_store']='';d['complaint_status']='current_unresolved'
        d['issues'][0]['customer_importance']='equal';d['issues'][0]['importance_evidence']=copy.deepcopy(d['issues'][0]['evidence'])
        d['issues'][0]['urgency_evidence'][0]['end']+=100
        before=copy.deepcopy(d)
        codes={f['mechanism'] for f in diagnostics(json.dumps(d),e)}
        self.assertTrue({'required_or_shape','blank_text','general_help_specific','together_not_equal','source_span','email_issue_resolution'}<=codes)
        self.assertEqual(d,before)

    def test_diagnostics_survive_nonobject_and_invalid_field_types(self):
        e=EmailInput(email_id='fixture',subject='',body='Please advise.')
        for raw in ('null','[]','1','"x"','{}','{"issues":[null,1],"relations":null}','{"issues":[{"evidence":null,"urgency_evidence":[1]}]}'):
            with self.subTest(raw=raw):self.assertIsInstance(diagnostics(raw,e),list)
        self.assertEqual(diagnostics('{"x":1,"x":2}',e)[0]['mechanism'],'invalid_json')

    def test_finer_catalog_distinguishes_single_sentence_events(self):
        e=EmailInput(email_id='test',subject='',body='My tent tore and the delivery appointment was cancelled.')
        items=p310_prompt.catalog(e)
        for ev in items:self.assertEqual(e.body[ev['start']:ev['end']],ev['quote'])
        self.assertIn('My tent tore',[e['quote'] for e in items])
        self.assertIn('the delivery appointment was cancelled.',[e['quote'] for e in items])
        self.assertEqual(len(items),len({(v['field'],v['start'],v['end']) for v in items}))

    def test_payload_capability_and_identity_no_reference_answers(self):
        e=EmailInput(email_id='renamed',subject='Routine question',body='Can this radio use batteries?')
        p=json.loads(p310_prompt.messages(e)[1][1]);identity=p310_prompt.identity()
        self.assertEqual(p['application_capabilities'],p310_prompt.CAPABILITIES)
        self.assertFalse(p['application_capabilities']['booking_or_lookup_access'])
        self.assertEqual(identity['prompt_sha256'],sha256(p310_prompt.system().encode()).hexdigest())
        self.assertFalse(identity['default_enabled']);self.assertNotIn('expected',p);self.assertNotIn('gold',p)
        renamed=e.model_copy(update={'email_id':'different'})
        q=json.loads(p310_prompt.messages(renamed)[1][1]);p.pop('email_id');q.pop('email_id')
        self.assertEqual(p,q)
        with self.assertRaises(ValueError):p310_prompt.messages(e,repair=True)

    def test_rubric_vocabulary_normalized_without_human_scoring(self):
        for label,state,severity in [('MAJOR_CANDIDATE','defect_candidate','major'),('PASS_CANDIDATE','supported_candidate',None),('UNVERIFIED','unresolved',None),('NOT_APPLICABLE_CANDIDATE','not_applicable',None)]:
            v=normalized_dimension(dict(verdict_candidate=label,ai_opinion='fixture',evidence_quote='quote'),'failed_raw_diagnostic_only')
            self.assertEqual((v['state'],v['severity_candidate']),(state,severity));self.assertIsNone(v['human_score'])


class HistoricalRecoveryAuditTests(unittest.TestCase):
    def test_full64_replay_and_asset_immutability(self):
        root=Path(__file__).resolve().parents[1]
        path=root/'.local/p39/r3/fixed-report-delivery/paired-evaluation.json'
        notes=root/'.local/p310/reading-notes.json'
        if not path.exists() or not notes.exists():self.skipTest('Private historical64 assets unavailable')
        before=sha256(path.read_bytes()).hexdigest()
        packet=build(json.loads(path.read_text(encoding='utf8')),json.loads(notes.read_text(encoding='utf8')))
        self.assertEqual(len(packet['records']),64);self.assertEqual(packet['accepted'],34)
        self.assertEqual(sum(r['original_status']=='failed' for r in packet['records']),30)
        self.assertEqual(packet['removed_diagnostic_accepts'],0)
        self.assertGreaterEqual(packet['added_diagnostic_accepts'],3)
        self.assertEqual(sha256(path.read_bytes()).hexdigest(),before)
        for row in packet['records']:
            self.assertEqual(len(row['dimensions']),18);self.assertIsNone(row['human_semantic_score'])
            self.assertFalse(row['prediction_substituted'])
