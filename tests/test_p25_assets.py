"""Local full-history audit: intentionally excluded from portable checkout tests."""
import csv
import json
from pathlib import Path
import unittest
from src.evaluation.dataset_audit import audit_dataset

ROOT=Path(__file__).resolve().parents[1]

class FullDatasetAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.audit=audit_dataset(ROOT/'data/synthetic/customer_emails_full_v1.csv')

    def test_400_integrity_and_complete_distributions(self):
        r=self.audit
        self.assertEqual((r['n'],r['unique_ids'],r['template_count']),(400,400,55))
        self.assertFalse(any(r['null_counts'].values()))
        self.assertNotIn('invalid_input_or_label',r['issue_counts'])
        for counts in r['distributions'].values():self.assertEqual(sum(counts.values()),400)

    def test_generation_is_deterministic_template_not_llm(self):
        from src.dataset.generate_full_dataset_v1 import generate_records
        with (ROOT/'data/synthetic/customer_emails_full_v1.csv').open(encoding='utf-8-sig',newline='') as f:original=list(csv.DictReader(f))
        self.assertEqual(generate_records(),original)  # pure memory call; no writer invoked

    def test_known_coverage_gaps_and_ambiguous_labels(self):
        r=self.audit
        self.assertEqual(r['issue_counts']['mixed_tag_without_praise_in_body'],41)
        self.assertEqual(r['issue_counts']['high_urgency_without_explicit_text_evidence'],49)
        for key in ('missing_store','missing_product','prompt_injection','human_summary_reference','human_reply_reference'):
            self.assertEqual(r['coverage'][key]['status'],'not_covered')
        self.assertEqual(r['grouping']['exact_duplicates'],[])
        self.assertEqual(sum(len(g) for g in r['grouping']['normalized_duplicates']),400)
