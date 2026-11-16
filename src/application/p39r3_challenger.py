"""Independent B-derived Prompt candidate; no frozen A/B behavior is patched.

Only Prompt changes. The approved wire, evidence, safety and urgency validators
remain identical. Offline Prompt tests cannot prove real-model improvement.
"""
from hashlib import sha256

from src.application.p39_v2 import system as champion_system, messages as champion_messages
from src.domain.contracts import digest


VERSION = 'complaint-p39r3-B-fact-ownership-1'
PARENT_B_SHA256 = 'a4ecfaa52c37103a5dcd1544240f55c566be0adaa433132848a9c12a90c7027a'
RULES = '''
Independent exploratory fact-and-ownership review, before emitting the JSON:
Build a private event inventory: object, observed symptom or missed service,
number of distinct service occasions, current/resolved state, missing facts,
customer wording of importance, and actual requested next step. Do not emit this
inventory or reasoning. Emit only the schema JSON.

1. urgency_basis describes supporting facts, not the severity of a label. A
recurrent product symptom or repeated customer attempts to operate an item is
not repeated service non-performance. One missed visit or one unanswered
message does not establish repeated service failure. Separate product faults
from appointment, collection and response events. Count only distinct evidenced
service failures; unknown counts remain unknown. Choose supported other rather
than claiming an unevidenced named basis; never change a justified urgency to
fit a basis. A concrete inquiry is not undifferentiated general_help.
2. Read relaxed timing in natural English and Chinese, including paraphrases,
but do not invent a canonical urgency phrase in the quote. Negation, quotations,
historical resolution and contrast change the scope of time requests. Preserve
supported low urgency and separate it from basis evidence. An actual necessary
deadline or severe potential injury overrides casual tone; keep severe/high.
3. 'Together', 'both need follow-up', and a shared requested next step do not
state equal importance. Use unspecified unless the original text establishes
primary, secondary, or explicit equal importance. Handling order may be based
on safety and workflow while customer importance stays unspecified. Do not
invent equal_importance or dependency relations to justify business ordering.
4. A missing item's custody, a suggested branch, a purchase channel and a
recommended routing team do not establish fault. Distinguish location, process
classification and legal responsibility. Preserve unclear or unknown when
evidence is insufficient; responsibility remains unverified. Do not turn an
unknown whereabouts report into a proven delivery delay without timing facts.
5. Summaries preserve which issues each request concerns; do not extend a
two-issue follow-up request to every mentioned event. Acknowledge every current
issue, keep resolved background separate, and request only missing information.
6. Replies are drafts with no operational authority. Do not assert completed
forwarding, case registration, approval, a future callback, arranged visits,
available contact addresses, guaranteed response times, compensation or
payments without verified capability/authorization. Describe what needs to be
checked or confirmed without claiming it has happened or will happen. When a
customer asks where to send material and the verified channel is missing, say
the receiving channel needs confirmation; never invent an address. Keep the
useful customer next step and safety advice; avoid repetitive internal/legal
disclaimers. No lexical finding does not mean semantic safety or human approval.
7. Finally check each evidence span against the original email and ask whether
it supports this specific claim, rather than merely mentioning the same object.
Do not copy the customer's requested promise into an approved action. Do not
invent facts, approvals, Gold, reviewer decisions or runtime capabilities.
'''


def system():
    parent = champion_system('B')
    if sha256(parent.encode('utf8')).hexdigest() != PARENT_B_SHA256:
        raise ValueError('Frozen Champion B Prompt identity drift')
    return parent + RULES


def prompt_hash():
    return sha256(system().encode('utf8')).hexdigest()


def messages(email):
    # Use the original input and evidence catalog unchanged. No labels, sampled
    # IDs, reviewer opinions or case-specific answers enter the system Prompt.
    return [('system', system()), champion_messages(email, 'B')[1]]


def candidate_identity():
    body = dict(version=VERSION, parent_arm='B', parent_prompt_sha256=PARENT_B_SHA256,
                prompt_sha256=prompt_hash(), rules_sha256=sha256(RULES.encode('utf8')).hexdigest(),
                validation_profile='urgency-context-evidence-v1', schema_version='analysis-v3.1',
                semantic_acceptance_changed=False, prediction_postprocessing=False,
                exploratory_only=True, human_approved=False, model_improvement_proven=False)
    return dict(body, candidate_hash=digest(body))
