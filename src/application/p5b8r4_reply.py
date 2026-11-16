"""Opt-in shared composer. Does not fabricate text or execute customer actions."""
import json
from src.application import p5b8r3_reply as previous
from src.application.p5b8r3_final_reply import SYSTEM as BASE
from src.application.p5b8r1_contracts import Reply
from src.domain.contracts import digest

VERSION='p5b8r4-shared-purpose-and-scoped-receipts-1'
SYSTEM=BASE+'''
For EACH past-tense claim match the receipt's kind AND business goal to that claim:
a product consultation cannot prove a praise relay; a query cannot prove arrival or refund.
Do not reuse one receipt for unrelated goals, products or stores. A created relay request
supports only that pending request, without a separate disclaimer about staff rewards.
For mixed feedback, thank the praise, apologize for the current inconvenience, answer the
technical question with scoped knowledge, then describe the actual next step. Do not ask to
repeat completed troubleshooting. No hurry changes timing, not the need to address the issue.
Keep a stated gift deadline and actual task priority; explore options without inventing an ETA.
For billing questions explain verification of basis, receipt and prior disclosure. Mention refund
approval only when needed for the customer's actual question. Avoid unrelated defensive clauses.
OUTPUT CONTRACT: exactly one JSON object with exactly one key, reply, a nonblank string.
The response_format envelope belongs to the HTTP request, never to the output. Do not add type,
metadata, explanations, multiple objects or trailing content. Escape embedded newlines and quotes.
Example syntax: {"reply":"Thank you for your message. Here is the complete response."}
End immediately after the final object brace. Validate against this field whitelist:
'''+json.dumps(Reply.model_json_schema(),ensure_ascii=False)
PLANNER_SYSTEM=previous.PLANNER_SYSTEM

def paired_messages(email,analysis,runtime):
    return {k:[('system',SYSTEM),v[1]] for k,v in previous.paired_messages(email,analysis,runtime).items()}

def chain_messages(email,runtime,analysis=None):
    return [('system',SYSTEM),previous.chain_messages(email,runtime,analysis)[1]]

def identity():return dict(version=VERSION,system_hash=digest(SYSTEM),planner_hash=digest(PLANNER_SYSTEM))
