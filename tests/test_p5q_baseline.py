from tests.archive_support import requires_archive
"""Integrity regressions with explicit copies; no API, working DB, or research writes."""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src.evaluation.p5q_baseline import validate

ROOT=Path(__file__).resolve().parents[1]


@requires_archive('docs/p5q/HUMAN_CALIBRATION_PACK_v1.json')
class P5QBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p5q_baseline_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'docs/p5q', self.root/'docs/p5q', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'resources/p5a', self.root/'resources/p5a')

    def edit_json(self, path, edit):
        target=self.root/path
        obj=json.loads(target.read_text(encoding='utf-8'))
        edit(obj)
        target.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

    def edit_csv(self, edit):
        target=self.root/'docs/p5q/DEV_CASE_AUDIT.csv'
        with target.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            fields=reader.fieldnames
            rows=list(reader)
        edit(rows)
        with target.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_complete_package_is_integrity_only(self):
        r=validate(self.root)
        self.assertEqual(r['coverage'],dict(SINGLE=48,CONVERSATION=6,BAD_CASE=3,KNOWLEDGE=4))
        self.assertEqual(r['anchors_exact'],3)
        self.assertFalse(r['semantic_certification'])

    def test_missing_case_rejected(self):
        self.edit_csv(lambda rows:rows.pop())
        with self.assertRaisesRegex(ValueError,'coverage'):validate(self.root)

    def test_duplicate_case_rejected(self):
        self.edit_csv(lambda rows:rows.append(rows[0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate(self.root)

    def test_edited_source_rejected(self):
        self.edit_json('resources/p5a/cases_dev.json',lambda obj:obj[0].update(body='edited'))
        with self.assertRaisesRegex(ValueError,'Source file hash'):validate(self.root)

    def test_owner_reference_cannot_be_rewritten(self):
        self.edit_json('docs/p5q/owner_accepted_references_v1.json',lambda obj:obj['anchors'][0].update(reply='USB直接支持'))
        with self.assertRaisesRegex(ValueError,'Frozen owner reply'):validate(self.root)

    def test_truncated_markdown_packet_rejected(self):
        target=self.root/'docs/p5q/HUMAN_CALIBRATION_PACK.md'
        target.write_text(target.read_text(encoding='utf-8').replace('您希望人工阅读原有沟通','省略'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Full packet markdown'):validate(self.root)

    def test_fabricated_human_score_rejected(self):
        self.edit_csv(lambda rows:rows[0].update(human_scores='2'))
        with self.assertRaisesRegex(ValueError,'Human fields'):validate(self.root)

    def test_invalid_evidence_rejected(self):
        self.edit_csv(lambda rows:rows[0].update(evidence_json='[{"field":"body","start":0,"end":2,"quote":"错引"}]'))
        with self.assertRaisesRegex(ValueError,'Evidence span'):validate(self.root)

    def test_reply_na_cannot_shrink_applicable_dimensions(self):
        self.edit_csv(lambda rows:rows[0].update(B1='N/A'))
        with self.assertRaisesRegex(ValueError,'Reply dimension N/A'):validate(self.root)

    def test_unproven_handoff_is_not_completed(self):
        self.edit_csv(lambda rows:rows[0].update(observed_action='FULL_HANDOFF'))
        with self.assertRaisesRegex(ValueError,'Unproven execution'):validate(self.root)

    def test_calibration_is_not_blind_gold(self):
        self.edit_json('docs/p5q/HUMAN_CALIBRATION_PACK_v1.json',lambda obj:obj.update(blind=True))
        with self.assertRaisesRegex(ValueError,'Calibration identity'):validate(self.root)

    def test_knowledge_approval_tamper_rejected(self):
        self.edit_json('resources/p5a/knowledge_drafts.json',lambda obj:obj[0].update(owner_approval='APPROVED',use_in_model='YES'))
        with self.assertRaisesRegex(ValueError,'Source file hash'):validate(self.root)
