"""Explicit fixtures for observed long task-noun false positives, offline only."""
import unittest
from src.application.p5b8r3_final_guard import assess
from src.application.p5b8r3_final_reply import SYSTEM
class FinalGuard(unittest.TestCase):
    def test_current_created_relay_task_nouns_are_not_external_completion(self):
        rt=dict(events=[dict(event_id='e',input_hash='fixture-hash',kind='store_service_request',status='created')])
        for text in ('已在本地登记了向浦东店转达您表扬的请求。','已为您在本地提交了转达请求。','已在本店这边登记了一条表扬转达请求。'):
            self.assertFalse(assess(text,rt,'fixture-hash')['findings'],text)
            self.assertTrue(assess(text,dict(events=[]),'fixture-hash')['findings'])
    def test_separate_completion_still_requires_external_receipt(self):
        rt=dict(events=[dict(event_id='e',input_hash='fixture-hash',kind='store_service_request',status='created')])
        self.assertIn('H04',{f['code'] for f in assess('已在本地登记了转达请求，并已转达谢意。',rt,'fixture-hash')['findings']})
    def test_other_kind_or_stale_task_cannot_authorize_relay(self):
        for e in (dict(event_id='e',input_hash='fixture-hash',kind='logistics_followup',status='created'),dict(event_id='e',input_hash='stale',kind='store_service_request',status='created')):
            self.assertIn('H04',{f['code'] for f in assess('已为您在本地提交了转达请求。',dict(events=[e]),'fixture-hash')['findings']})
    def test_candidate_has_generic_execution_boundary(self):
        self.assertNotIn('B7-',SYSTEM);self.assertIn('ONLY an email composer',SYSTEM)
if __name__=='__main__':unittest.main()
