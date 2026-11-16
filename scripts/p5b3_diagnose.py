from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.live_execution import strict_json
from src.domain.analysis_v32 import validate
from src.domain.contracts import EmailInput
for p in (ROOT/'.local/p5b3-20261029-v1'/sys.argv[1]).glob('*/run.json'):
    r=json.loads(p.read_text(encoding='utf8'))
    try:validate(strict_json(r['attempts'][0]['raw_output']),EmailInput.model_validate(r['email'])); error='PASS'
    except Exception as e:error=str(e)
    print(r['email']['email_id'],error.encode('ascii','backslashreplace').decode()[:1600])
