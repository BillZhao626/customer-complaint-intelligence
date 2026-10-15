"""Offline raw comparison. No taxonomy remapping, label imputation or implicit joins."""
from collections import Counter
import math

FIELDS = ['sentiment','urgency','is_complaint','store_location','product_category','complaint_reason','source_attribution']


def normalize(value):
    text = str(value).strip().lower()
    if text in {'true','1','yes'}:
        return 'true'
    if text in {'false','0','no'}:
        return 'false'
    return text


def index_rows(rows, fields=(), name='rows'):
    indexed = {}
    for number, row in enumerate(rows):
        for field in ['email_id', *fields]:
            value = row.get(field)
            if not isinstance(value,(str,bool,int,float)) or (isinstance(value,float) and not math.isfinite(value)) or not str(value).strip():
                raise ValueError(f'{name} row {number}: missing {field}')
        key = str(row['email_id']).strip()
        if key in indexed:
            raise ValueError(f'{name}: duplicate email_id {key}')
        indexed[key] = row
    return indexed


def evaluate(predictions, golden, fields=None):
    fields = FIELDS if fields is None else fields
    if not fields or len(set(fields)) != len(fields):
        raise ValueError('Evaluation requires unique, nonempty field names')
    p = index_rows(predictions, fields, 'predictions')
    g = index_rows(golden, fields, 'golden')
    matched = sorted(g.keys() & p.keys())
    missing, extra = sorted(g.keys()-p.keys()), sorted(p.keys()-g.keys())
    report = dict(status='invalid', expected=len(g), matched=len(matched), coverage=len(matched)/len(g) if g else 0,
                  missing_prediction_ids=missing, extra_prediction_ids=extra, field_metrics={}, mismatches=[],
                  warnings=[], fields=list(fields), whole_email_correct=None, correct_fields=None, total_fields=len(g)*len(fields))
    if not g or missing or extra:
        report['warnings'] = [f'Invalid coverage: expected={len(g)}, matched={len(matched)}, missing={len(missing)}, extra={len(extra)}; no score produced.']
        return report
    for field in fields:
        pairs=[(normalize(g[k][field]),normalize(p[k][field])) for k in matched]
        support=len(pairs)
        counts=Counter(a for a,b in pairs)
        precision=recall=f1=0.0
        for label in sorted({v for pair in pairs for v in pair}):
            tp=sum(a==label and b==label for a,b in pairs)
            fp=sum(a!=label and b==label for a,b in pairs)
            fn=sum(a==label and b!=label for a,b in pairs)
            pr=tp/(tp+fp) if tp+fp else 0
            re=tp/(tp+fn) if tp+fn else 0
            weight=counts[label]/support
            precision+=weight*pr; recall+=weight*re
            f1+=weight*(2*pr*re/(pr+re) if pr+re else 0)
        wrong=sum(a!=b for a,b in pairs)
        report['field_metrics'][field]=dict(accuracy=(support-wrong)/support,precision_weighted=precision,recall_weighted=recall,f1_weighted=f1,support=support,mismatches=wrong)
        report['mismatches'].extend(dict(email_id=k,field=field,prediction=str(p[k][field]),golden_label=str(g[k][field])) for k in matched if normalize(p[k][field])!=normalize(g[k][field]))
    report.update(status='valid', correct_fields=report['total_fields']-len(report['mismatches']),
                  whole_email_correct=sum(all(normalize(g[k][f])==normalize(p[k][f]) for f in fields) for k in matched))
    report['accuracy']=report['correct_fields']/report['total_fields']
    return report


def validate_summary(summary):
    """Validate the historical summary's internal arithmetic; no missing defaults."""
    try:
        if not isinstance(summary,dict) or summary['fields_compared']!=FIELDS:
            raise ValueError('seven-field definition missing or incompatible')
        n,total,wrong=(summary[k] for k in ('total_cases','total_field_count','total_mismatch_count'))
        if any(type(v) is not int for v in (n,total,wrong)) or n<=0 or total!=n*len(FIELDS) or not 0<=wrong<=total:
            raise ValueError('invalid counts')
        accuracy=summary['overall_field_accuracy']
        if not isinstance(accuracy,(float,int)) or not math.isfinite(accuracy) or abs(accuracy-(total-wrong)/total)>1e-10:
            raise ValueError('accuracy inconsistent with counts')
        metrics=summary['field_metrics']
        for field in FIELDS:
            m=metrics[field]
            if not isinstance(m['accuracy'],(int,float)) or not math.isfinite(m['accuracy']):
                raise ValueError('nonfinite field accuracy')
            if m['support']!=n or type(m['mismatches']) is not int or not 0<=m['mismatches']<=n or abs(m['accuracy']-(n-m['mismatches'])/n)>1e-10:
                raise ValueError('field metric inconsistency')
        if sum(metrics[f]['mismatches'] for f in FIELDS)!=wrong:
            raise ValueError('mismatch totals inconsistent')
        attempted,errors=summary['api_attempted_count'],summary['api_error_count']
        if any(type(v) is not int for v in (attempted,errors)) or not 0<=errors<=attempted<=n:
            raise ValueError('invalid runtime counts')
        return dict(available=True,reason='',cases=n,total=total,correct=total-wrong,mismatches=wrong,accuracy=accuracy,attempted=attempted,errors=errors)
    except (KeyError,TypeError,ValueError) as exc:
        return dict(available=False,reason=f'unavailable: missing or invalid formal report ({exc})')
