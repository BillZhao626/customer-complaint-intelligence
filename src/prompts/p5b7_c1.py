"""One frozen general repair; not case-specific labels or answers."""
VERSION='p5b7-C1-dev-repair-1'
GUIDANCE='''
P5-B7 general consistency clarification (same wire taxonomy and owner policy):
- Distinguish explicit customer tone from unresolved business dissatisfaction using the project sentiment rule:
  an actual defect, wrong item, failed service, overdue refund or unresolved post-purchase problem is negative
  even when politely phrased as a question. A pre-purchase or ordinary specification inquiry remains neutral.
  A previously resolved problem followed by current praise need not be a current complaint.
- Derive complaint_status from your issue array. no_complaint cannot coexist with an unresolved complaint;
  current_unresolved needs at least one complaint/unresolved issue. Minor negative aspects in praise still
  need a consistent overall status; do not silently drop them. Read actual content, not any dataset intent.
- Separate events only when independently supported. Do not create two issues with identical evidence sets.
  One faulty item and its packaging can share one issue when the email supplies only one inseparable event.
  Product and service may be distinct, but preserve the purchased product category on its product issue.
- explicit_relaxed requires an actual no-rush statement, not merely 'no problem' or positive feedback.
  For explicit_urgent include the exact active deadline/need span. Two unanswered contacts are customer-
  reported repeated failure, not proof of verified ticket failure. Carry exact full evidence spans.
- Reply in the latest customer's language. An entirely English email requires an English reply, despite
  Chinese examples and rules in this system. Before returning JSON check the actual reply language.
- Describe the current useful path and matching internal receipts. Do not promise a later callback/update,
  claim photos were received/viewed, or turn a customer-reported old ETA/refund promise into a new promise.
  Retain real safety advice proportionately. Do not re-request information already supplied.
Return exactly one schema-valid JSON object. No evaluation labels, generator metadata or reference answers
are available; infer solely from the actual customer email and supplied scoped internal runtime receipts.
'''
