import json
import unittest
from src.domain.contracts import (AnalysisResult,EmailInput,RunConfig,LegacyProviderResult,adapt_legacy,business_warnings,idempotency_key)
from tests.fixtures import VALID, EMAILS


class ContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(AnalysisResult.model_validate(VALID).sentiment,'negative')

    def test_empty_array_and_missing(self):
        for raw in ({},[],{k:v for k,v in VALID.items() if k!='sentiment'}):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                AnalysisResult.model_validate(raw)

    def test_invalid_types_enums_and_extras(self):
        for patch in ({'is_complaint':'false'},{'is_complaint':'garbage'},{'is_complaint':1},{'sentiment':'happy'},
                      {'product_category':'Other'},{'store_location':42},{'key_information':'x'},{'key_information':[1]},
                      {'confidence':2.0},{'confidence':float('nan')},{'summary':' '},{'unexpected':'x'}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                AnalysisResult.model_validate({**VALID,**patch})

    def test_explicit_unknown_is_not_missing_or_other(self):
        self.assertEqual(AnalysisResult.model_validate(dict(VALID,product_category='unknown')).product_category,'unknown')
        self.assertEqual(AnalysisResult.model_validate(dict(VALID,product_category='Service/Other')).product_category,'Service/Other')
        for value in ('',None,'unseen'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                AnalysisResult.model_validate(dict(VALID,product_category=value))

    def test_legacy_raw_structure_before_normalization(self):
        for value in ({},[],dict(VALID,is_complaint='true'),dict(VALID,product_category='Food/Beverage')):
            with self.subTest(value=value),self.assertRaises(ValueError):
                LegacyProviderResult.model_validate(value)

    def test_legacy_unambiguous_exact_categories(self):
        for category in ('Electronics','Home Appliances','Clothing','Furniture'):
            result,warnings=adapt_legacy(dict(VALID,product_category=category))
            self.assertEqual(result.product_category,category)
            self.assertFalse(warnings)

    def test_legacy_ambiguous_no_guess(self):
        for category in ('Beauty Products','Sportswear','Service','Other'):
            raw=dict(VALID,product_category=category)
            result,warnings=adapt_legacy(raw)
            self.assertEqual(result.product_category,'unknown')
            self.assertEqual(raw['product_category'],category)
            self.assertTrue(warnings)

    def test_consistency_is_warning_not_semantic_quality(self):
        self.assertTrue(business_warnings(AnalysisResult.model_validate(dict(VALID,is_complaint=False))))
        self.assertFalse(business_warnings(AnalysisResult.model_validate(VALID)))

    def test_input_rejects_missing_types_and_blank(self):
        for values in ({'email_id':'x','subject':'s'}, {'email_id':'','subject':'s','body':'x'},
                       {'email_id':'x','subject':'s','body':'  '},{'email_id':'x','subject':'s','body':None},
                       {'email_id':1,'subject':'s','body':'x'}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                EmailInput.model_validate(values)

    def test_hash_and_key_versions(self):
        e=EMAILS[0];c=RunConfig();key=idempotency_key(e,c)
        self.assertEqual(key,idempotency_key(e,RunConfig()))
        for changed in (e.model_copy(update={'body':e.body+'!'}),e.model_copy(update={'subject':'new'}),e.model_copy(update={'email_id':'new'})):
            self.assertNotEqual(key,idempotency_key(changed,c))
        for field,value in [('prompt_version','v2'),('schema_version','v3'),('taxonomy_version','v3'),('model_id','fake-v2'),('backend','legacy_mock')]:
            self.assertNotEqual(key,idempotency_key(e,c.model_copy(update={field:value})))
