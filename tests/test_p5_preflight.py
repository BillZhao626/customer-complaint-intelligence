import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from scripts.p5_preflight import prepare, check_packet


class PreflightTests(unittest.TestCase):
    def records(self):
        return [dict(email_id='engineering-only',subject='Fixture',body='Does the lamp have a switch?',
            source_kind='explicit_test_fixture',source_ref='test_p5_preflight',template_family='test-lamp',semantic_family='test-inquiry')]

    def test_blank_workbooks_never_certify_gold_and_are_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'new'
            manifest=prepare(self.records(),out,dict(semantic_families=['test-inquiry']))
            self.assertEqual(manifest['known_overlap_count'],1)
            self.assertFalse(manifest['independent_holdout']);self.assertFalse(manifest['gold_frozen'])
            packet=json.loads((out/'reviewer-A.json').read_text(encoding='utf-8'))
            self.assertEqual(check_packet(manifest,packet)['status'],'pending')
            self.assertIsNone(packet['reviewer'])
            tampered = deepcopy(manifest)
            tampered['samples'][0]['provenance']['semantic_family'] = 'hidden-change'
            with self.assertRaises(ValueError):check_packet(tampered,packet)
            packet['annotations'][0]['email']['body']='changed'
            with self.assertRaises(ValueError):check_packet(manifest,packet)
            with self.assertRaises(FileExistsError):prepare(self.records(),out)

    def test_duplicate_text_with_changed_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            records=self.records();records.append(dict(records[0],email_id='different-id'))
            with self.assertRaises(ValueError):prepare(records,Path(temp)/'new')
            self.assertFalse((Path(temp)/'new').exists())
