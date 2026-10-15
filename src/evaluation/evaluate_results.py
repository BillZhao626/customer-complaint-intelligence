from __future__ import annotations
import pandas as pd
from src.evaluation.core import FIELDS, evaluate, index_rows, normalize

DEFAULT_LABEL_COLUMNS = FIELDS
LEGACY_LABEL_COLUMNS = FIELDS[:6]

def evaluate_predictions(predictions, golden, label_columns=None):
    fields = DEFAULT_LABEL_COLUMNS if label_columns is None else label_columns
    # Legacy *_label headings are resolved on Gold alone, before alignment.
    golden = golden.rename(columns={f + "_label": f for f in fields if f not in golden.columns})
    report = evaluate(predictions.to_dict("records"), golden.to_dict("records"), fields)
    report["row_count"] = report["matched"]
    report["metrics"] = [dict(label=f, **m) for f,m in report["field_metrics"].items()]
    report["legacy_display_fields"] = LEGACY_LABEL_COLUMNS
    report["confusion_matrices"] = {}
    if report["status"] == "valid":
        p=index_rows(predictions.to_dict("records"));g=index_rows(golden.to_dict("records"))
        for f in fields:
            pairs=[(normalize(g[k][f]),normalize(p[k][f])) for k in sorted(g)]
            labels=sorted({v for pair in pairs for v in pair})
            report["confusion_matrices"][f]=pd.DataFrame([[sum(a==x and b==y for a,b in pairs) for y in labels] for x in labels],index=labels,columns=labels)
    return report
