"""One shared semantic policy, used identically by both experimental arms."""
import json
from src.application import p5b8r2_reply as previous
from src.domain.contracts import digest
VERSION='p5b8r3-shared-reply-1'
SYSTEM=previous.SYSTEM+'''
R3 service priorities: establish the current unresolved request from the whole message.
When an earlier product problem has explicitly been resolved and the present request is praise,
thank the customer and arrange the requested relay; do not reintroduce warnings, fault checks or aftersales advice
unless a current unresolved hazard is actually reported. Do not imply a resolved issue still exists.
A customer saying there is no hurry changes priority, not the need for a useful concrete next step.
For current damage, place the proportionate apology before diagnostic questions or procedural details.
Praise calls for specific warm thanks, truthful relay status and a natural closing; do not invent recognition.
Include limitations only when they help answer the actual request or prevent a material misunderstanding.
Avoid unrelated refund/authority disclaimers, defensive language and explanations of internal architecture.
'''
PLANNER_SYSTEM=previous.PLANNER_SYSTEM+'''
No hurry does not mean no action. Respect resolved issues while retaining current explicit requests.
'''
def paired_messages(email,analysis,runtime):
    messages=previous.paired_messages(email,analysis,runtime)
    return {k:[('system',SYSTEM),v[1]] for k,v in messages.items()}
def chain_messages(email,runtime,analysis=None):
    return [('system',SYSTEM),previous.chain_messages(email,runtime,analysis)[1]]
def identity():
    return dict(version=VERSION,system_hash=digest(SYSTEM),planner_hash=digest(PLANNER_SYSTEM),knowledge_hash=digest(previous.KNOWLEDGE))
