"""Shallow wire form for the same strict, evidence-bound Judge decisions."""
import copy
import json

from jsonschema import Draft202012Validator
from src.evaluation import service_judge_protocol as canonical

VERSION = 'r11-judge-matrix-wire-v1'
CHECK_FIELDS = ('goal', 'reply_obligation', 'source_quote', 'status', 'reply_quote', 'consequence')
FINDING_FIELDS = ('category', 'quote', 'reason')
ACTION_FIELDS = ('quote', 'state', 'event_ids', 'missing_evidence')
INSTRUCTION = """
Use the supplied shallow matrix wire. Each answer has slot, verdict, severity, dimensions,
checks, findings and actions. Every dimension row is exactly
[dimension, applicability, score, evidence_reference, reason].
Include attitude, helpfulness, action_accuracy, reliability, information_density once each.
For helpfulness/reliability/information_density use applicability APPLICABLE.
Every check row is [goal, reply_obligation, customer_reference, status, reply_reference,
consequence]. Every finding is [category, reply_reference, reason].
Every action is [exact_full_assertion, asserted_state, [event_ids], missing_evidence].
Keep empty findings/actions as []. Do not create nested score/reason/applicability objects.
All semantic anchors and exact-source/own-event requirements above still apply.
"""


def tuple_schema(columns):
    return dict(type='array', prefixItems=columns, minItems=len(columns), maxItems=len(columns), items=False)


def schema(payload):
    original = canonical.schema(payload)
    variants = original['properties']['answers']['items']['anyOf']
    options = []
    for variant in variants:
        fields = variant['properties']
        dimension_options = []
        for dimension in canonical.DIMENSIONS:
            applicability = (fields['applicability']['properties'][dimension] if dimension in ('attitude', 'action_accuracy')
                             else dict(type='string', enum=['APPLICABLE']))
            dimension_options.append(tuple_schema([
                dict(type='string', enum=[dimension]), applicability,
                fields['scores']['properties'][dimension], fields['score_evidence']['properties'][dimension],
                fields['reasons']['properties'][dimension],
            ]))
        properties = {key: fields[key] for key in ('slot', 'verdict', 'severity')}
        properties.update(
            dimensions=dict(type='array', minItems=5, maxItems=5, items=dict(anyOf=dimension_options)),
            checks=dict(type='array', minItems=1, maxItems=6,
                        items=tuple_schema([fields['checks']['items']['properties'][key] for key in CHECK_FIELDS])),
            findings=dict(type='array', items=tuple_schema([fields['findings']['items']['properties'][key] for key in FINDING_FIELDS])),
            actions=dict(type='array', items=tuple_schema([fields['action_evidence']['items']['properties'][key] for key in ACTION_FIELDS])),
        )
        options.append(dict(type='object', properties=properties, required=list(properties), additionalProperties=False))
    output = copy.deepcopy(original)
    output['properties']['answers']['items']['anyOf'] = options
    return output


def parse(raw, payload):
    value = json.loads(raw) if isinstance(raw, str) else copy.deepcopy(raw)
    errors = list(Draft202012Validator(schema(payload)).iter_errors(value))
    if errors:
        raise ValueError('Judge matrix schema: ' + errors[0].message[:200])
    answers = []
    for answer in value['answers']:
        rows = answer['dimensions']
        if {row[0] for row in rows} != set(canonical.DIMENSIONS):
            raise ValueError('All five dimension rows required exactly once')
        by_dimension = {row[0]: row for row in rows}
        answers.append(dict(
            slot=answer['slot'], verdict=answer['verdict'], severity=answer['severity'],
            applicability={key: by_dimension[key][1] for key in ('attitude', 'action_accuracy')},
            scores={key: row[2] for key, row in by_dimension.items()},
            score_evidence={key: row[3] for key, row in by_dimension.items()},
            reasons={key: row[4] for key, row in by_dimension.items()},
            checks=[dict(zip(CHECK_FIELDS, row, strict=True)) for row in answer['checks']],
            findings=[dict(zip(FINDING_FIELDS, row, strict=True)) for row in answer['findings']],
            action_evidence=[dict(zip(ACTION_FIELDS, row, strict=True)) for row in answer['actions']],
        ))
    result = canonical.parse(dict(answers=answers, preference=value['preference']), payload)
    result.update(raw_matrix=value, wire_version=VERSION)
    return result
