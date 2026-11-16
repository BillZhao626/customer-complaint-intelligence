"""Evidence-based E4: state ambiguity bug + explicit schema enums and source constraints."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import p5b5_live as live
from scripts.p5b5_e3 import messages as e3_messages
from src.application.p5b5_state_v2 import ConversationState
from src.evaluation.p5b5 import write_new,hashfile

def messages(email,runtime,experiment):
    msgs=e3_messages(email,runtime,experiment)
    system=msgs[0][1]+'''
E4 focused correction from observed traces; original safety and evidence requirements remain:
- If customer is undecided between return and exchange, do not invent a preferred outcome.
  A null preferred_outcome means neither option was chosen. Never turn '退还是换' into '更倾向退货'.
- Do not repeat a known order/model, even when needed by a different issue: one supplied order is
  the available identifier, reuse it unless customer explicitly says it belongs to another purchase.
  Customer reports having photos; use only existing safe evidence and do not demand new photos.
- Do not claim both store/mail routes are generally available. These merchant-specific eligibility,
  freight, exception, replacement and partial-refund terms are UNKNOWN; the request is to verify options.
- Ordinary lamp not lighting alone: do not automatically tell customer to stop power/use, keep packaging,
  or perform extra tests. Explain the actual pending aftersales request and ask only missing order/model.
- For load-bearing frame/latch failure, risk_level MUST be severe, issue urgency high, and risk_evidence
  MUST contain the exact earlier CUSTOMER failure quote. Use urgency_basis safety with nonempty matching
  evidence; never safety with none/unknown risk. Reuse it on follow-up. A wet box alone does not prove
  the lamp is wet; only conditional electrical precautions, no mandatory opening/moving/testing.
- business_process enum ONLY: product issue; store service issue; delivery/logistics issue;
  customer service response issue; refund/exchange process issue; unclear; none; unknown;
  billing/invoice issue. Never output after-sales service. reason uses its separate schema enum.
- For '不是催今天一定到', use urgency_basis other, not explicit_relaxed. For product again broken,
  use other, not repeated_failure. Do not invent service history beyond customer reports.
- Concisely distinguish what HAS been internally registered from what needs merchant verification.
  Do not guarantee no extra fee or callback. Preserve latest return-not-repair and schedule constraints.
'''
    return [('system',system),*msgs[1:]]

def main():
    paths=[Path(__file__),ROOT/'src/application/p5b5_state_v2.py',ROOT/'scripts/p5b5_e3.py']
    hashes={str(p.relative_to(ROOT)):hashfile(p) for p in paths}
    write_new(live.LOCAL/'E4-amendment.json',dict(version='E4-state-schema-source-1',source_hashes=hashes,
        hypothesis='Fix deterministic undecided preference and explicit schema enum/risk invariants seen in E3; no Gold or safety rule change',
        evidence=['E3/CAL-09-T1/evaluation.json','E3/CAL-07-T1/run.json','E3/CAL-08-T1/run.json','E3/CAL-15-T2/run.json'],
        preregistered='All 18 same DEV turns once. Remaining budget reserved for balanced blinded Judge subset plus reversal/repetition; unknown unjudged turns retained.'))
    original=live.config_analyzer
    def analyzer(email,evidence,arm,msgs):
        if any(hashfile(ROOT/p)!=h for p,h in hashes.items()):raise ValueError('E4 drift')
        a=original(email,evidence,arm,msgs)
        a.config=a.config.model_copy(update=dict(parameters=dict(a.config.parameters,amendment_sources=hashes)))
        return a
    live.config_analyzer=analyzer;live.ConversationState=ConversationState;live.candidate_messages=messages
    live.generate('E4')

if __name__=='__main__':main()
