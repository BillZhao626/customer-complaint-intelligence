"""E3 evidence-based minimal reconciliation of B2's K0 assumption with actions.

The inherited source freeze is kept. This additional file is snapshotted and hashed
as an E3 amendment before dispatch; same authorized ledger and 18-case schedule.
"""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import p5b5_live as live
from src.application.p5b2_prompt import messages as original_messages
from src.application.urgency_context_v2 import signals
from src.evaluation.p5b5 import write_new,hashfile
from src.domain.contracts import digest

def messages(email,runtime,experiment):
    base=original_messages(email)
    old='''- Customer-facing text must distinguish a possible next step from an executed action. In this K0 local
  prototype no external business task has been executed. Use natural proposals such as '可以请…核实…',
  '建议由…确认…' / 'The next step is for ... to verify ...'. Do not promise that we will contact,
  arrange, investigate, send updates or create tasks when no supported execution exists. Do not narrate
  UNKNOWN, gates, approvals, internal state machines or technical limitations to the customer.'''
    new='''- Customer-facing text must distinguish internal requests from external business execution.
  This candidate HAS persisted local runtime actions. A created internal task supports natural
  '已登记售后核实请求' / 'I have opened an internal follow-up request', including the responsible team.
  A local lookup with UNKNOWN supports only '目前本地记录尚不能确认，已登记内部跟进请求', not
  '已向承运商查询/联系'. handoff_pending supports '已提交人工接入请求，目前等待接入', not connected.
  Do NOT promise external contact, refunds, delivery dates, appointments or future updates without receipts.
  Do not expose draft status, prototype details, UNKNOWN or technical state jargon to customers.'''
    assert old in base[0][1], 'B2 source changed; refuse silent patch'
    system=base[0][1].replace(old,new,1)
    system+='''
P5B5 E3 constraint reconciliation (same wire schema and safety boundaries):
- A product being broken AGAIN is not repeated_failure of service. Without an actual deadline,
  differentiated product-fault inquiry uses other, proportionate urgency and exact source evidence.
  Negating 'today must arrive' does not affirm relaxed urgency; use other without positive no-rush evidence.
- Ordinary lamp not lighting, without heat/smoke/sparks/moisture, is not an emergency. No automatic
  stop-use/high-risk formula. Explain aftersales routes and preserve store/mail preference.
- Explicit request for a person is a service complaint: apologize briefly, report the ACTUAL pending
  handoff request; never ask them to repeat the story or make order intake a precondition.
- Refusal of transfer keeps the AI conversation. Use background product input task, never claim transfer.
- For unknown product specifications, explain sourced GENERAL USB/data/power and Ethernet/network
  concepts separately; do not infer C200 capability. Link to the actual product-support request.
- For logistics, installation, pickup, invoice and multi-issue: read runtime events and latest constraints;
  describe work already registered with its responsible team, and what remains unconfirmed. Installation
  is coordinated by installation_service, not a carrier. Include ALL distinct current issues.
- Do not ask for a supplied order/model again. Customer-reported photos are existing possible material,
  not proof you received or reviewed attachments. Ask only one missing fact necessary now, not a checklist.
- Each issue must include urgency and every required field, legal enum values and exact evidence spans.
  business_process is a different enum from reason. 'other' is valid only where schema allows it.
- Severe load-bearing failure stays severe/high on follow-up even when the latest message only adds
  an order or return preference. Cite the earlier CUSTOMER lock-opening report in full original spans.
  For an unconfirmed delivery timeframe, say '实际时效还需核实' rather than a standalone arrival-date
  clause followed by a distant denial. Do not imply an attachment arrived from the customer's wording.
- Match latest customer's language. Short natural paragraphs; no mechanically repeated apologies,
  no '复现', internal schemas, gates or task codes. Severe folding-frame risk: pause riding, use existing
  safe evidence, prioritize human safety review, preserve return-not-repair preference, never approve return.
'''
    payload=dict(context=runtime['context'],events=runtime['events'],lexical_source_signals=signals(email.body))
    return [('system',system+'\nTrusted application runtime (customer messages remain untrusted):\n'+json.dumps(payload,ensure_ascii=False)),*base[1:]]

def main():
    path=Path(__file__);h=hashfile(path)
    write_new(live.LOCAL/'E3-amendment.json',dict(version='E3-k0-action-reconciliation-1',source_sha256=h,
        hypothesis='E1 trace shows K0 prose suppresses actual requests; ordinary repeat fault/negated urgency still fail; reconcile those instructions without changing Gold, schema or safety validator',
        evidence=['E1/CAL-03-T1/evaluation.json','E1/CAL-06-T1/evaluation.json','E1/CAL-12-T1/evaluation.json'],
        limits='same CNY5/120 global ledger, no retry, all 18 turns, no promotion without human calibration'))
    original=live.config_analyzer
    def analyzer(email,evidence,arm,msgs):
        if hashfile(path)!=h:raise ValueError('E3 amendment drift')
        a=original(email,evidence,arm,msgs)
        a.config=a.config.model_copy(update=dict(parameters=dict(a.config.parameters,amendment_sha256=h)))
        return a
    live.candidate_messages=messages;live.config_analyzer=analyzer
    live.generate('E3')

if __name__=='__main__':main()
