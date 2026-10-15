"""Second development revision: bilingual unsent-draft action boundary."""
import json
from hashlib import sha256
from src.application.v3_pilot_prompt import SYSTEM as BASE, catalog

PROMPT_VERSION='complaint-multi-issue-v3-3-draft'
SYSTEM=BASE+'''
Chinese reply boundary (also applies to other languages):
你只是生成未审核、未发送的回复草稿，没有记录、转交、退款、审批、升级或联系团队的执行能力。
不得写“我们已记录”“我们已经记录”“已将问题转交”“已为您安排”“已批准”“已退款”等已执行动作。
改写为“感谢您说明……”“建议核对……”“为便于核实，请提供……”。
对于冒烟等明确安全事件，可写“请继续停止使用，不要再次通电”，随后请求缺失的购买和产品资料。
客户已经说明停止使用时，认可这一事实，不要写成我们已实施了措施。
Before returning the JSON, check the suggested_reply for any claim of action by the company.
Remove every such claim, including merely saying we logged/noted/forwarded the case. Do not
replace it with guaranteed future compensation, dates, refunds or a promise to resolve the case.
'''
PROMPT_HASH=sha256(SYSTEM.encode('utf8')).hexdigest()


def messages(email,repair=False):
    return [('system',SYSTEM),('human',json.dumps(dict(email_id=email.email_id,subject=email.subject,
        body=email.body,input_hash=email.input_hash,evidence_catalog=catalog(email)),ensure_ascii=False))]
