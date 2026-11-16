"""Read-only inspection of saved experiment turns; no dispatch."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b2 import LOCAL,read,validate,strict_json
from src.domain.contracts import EmailInput
stage=sys.argv[1]
for p in sorted((LOCAL/stage/'turns').glob('*/run.json')):
    r=read(p);data=strict_json(r['attempts'][0]['raw_output']);email=EmailInput.model_validate(r['email'])
    print('\n'+email.email_id+' '+r['status'])
    print('INPUT:',email.body)
    print('REPLY:',data.get('suggested_reply'))
    print('ISSUES:',[(i.get('object_name'),i.get('issue_kind'),i.get('urgency'),i.get('urgency_basis'),i.get('risk_level')) for i in data.get('issues',[])])
    try:validate(data,email)
    except ValueError as exc:print('ERROR:',str(exc))
