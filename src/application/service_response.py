"""Current response strategy below the existing analysis/action/review interfaces.

No model invocation, reference labels, case IDs or historical runner dependency.
Use implementations explicitly to compare/rollback; pending local work is not external execution.
"""
import copy,json,re
from src.application.p5b8_pipeline import guided_actions as issue_actions,validate_plan,execute,OWNERS
from src.application.p5b8r1_contracts import parse_reply
from src.application.reply_guidance import service_checks, source_topics, strengthen_plan
from src.domain.contracts import digest
VERSION='service-response-r11-risk-review-v27'

SYSTEM_CORE="Compose the complete first customer-service email in the customer's language.\nReturn exactly one JSON object with one nonblank string key reply. No analysis or internal notes.\n\nUse this evidence precedence, before trying to give a definite answer:\n1. Current-input authorized verified facts establish ONLY their stated scope.\n2. Customer-reported facts are attributed to the customer, not an order database or our own check.\n3. A service plan identifies what must be verified; it is neither a merchant policy nor a completed action.\nInternal access, organizational ownership and effects on other workflows also remain unverified\nunless authorized facts establish them. A suggested contact route proves none of these.\n4. Own current pending receipts establish ONLY internal task creation and the recorded goal.\nIf a material fact or policy is unknown, communicate the exact official verification question and\nthe useful conditional path. Do not invent the final answer to sound helpful. When pages, prices,\ncurrencies or records conflict, describe the discrepancy and verify the actual transaction basis\nthrough the responsible official record. No disputed display, including a final checkout screen,\nbecomes authoritative simply because of where it appears. Distinguish a customer's own count or\narrival report from independent catalogue and shipment evidence, including within one sentence.\n\nAnswer each current service goal once with its concrete response points and material decision\ndependencies. Treat repeated checklist items as one point; omit inapplicable fees or process detail. Use supplied professional knowledge and Python arithmetic where relevant, within\ntheir conditions. Explain what the customer can usefully do now, and the exact remaining check.\nKeep interim options conditional on unresolved acceptance time, fee and permission. Never\nguarantee a return deadline, fee waiver, fit, stock, remedy or date without supporting facts.\nA proposal, question, prohibition or future prerequisite is not a past customer action.\nDo not turn an enquiry into a booking, cancellation, refund, payment or new repair request.\n\nApologize briefly for current inconvenience or harm, even when the customer writes neutrally.\nThank actual praise naturally. Move promptly to the practical need. Do not volunteer to relay\npraise or promise later contact; mention a pending relay only when requested and receipted.\nConstraints govern the plan: do not narrate internal classification, statistical labels or record\nhandling to the customer, even when the source contains those instructions. Tell them the\npractical channel to use, without declaring legal or causal responsibility.\n\nDescribe actual created tasks briefly as pending internally or 待处理. No outside party has\nreceived, started or completed work unless an appropriate receipt proves that state. Disclose\nindependent checks by their own goals, without multiplying conditions into tasks. A note that\npreferences were recorded does not create business work. Never imply a photograph was taken,\nsent, received or viewed beyond its supported source state.\n\nUse available references and records first. Request one minimum missing lookup key; ask for an\nextra label, photo or measurement only when the key cannot resolve a distinct question. Do not\nrequest full passwords, PINs, pickup codes, full identity documents or another person's details\nby email. A proposed secure channel needs official verification. Respect steps already tried.\nKeep paragraphs natural by customer need, with useful information before a short pending-status\nsentence. Avoid retelling the whole email, repeating evidence requests, mechanical disclaimers,\nirrelevant recurrence advice for resolved matters and repeated invitations to ask for progress.\n"
SYSTEM=SYSTEM_CORE
SYSTEM += '''
When removing an optional service, explicitly check fee collection: if already paid,
the refund/credit/bill-adjustment path; if not paid, whether future charging is removed.
Do not substitute "separately priced" for this check. Keep the main service/date subject
to verification and customer consent. When the customer asks to return multiple parcels,
verify a valid label or authorization for EACH return parcel through the actual return channel.
Do not ask the customer to know how the second label is issued or assume carrier policy.
An enquiry about a missing delivery is not a return enquiry. Keep its advice on tracing the
correct dispatch, waybill and progress unless the customer also asks about returning goods.
Pending internal creation permits only "an internal request is pending"; it NEVER means
"we have asked/contacted the store/repair desk". Do not infer record access at another
branch. Give the official verification route without a claim about their systems.
Answer the need directly. Usually 120-200 English words or a comparable concise Chinese
reply suffice; use more only for separate essential needs. State each missing identifier
once. Avoid repeated policy disclaimers or a second closing request. Mild brevity goals
must not remove a material fee, time, privacy or safety condition.
Do not describe a merchant procedure as normally/routinely/usually true without a scoped
authorized policy. Saying the requested date should be preserved is a constraint; it is
not evidence that it will remain unchanged after a service removal. Keep both separability
and delivery-date preservation conditional on verification, even at the end of a paragraph.
Use authorized_case_facts explicitly wherever they answer the customer's question, within
their actual product/record scope. Do not ask for an already supplied reference or file.
When the source reports a file sent earlier, check that channel's receipt/record first;
do not ask to resend the same file merely because this email has no attachment.
For different purchase and trial/collection branches, identify the purchase channel's
official verification route from the customer's report. Do not add a statement about another
branch lacking access, and do not repeat internal complaint-classification instructions.
For a one-cycle subscription skip, explicitly check whether that cycle is charged and
what happens to the following billing/refill date and discount, not only whether a skip is allowed.
For a locker fault, use the operator contact shown on the unit/order as a verification route.
Do not claim a carrier lacks opening authority, access or responsibility; those are unknown.
When a no-duplicate/no-change constraint is already in an actual local task goal, say it is
included in that pending check. Do not merely promise to add it later or imply that an outside
shipment/order hold has been applied. Preserve the requested items and conditions explicitly.
Respect the customer's chosen secure channel even for a partial card reference. If they offer
last-four characters through a secure channel, do not ask for those characters in an ordinary
email reply. Explain verification of the official secure route using the existing order/site
contact details; no portal, URL or telephone number is invented. Use only an allowed non-secret
lookup reference here, or let the secure-route verification proceed before sharing the token.
An internal created/pending task does not show active investigation. Do not say it is already
being checked or 正在核对 unless a current receipt explicitly establishes that started state.
Never turn a necessary numerical condition into sufficient safety approval. For electrical
loads, do not propose separate sockets/circuits or alternating use as verified safe from the
appliance wattages alone. For whichever-comes-first usage/time limits, unknown usage never
permits waiting until the calendar maximum. Ask for the exact official verification instead.
'''

SYSTEM += '''
Give useful conditional service routes even when final acceptance is unknown. For a separately
affected second product, explain how assessment can be checked with its actual seller or brand
through the official aftersales channel. Distinguish purchases here from another seller and
ask for the missing purchase channel. Do not defer all help until an assessor is already known.
For cancellation involving a deposit or outstanding balance, verify cancellation effectiveness,
deposit treatment, balance deadline and whether obligations remain during review. Never advise
stopping or continuing payment without that basis. When time may be short, direct timely
confirmation with official human support using the current payment notice and order reference.
For bundle returns check actual order discount allocation and retained items first. Discuss
coupon rules only if the source or verified order establishes a coupon. A general bundle
discount does not establish one. Use concise paragraphs organized around the customer goals.
For missing items first locate the order, then check the relevant consignment and progress.
Give an available delivery estimate only from an actual applicable logistics record, and
claim outside contact only when its receipt exists. Avoid repeating the same uncertainty.
General policy examples do not establish what this customer said. Do not attribute no-change,
no-duplicate, collection or other constraints to the customer unless the original email
actually contains them. A restriction on advice does not create a separate business task.
Make the initial intake immediately actionable. When a scoped authorized fact already identifies
the order, use that reference for its stated purpose. Do not ask the customer to send that same
reference again. Request a distinct identifier only to resolve a genuine missing link. Attribute
catalogue, policy and order facts to their supplied records, and the customer's report to them.
Keep technical advice within the applicable model/record or a supplied professional reference.
When those are absent, give the needed measurements or the specific verification question.
Do not introduce an unrelated treatment, return, electrical precaution or policy example.
Use the current product and order only. Leave unrelated historical or third-party facts out of
the reply, including reports of prior photos or text that is explicitly background only.
Do not narrate internal complaint-classification instructions back to the customer.
State actual internal pending creation once. Put the remaining conditions in the useful next
step, without restating the complete task goal or promising staff follow-up.
'''

PLANNER_SYSTEM='''Read the original email and plan useful LOCAL internal tasks. JSON only:
{"actions":[{"kind":"human_input_request","issue_ids":[],"goal":"specific verification","evidence":["exact source quote"],"priority":"normal"}]}.
Allowed kind: '''+', '.join(OWNERS)+'''. Each goal must address a current request, with literal source quotes.
Past resolved faults do not cancel a current explicit/implicit request to pass thanks to staff.
Praise alone needs no relay unless requested. Use store_service_request for requested thanks relay.
An ongoing product fault needs aftersales_request to verify inspection/repair/exchange eligibility,
even when the customer also asks a technical question or says no hurry. Damage in delivery needs
both aftersales_request and logistics_followup to check handling, not to assert carrier liability.
For a gift deadline include checking replacement stock, expedited delivery and alternatives; guarantee none.
Billing requests check line item, basis and prior disclosure. No refund task unless actually requested.
Separate privacy/contact correction checks from missing-shipment checks. Verify applicable merchant
terms for promotion cutoff and payment timestamp. Treat skip, collection by another person and
temporary equipment loans as inquiries unless the customer authorizes a specific change.
No external execution, store contact, booking or payment is authorized. High priority requires time/risk evidence.'''

RELAY=re.compile(r'转达|转告|转交|希望店.{0,8}知道|(?:pass|relay|forward).{0,45}(?:thanks|gratitude|praise|compliment|kind words|positive feedback)',re.I)
NEGATED_RELAY=re.compile(r'不要|无需|不必|不需要|别|do not|don.t|no need|not asking',re.I)
DEADLINE=re.compile(r'周[一二三四五六日天]|星期|本周|这周|周末|生日|(?:before|by) (?:a |this |next )?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|birthday|this weekend',re.I)
INTAKE_PROHIBITION = re.compile(
    r'(?:请)?(?:不要|别|请勿)(?:让我|要求我|要求客户|向我索要)?[^。；;!?]{0,36}'
    r'(?:发送|提供|提交|转发|分享)[^。；;!?]{0,24}(?:身份证|证件照片|完整卡密|取件码)[^。；;!?]{0,16}|'
    r'(?:please )?(?:do not|don.t) (?:ask (?:me|us|the customer) to )?(?:send|provide|share|forward) '
    r'[^.;!?]{0,65}(?:ID (?:images?|documents?)|passport|full PIN|pickup code)[^.;!?]{0,40}', re.I,
)
BACKGROUND_ONLY = re.compile(
    r'i am reporting that (?:text|quote),? not instructing you|'
    r'(?:那|这)是(?:我)?(?:朋友|他人|别人|另一位客户)的订单[，, ]*(?:与我无关|不是我的订单)', re.I,
)

def source_clauses(text):
 return [m.group().strip() for m in re.finditer(r'[^。！？!?\n]+',text) if m.group().strip()]

def relay_quotes(text):
 return [s for s in source_clauses(text) if RELAY.search(s) and not NEGATED_RELAY.search(s[:RELAY.search(s).end()])]

def merge_actions(actions):
 unique={}
 for a in actions:
  key=(a['kind'],tuple(sorted(a['issue_ids'])))
  if key not in unique:unique[key]=copy.deepcopy(a)
  else:
   b=unique[key]
   b['goal']='; '.join(dict.fromkeys(x.strip() for goal in (b['goal'],a['goal']) for x in re.split('[;；]',goal) if x.strip()))
   b['evidence']=list(dict.fromkeys(b['evidence']+a['evidence']))
   if a['priority']=='high':b['priority']='high'
 return list(unique.values())

def plan_actions(analysis,*,email=None):
 """Repair intent-to-action at the shared mapping, not at reply or Guard."""
 actions=issue_actions(analysis)
 # The source can establish a historical fault is now resolved even when the
 # model retains resolution=unknown. Remove only request-free historical tasks;
 # mixed emails with a current fault/request are preserved.
 source=(email.subject+'\n'+email.body) if email is not None else ''
 resolved_now=bool(re.search(r'问题已解决|现在.{0,6}正常|已经.{0,6}正常|so far so good|working (?:well|fine) (?:now|since)|has been fixed',source,re.I))
 historical_ids={i['issue_id'] for i in (analysis or {}).get('issues',[]) if resolved_now and i['business_process']=='product issue' and not i['customer_requests'] and i['resolution']!='unresolved'}
 if email is not None and 'service_loan' in source_topics(email):
  # A product currently being repaired is the reason for a loan enquiry.
  # Preserve separately requested aftersales work and any reported new fault.
  for issue in (analysis or {}).get('issues',[]):
   if issue['business_process']=='product issue' and not issue['customer_requests'] and issue['evidence'] and all(
       re.fullmatch(r'[^。!?！？]{1,26}(?:正在维修|维修中|is being repaired|is being serviced)[。.!]?',quote,re.I)
       for quote in issue['evidence']):
    historical_ids.add(issue['issue_id'])
 actions=[a for a in actions if not (a['kind'] in ('aftersales_request','human_input_request') and a['issue_ids'] and set(a['issue_ids'])<=historical_ids)]
 for i in (analysis or {}).get('issues',[]):
  requests=i['customer_requests'];text='; '.join(requests);quotes=i['evidence'];ids=[i['issue_id']]
  if requests and relay_quotes(text):
   actions.append(dict(kind='store_service_request',issue_ids=ids,goal=text,evidence=quotes,priority='normal'))
  # A negative unresolved product experience requires a real eligibility/inspection task,
  # rather than only a product-support query. Neutral wording does not cancel that need.
  if i['issue_id'] not in historical_ids and i['resolution']=='unresolved' and i['business_process']=='product issue' and i['experience_polarity']=='negative':
   actions.append(dict(kind='aftersales_request',issue_ids=ids,goal=text+'；核实检查、维修或退换适用条件',evidence=quotes,priority='high' if i['risk']=='severe' or i['urgency']=='high' else 'normal'))
   # A model may collapse package + product damage into one product Issue.
   # Recover a verification request from literal packaging evidence; this is
   # association, never a finding that the carrier caused the damage.
   packaging=[q for q in quotes if re.search(r'外箱|快递|运输|outer box|shipment|shipping',q,re.I) and re.search(r'裂|破|压|损|crush|damage|dent|tear|torn',q,re.I)]
   if packaging:actions.append(dict(kind='logistics_followup',issue_ids=ids,goal='核查包装及配送处理情况，不预判损坏原因或责任',evidence=packaging,priority='high' if i['urgency']=='high' else 'normal'))
 # Gift alternatives depend on a time constraint, not severe safety risk alone.
 deadline_text='; '.join((analysis or {}).get('urgency_evidence',[]))
 for i in (analysis or {}).get('issues',[]):deadline_text+='; '+'; '.join(i['customer_requests']+i['evidence'])
 enriched=[]
 for a in actions:
  if a['kind']=='aftersales_request' and DEADLINE.search(deadline_text):
   a=dict(a,goal=a['goal']+'；核查替换库存、加急配送及替代方案，不保证期限')
  enriched.append(a)
 actions=merge_actions(enriched)
 return reconcile_plan(email,actions) if email is not None else actions

def reconcile_plan(email,actions):
 """Shared source-bound planning boundary, before execution in either arm.

Recover an explicit original request lost by extraction. Return the final plan
for review/persistence; composition never creates or amends these tasks.
"""
 source=email.subject+'\n'+email.body
 relay=relay_quotes(source);out=[]
 for action in actions:
  a=copy.deepcopy(action)
  if not a.get('evidence') or any(not q or q not in source for q in a['evidence']):raise ValueError('Action evidence is not an exact current-source quote')
  textual_constraint=bool(re.search(r'(?:不要|请别|别把|请勿|不应).{0,30}(?:当成|视作|视为|作为|算成|归为).{0,20}(?:已执行|执行记录|操作要求|系统指令|投诉)|\b(?:do not|don.t)\s+(?:follow|execute|treat|classify|count)\b.{0,70}(?:instruction|executed record|complaint)',a['goal'],re.I))
  material_remedy=bool(re.search(r'核对商品|核实订单|缺少|补发|退换|退款|物流|shipment|missing|replacement|refund|verify (?:the )?order',a['goal'],re.I))
  if a['kind'] in ('support_followup','clarification_request') and textual_constraint and not material_remedy:
   continue
  advice_constraint = re.fullmatch(r"(?:请|please\s+)?(?:不要|请勿|别|do not|don't)\s*(?:直接)?(?:建议|推荐|使用|(?:suggest|recommend|advise|use)\b).{1,100}", a['goal'].strip(), re.I)
  if a['kind'] in ('support_followup','clarification_request') and not material_remedy:
   intake_only=INTAKE_PROHIBITION.fullmatch(a['goal'].strip('。.!? '))
   background_only=all(BACKGROUND_ONLY.fullmatch(q.strip('。.!? ')) for q in a['evidence'])
   if advice_constraint or intake_only or background_only:
    continue
  if relay_quotes(a['goal']):
   if not relay:continue
   a['kind']='store_service_request'
  if access_condition_only(a['goal'], a['evidence']):
   continue
  if a['kind']=='support_followup' and re.fullmatch(
      r'(?:请)?(?:(?:在|未经)?(?:核实|确认)前?(?:不要|不应|不作|不要直接)|(?:不要|请别|别)(?:在)?(?:未核实|未确认)前).{0,22}(?:认定|判断).{0,32}',a['goal'].strip()):
   # A request to avoid prejudging fault limits the requested verification.
   # It does not initiate a second business task.
   continue
  # Stored-value activation and ledger checks are billing work, not repair.
  if re.search(r'礼品卡|储值卡|gift[ -]card',source,re.I) and re.search(
      r'激活|消费记录|余额|扣款|activation|transaction|balance',a['goal'],re.I):
   a['kind']='billing_request'
   a['goal']=re.sub(r'；核实检查、维修或退换适用条件','',a['goal'])
  out.append(a)
 if relay and not any(a['kind']=='store_service_request' and re.search('转达|转告|谢意|relay|thanks|gratitude',a['goal'],re.I) for a in out):
  out.append(dict(kind='store_service_request',issue_ids=[],goal='; '.join(relay),evidence=relay,priority='normal'))
 packaging=[s for s in source_clauses(source) if re.search(r'外箱|快递|运输|outer box|shipment|shipping',s,re.I) and re.search(r'裂|破损|受压|压坏|crush|damaged|dent|torn',s,re.I) and not re.search(r'没有破损|完好|was fine|undamaged|not damaged',s,re.I)]
 resolved_damage=bool(re.search(r'问题已解决|已经换好|更换好了|has been resolved|has been replaced',source,re.I))
 if packaging and not resolved_damage and not any(a['kind']=='logistics_followup' for a in out):
  out.append(dict(kind='logistics_followup',issue_ids=[],goal='核查包装及配送处理情况，不预判损坏原因或责任',evidence=packaging,priority='normal'))
 out = strengthen_plan(email,out)
 # Lookup prerequisites belong to the one owner already handling that Issue.
 # An independent Issue or an ambiguous multi-owner clarification remains separate.
 for question in [a for a in out if a['kind']=='clarification_request' and a['issue_ids']]:
  owners=[a for a in out if a['kind']!='clarification_request' and set(question['issue_ids'])<=set(a['issue_ids'])]
  if len(owners)==1:
   owner=owners[0]
   owner['goal']+='；'+question['goal']
   owner['evidence']=list(dict.fromkeys(owner['evidence']+question['evidence']))
   if question['priority']=='high':owner['priority']='high'
   out.remove(question)
 # Finding the missing tracking reference is part of tracing this shipment.
 logistics = [action for action in out if action['kind']=='logistics_followup']
 if len(logistics)==1:
  main = logistics[0]
  for action in out[:]:
   same_goal = action['goal'].strip('；;。 ') == main['goal'].strip('；;。 ')
   tracking_reference = re.fullmatch(
       r'(?:请)?(?:提供|查找|核对|核实)(?:第[二三四五个]+个?|另一个|另一件的)?(?:运单(?:号|信息)?|物流单号)|'
       r'(?:provide|locate|check|find) (?:the )?(?:second|other|missing)?\s*tracking (?:number|reference|details)',
       action['goal'].strip(), re.I)
   if action['kind']=='support_followup' and (same_goal or tracking_reference):
    if not same_goal:
     main['goal'] += '；' + action['goal']
    main['evidence'] = list(dict.fromkeys(main['evidence'] + action['evidence']))
    main['issue_ids'] = list(dict.fromkeys(main['issue_ids'] + action['issue_ids']))
    out.remove(action)
 constraints=[q for q in source_clauses(source) if re.search(r'(?:不要|请勿|别).{0,6}重复(?:寄|发)|\b(?:do not|don.t|without)\s+(?:resend|resending)|\bno duplicate (?:shipment|dispatch)',q,re.I)]
 for action in out:
  if action['kind']=='logistics_followup' and constraints:
   action['goal']+='；将不重复寄送已收商品作为核查约束，核对是否存在重复发货风险 / verify no duplicate dispatch of already received items; constraint: '+'; '.join(constraints)
   action['evidence']=list(dict.fromkeys(action['evidence']+constraints))
 return merge_actions(out)

def access_condition_only(goal, evidence):
 """A code-sharing restriction constrains an appointment, without starting work."""
 secret = r'门锁密码|门禁密码|门锁码|钥匙密码|\b(?:key|door|entry|access) code\b'
 condition = r'别|不要|未经|先问|征得|同意前|保密|before|do not|don.t|without|keep.{0,15}private|permission|consent'
 remedy = r'更改|更换|重置|补发|预约|改期|上门|reset|reissue|replace|appointment|visit|reschedul'
 return bool(re.search(secret, goal, re.I) and re.search(condition, goal, re.I)
             and not re.search(remedy, goal, re.I)
             and any(re.search(secret, quote, re.I) and re.search(condition, quote, re.I) for quote in evidence))

def current_receipts(email,runtime):
 """Select only this input's latest actual operation state; plans are not receipts."""
 latest={}
 for e in runtime.get('events',[]):
  if e.get('input_hash')!=email.input_hash or e.get('conversation_id',email.email_id)!=email.email_id:continue
  if not e.get('event_id') or e.get('kind') not in OWNERS:continue
  binding=e.get('_binding')
  if binding and (binding.get('input_hash')!=email.input_hash or binding.get('event_hash')!=digest({k:v for k,v in e.items() if k!='_binding'})):continue
  if any(e.get(k,binding.get(k) if binding else None)!=v for k,v in runtime.get('identity',{}).items() if k in ('run_id','arm')):continue
  latest[e.get('operation_id',e['event_id'])]=e
 return [e for e in latest.values() if e['status'] in ('created','handoff_pending')]

def missing_actions(email,planned,events):
 """Do not create a second pending task when this run already covers its goal."""
 current=current_receipts(email,dict(events=events))
 norm=lambda s:re.sub(r'\s+','',s.casefold())
 def covered(action):
  goals=[norm(x) for x in re.split('[;；]',action['goal']) if x.strip()]
  return any(e['kind']==action['kind'] and set(e['payload']['action'].get('issue_ids',[]))==set(action['issue_ids']) and all(x in norm(e['payload']['action'].get('goal','')) for x in goals) for e in current)
 return [a for a in planned if not covered(a)]

def brief(email,runtime,analysis=None):
 source=email.subject+'\n'+email.body
 tasks=[dict(event_id=e['event_id'],kind=e['kind'],status=e['status'],goal=e['payload']['action'].get('goal',''),priority=e['payload']['action'].get('priority','normal')) for e in current_receipts(email,runtime)]
 clauses=source_clauses(source)
 checks=service_checks(email,runtime)
 completed=[]
 if re.search(r'重新(?:装|安装)过|重新安装了|reinstalled|reseated',source,re.I):completed.append('tank_seating')
 if re.search(r'清洗过|清洗了|cleaned',source,re.I):completed.append('seal_cleaning')
 acknowledgements=[]
 harm=[s for s in clauses if re.search(r'渗.{0,5}水|漏.{0,5}水|破损|磕痕|开线|crushed|dented|damaged|leaking',s,re.I) and not re.search(r'没有破损|未损坏|undamaged|not damaged',s,re.I)]
 for issue in (analysis or {}).get('issues',[]):
  if issue.get('experience_polarity')=='negative' and issue.get('resolution')=='unresolved':
   harm.extend(q for q in issue.get('evidence',[]) if q in source and q not in harm)
 for topic in checks['topics']:
  if topic['topic'] in ('contact_privacy','missing_shipment','uncomfortable_odor'):
   harm.extend(q for q in topic['source_quotes'] if q not in harm)
 if harm:acknowledgements.append(dict(kind='apology_for_current_inconvenience',source_quotes=harm,instruction='Offer a brief proportionate apology for the current reported inconvenience, even if expression is neutral; do not infer anger or confirmed liability.'))
 praise=[s for s in clauses if re.search(r'感谢|谢谢|满意|认可|lovely|appreciat|thank|working well',s,re.I)]
 if praise:acknowledgements.append(dict(kind='thanks_for_praise',source_quotes=praise,instruction='Thank the customer briefly for the specific kind words, then address their current need.'))
 knowledge=[]
 # Retrieval by content, independent of case and language. Hypotheses are not diagnosis.
 if re.search(r'水箱|water tank|reservoir',source,re.I) and re.search(r'渗|漏|leak',source,re.I):
  visual_checks=[dict(key=k,instruction=text,status='ALREADY_REPORTED_DONE' if k in completed else 'REMAINING_VISUAL_CHECK') for k,text in [('tank_seating','Tank correctly seated according to the actual manual.'),('seal_cleaning','Seal contact surface clean and flat.'),('visible_seal_damage','Visually check seal aging, deformation or damage without dismantling.'),('visible_tank_seams','Visually check tank body/seams for cracks.'),('leak_location','Observe the reported leak location without powered testing.')]]
  knowledge.append(dict(topic='water reservoir',source='Owner professional-help policy 2026-11-04; manufacturer example https://www.usa.philips.com/c-t/XC000004110/my-philips-espresso-machine-is-leaking',advice='Possible checks only while unplugged, without dismantling. Acknowledge already reported operations; do not prescribe them again. A seal check is not a diagnosis. Persistent leaks need qualified inspection and eligibility verification. Confirm actual brand/model/manual.',checks=visual_checks))
 if re.search(r'磕|破损|crush|dent|damaged',source,re.I):
  advice='Offer a proportionate apology. Keep packaging and existing photos; ask to share photos merely taken, check receipt if reported sent. Ask for missing order proof only. Check repair/replacement and logistics handling, do not establish cause or guarantee entitlement.'
  if re.search(r'电源|电器|电线|插头|通电|电池|electrical|powered|battery|power (?:cord|supply)|plug\b',source,re.I):
   advice+=' For damaged electrical equipment do not power on before qualified assessment.'
  knowledge.append(dict(topic='damage',source='Owner service/safety policy',advice=advice))
 if DEADLINE.search(source):
  knowledge.append(dict(topic='deadline',source='Owner service policy',advice='Use the stated date without asking the customer to repeat it. For a time-critical correction, check the proof and feasible remake or collection timing before the deadline. Where useful, suggest a customer-controlled interim option such as using an unpersonalised substitute for the occasion. Availability and timing require confirmation.'))
 if re.search(r'费用|收费|charge|fee',source,re.I):
  knowledge.append(dict(topic='billing',source='Owner service policy',advice='Verify the actual line item, charging basis and whether explained/agreed before payment. A receipt photo may help; do not assume charge lawful/incorrect or introduce unrelated refund approval disclaimers.'))
 if re.search(r'床笠|fitted sheet|pocket depth|被套|duvet',source,re.I):
  knowledge.append(dict(topic='dimensional fit',source='Dimensional reasoning; actual product specifications remain unverified',advice='Length/width and fitted-sheet pocket depth are independent. If mattress footprint matches but pocket is too shallow, check a deeper-pocket product with the same footprint; increasing length/width alone does not solve depth. Size mismatch can explain excess duvet fabric but cannot rule out a manufacturing defect. Identify the model and depth from any available authorized order record first. Verify actual SKU dimensions and availability before naming a specific replacement. Ask for one missing reference only if needed.'))
 if re.search(r'办公椅|电脑椅|desk chair|office chair|armrest clearance|扶手净空',source,re.I):
  knowledge.append(dict(topic='chair and desk clearance',source='HSE workstation guidance https://www.hse.gov.uk/Msd/dse/good-posture.htm and OSHA desk guidance https://www.osha.gov/etools/computer-workstations/components/desks (checked 2026-11-10)',advice='Ask for the chair model and verify its seat-height range and floor-to-armrest height at the intended setting. Compare the armrests with actual clearance below the desk, including any apron or drawer, not the desktop height alone. In general the seat supports the thighs with space below the desk and relaxed shoulders at the working surface. Do not put thighs at desktop level or infer individual fit from one dimension.'))
 if re.search(r'洗标|care (?:label|symbol)|fibre|colour transfer|染',source,re.I):
  transfer = bool(re.search(r'蹭染|染蓝|串色|颜色转移|colour transfer|color transfer|transferred colour|transferred color',source,re.I))
  advice = 'Ask for a clear complete care label and relevant fibre composition. Ask about washing or drying only if the customer already treated the item and it matters. Explain only a symbol the customer described. A circle inside a square identifies tumble-drying instructions. It does not by itself establish permission. Dots show heat settings and a confirmed cross means do not tumble dry. If the symbol is undescribed or unreadable, ask for a legible label and defer treatment advice.'
  if transfer:
   advice += ' Obtain both materials and care labels, preserve both items, and pause cleaning until material-specific guidance is verified.'
  knowledge.append(dict(topic='care verification',source='GINETEX care symbols; actual label/manual not supplied',advice=advice))
 if re.search(r'徒步鞋|hiking (?:boot|shoe)',source,re.I):
  knowledge.append(dict(topic='hiking fit',source='REI general fitting guide https://www.rei.com/learn/expert-advice/hiking-boots.html checked 2026-11-09; not this product specification',advice='First request specific model/link and actual size/width chart. General fitting advice only: try intended hiking socks, allow toe movement and check heel hold and side pressure; feet may swell during the day. A generic rule of thumb is not a guaranteed size or a substitute for brand chart or in-person fit.'))
 if re.search(r'礼品卡|gift card',source,re.I):
  knowledge.append(dict(topic='stored value',source='Owner privacy and billing verification policy',advice='Check activation and transaction entries and display discrepancy without blaming another person. Ask for redacted receipt/transaction time or a non-secret reference; never full card back/PIN. A secure channel must be verified through official contact details before sensitive information. Do not discuss physical repair.'))
  if re.search(r'安全渠道|安全通道|secure channel',source,re.I):
   knowledge.append(dict(topic='customer chosen secure intake',source='Explicit current customer channel constraint',advice='Keep the offered partial card reference in the verified official secure channel. Do not ask for the last-four characters by replying to this email. First verify the authorized secure route through the official contact on the existing site/order/receipt; no made-up URL or phone. A separate redacted transaction/order reference may be requested here only if not restricted by the customer.'))
 if re.search(r'取件码|柜机|快递柜|locker',source,re.I):
  knowledge.append(dict(topic='locker access',source='Owner privacy and unverified operator-policy boundary',advice='Ask operator to verify reissue, expiry/extension and any fees using its official contact on the cabinet/order; no confirmed app button, routing promise or extension exists. Respect attempted steps. Ask only order/tracking reference and locker location, never pickup code. Preserve timestamp/report reference; do not mark collected or force open.'))
 if re.search(r'代取|自提|取货凭证|collect.*instead|sister collect|reserved|collection (?:email|proof)|proof.{0,45}counter',source,re.I):
  advice='Identify the collection store and use one order/reservation reference. Verify minimum proof and holding period when relevant. Discuss delegation only if requested. Never assume alternatives are accepted or ask for ID images by email.'
  if re.search(r'(?:找不到|没收到|未收到|无法显示).{0,15}(?:自提|邮件|凭证)|(?:missing|lost|cannot find|not received).{0,20}collection email|phone.{0,20}(?:broken|dead)',source,re.I):
   advice+=' For the reported missing/unavailable confirmation, check order history on a controlled device or an accessible printout; ask the official store contact whether that evidence is accepted before travel.'
  knowledge.append(dict(topic='collection authorization',source='Owner minimum-data service policy',advice=advice))
 if re.search(r'小票抬头|receipt (?:header|heading|names?)|取货点|collection.*branch',source,re.I):
  knowledge.append(dict(topic='merchant roles',source='Owner attribution policy',advice='Receipt heading is a reported label only; verify seller identity from order/trading details, not the receipt heading alone. Purchase, collection and service targets differ; damage does not prove store-service fault or liability.'))
 relay_requested=bool(relay_quotes(source))
 labels={'aftersales_request':('售后核实','aftersales verification'),'store_service_request':('表扬转达' if relay_requested else '门店服务','thanks relay' if relay_requested else 'store service'),'billing_request':('收费核查','billing verification'),'logistics_followup':('物流核查','logistics verification'),'human_input_request':('产品咨询','product inquiry')}
 progress=[]
 for t in tasks:
  zh,en=labels.get(t['kind'],('内部核实','internal verification'))
  progress.append(dict(event_id=t['event_id'],kind=t['kind'],state=t['status'],goal=t['goal'],may_say_zh=f'已创建{zh}请求，待处理。',may_say_en=f'An internal {en} request has been created and is pending.',unverified_outcomes=['staff acceptance or start','external recipient/delivery','investigation result','callback schedule','completion'],instruction='This is one pending internal receipt. Conditions in its goal do not create additional requests.'))
 resolved=[i['object_name'] for i in (analysis or {}).get('issues',[]) if i['resolution']=='resolved']
 current_verification=any(t['kind']!='store_service_request' for t in tasks) or any(i['resolution']=='unresolved' and i['experience_polarity']=='negative' for i in (analysis or {}).get('issues',[]))
 intake=dict(order_reference='Ask for missing order reference or purchase proof only for the actual unresolved verification; never for praise/thanks relay.',photos='Use attachment_evidence source states. Ask conditionally for useful missing evidence; never ask again for reported sent files.',permission='Customer may reply with relevant details; no guaranteed visit availability.') if current_verification else dict(order_reference='NOT_APPLICABLE. Do not request order information, purchase proof, receipt, invoice or serial number for praise/thanks relay.',photos='NOT_APPLICABLE for resolved praise.',permission='Do not add future help, recurrence or callback disclaimers. Close with warm thanks and a wish. Existing relay task is pending; no personal promise to deliver.')
 return dict(version=VERSION,current_objectives=[q for i in (analysis or {}).get('issues',[]) for q in i['customer_requests']],resolved_matters=resolved,acknowledgements=acknowledgements,completed_steps=completed,feedback_relay=dict(requested=relay_requested,source_quotes=relay_quotes(source),instruction='Only thank praise when no relay was requested; do not add a relay promise or claim.'),reply_focus='Only current objectives. If product issue is resolved, thank and wish pleasant use; omit recurrence advice. No promise to reply/contact later. Give customer-controlled next steps instead.',paragraph_topics=['acknowledgement','current questions and useful advice','supported pending progress and customer next step'],paragraph_rule='Combine naturally for simple cases; keep independent questions and their pending checks distinct. No fixed paragraph count.',pending_progress=progress,evidence_intake=intake,knowledge=knowledge,service_checks=checks,attachment_manifest=runtime.get('attachment_manifest',[]),unknown_merchant_facts=['payment obligations/fee waivers','refund or exchange entitlement','inspection availability','staff acceptance','callback schedule'],permitted_closing='Thank customer; wish pleasant use where appropriate. Invite customer to provide missing information or ask for progress. Do not commit staff to future contact.',execution_scope='LOCAL_SIMULATION_PENDING; no external action',attitude='Apologize proportionately for actual harm even with neutral expression; thank praise; no unsolicited warnings about resolved faults.')

def composition_brief(email,runtime,analysis=None):
 guidance=brief(email,runtime,analysis)
 from src.application.source_facts import page_jump_facts
 page_jumps = page_jump_facts(email)
 if page_jumps:
  guidance['source_page_observations'] = dict(jumps=page_jumps, instruction='Describe the reported jump literally. The two observed endpoints do not belong in a missing-page range.')
 # Classification constraints select the review route; they are not a customer
 # remedy and should not become an objective narrated in the reply.
 guidance['current_objectives']=[q for q in guidance['current_objectives'] if not re.search(
     r'(?:请别|不要|不应|别把|不把).{0,35}(?:算成|记为|视为|归为|归类|分类).{0,15}(?:投诉|服务)|do not (?:count|classify|record).{0,50}(?:complaint|category)',q,re.I)]
 from src.application.service_plan import dimension_comparison
 planning=runtime.get('service_plan')
 if planning is not None:
  guidance['current_objectives']=[g['goal'] for g in planning['goals']]
  # Constraints govern planning and execution. Do not automatically turn them
  # into reply paragraphs; preserve their full form in runtime for review.
  guidance['service_goals']=[{k:v for k,v in goal.items() if k!='preserve_constraints'} for goal in planning['goals']]
  guidance['customer_reported_facts']=planning.get('customer_reported_facts',[])
  guidance['service_checks'].pop('path_requirements',None)
  guidance['response_priority']='Address each supplied service goal and its applicable response points. State concrete checks, not only pending work. Do not narrate internal classification or record-handling instructions. Keep interim options conditional on unresolved timing, cost and authorization dependencies; never turn a proposed time into an assurance of on-time return or no fee. Ask only the missing minimum lookup key.'
 arithmetic=dimension_comparison(email)
 if arithmetic:guidance['source_dimensional_arithmetic']=arithmetic
 # Select current objectives/resolved context once in brief. Do not duplicate the
 # full analysis (historical faults and tool hypotheses) as competing instructions.
 if not guidance['feedback_relay']['requested']:
  del guidance['feedback_relay']
  if not guidance['pending_progress']:
   guidance['evidence_intake'] = dict(instruction='Thank the customer naturally. Ask for information only if needed to resolve a current service question.')
  elif guidance['evidence_intake']['order_reference'].startswith('Ask for missing'):
   guidance['evidence_intake']['order_reference'] = 'Ask for one missing lookup reference only if the current verification needs it.'
 else:
  guidance['feedback_relay']['instruction'] = 'Describe the matching pending task only if it appears in pending_progress.'
 facts=guidance['service_checks'].pop('verified_facts',[])
 known_orders = []
 for fact in facts:
  for reference in re.findall(r'(?i:\border(?:\s+(?:number|reference|ID))?|订单(?:号|编号)?)\s*[:：#]?\s*([A-Z]{1,5}-\d{2,10})(?![A-Za-z0-9])',fact['conclusion']):
   known_orders.append(dict(reference=reference,source_id=fact['source_id'],topic=fact.get('topic')))
 if known_orders:
  guidance['evidence_intake']['known_order_references'] = known_orders
  guidance['evidence_intake']['order_reference'] = 'Use these scoped existing order references in the verification or official-channel instruction. No request to send them again in this email.'
 return dict(authorized_case_facts=facts,**guidance)

def chain_messages(email,runtime,analysis=None):
 from src.application.source_facts import attachment_facts
 payload=dict(customer=email.model_dump(),service_brief=composition_brief(email,runtime,analysis),attachment_evidence=attachment_facts(email,runtime.get('attachment_manifest',[])))
 return [('system',SYSTEM),('human',json.dumps(payload,ensure_ascii=False))]
def identity():return dict(version=VERSION,system_hash=digest(SYSTEM),planner_hash=digest(PLANNER_SYSTEM))

def audit_reply(email,reply,runtime):
 from src.application.reply_quality_checks import review
 return review(email,reply,runtime,current_receipts(email,runtime),
               relay_requested=bool(relay_quotes(email.subject+'\n'+email.body)))

def quality(run,data,reply,accepted):
 """Same action-evidence assessment in the R6 product and evaluation views."""
 from src.application.p5b8_product import quality as inherited_quality
 from src.application.p5b8r1_guard import calibrate
 from src.application.p5b8r3_final_guard import assess
 from src.evaluation.p5b8r3_judge import bind
 identity=dict(case_id=run.email.email_id,run_id=run.run_id,arm=run.config.parameters.get('arm','GUIDED'),input_hash=run.input_hash)
 runtime=copy.deepcopy(run.metadata['runtime'])
 raw=runtime.get('events',[])
 # Existing bindings are validated; never strip them to relabel a foreign arm.
 if any('_binding' in e for e in raw):
  from src.evaluation.p5b8r3_judge import validate_slot
  validate_slot(dict(identity,parse_ok=True,reply=reply or '',events=raw),run.email)
 else:runtime['events']=bind(raw,**identity)
 runtime.update(identity=dict(identity,conversation_id=run.email.email_id),strict_identity=True,future_intent_policy='owner-nonrigid-v1')
 prior=inherited_quality(run,data,reply,accepted)
 result=calibrate(prior,reply or '',runtime,run.input_hash,action_audit=assess(reply or '',runtime,run.input_hash))
 from src.application.source_facts import nonasserted_spans,reported_delivery_claim
 spans=nonasserted_spans(reply or '')
 severe=[i for i in (data or {}).get('issues',[]) if i.get('risk_level')=='severe']
 privacy_quotes=source_topics(run.email).get('contact_privacy',[])
 contact_only=bool(severe and all(
  i['business_process']=='customer service response issue' and any(
   e.get('quote') and any(e['quote'] in q or q in e['quote'] for q in privacy_quotes)
   for e in i.get('risk_evidence',[]))
  for i in severe))
 physical_risk=re.search(r'受伤|伤害|触电|冒烟|起火|漏电|灼伤|断裂|危险|injur|hurt|shock|smoke|fire|burn|spark|danger|unsafe',
                         run.email.subject+'\n'+run.email.body,re.I)
 kept=[]
 for f in result['findings']:
  q=f.get('quote','');start=(reply or '').find(q)
  scoped=q and start>=0 and any(a<=start and start+len(q)<=b for a,b,_ in spans)
  reported=reported_delivery_claim(reply or '',q,run.email)
  if f.get('code') in ('H04','executed_action') and (scoped or reported):
   result.setdefault('exclusions',[]).append(dict(f,reason_r8='Source-bound report/quotation/condition, not application execution',source_report=reported));continue
  if contact_only and not physical_risk and f.get('code') in ('risk_urgency_conflict','missing_stop_use_advice','severe_safety_review'):
   result.setdefault('exclusions',[]).append(dict(f,reason_r8='The source-bound severe concern is contact privacy; preserve the privacy review without imposing a physical stop-use instruction.'));continue
  if f.get('code')=='unavailable_future_action' and re.fullmatch(r'(?:we|I) can (?:check|investigate)|(?:我们|客服)(?:可以|能)核查',q,re.I):
   tail=re.split(r'[。！？.!?\n；;]',(reply or '')[start+len(q):],maxsplit=1)[0]
   execution=r'\b(?:and|then|will)\s+(?:send|contact|call|book|charge|refund|reply)\b|(?:再|并|就|将)(?:发送|联系|预订|收费|退款|回访)'
   if not re.search(execution+r'|\btomorrow\b|\bwithin\s+\d|明天|小时内',tail,re.I):
    result.setdefault('exclusions',[]).append(dict(f,reason_r8='A bounded offer to check is a proposal, not an external execution or guaranteed follow-up.'));continue
  kept.append(f)
 if contact_only and not physical_risk:
  review=dict(code='CONTACT_PRIVACY_REVIEW',severity='review',scope='analysis',
              quote=privacy_quotes[0],reason='Verify the authorized order contact without collecting third-party details.')
  kept.append(dict(review,finding_id=digest(review)))
 result['findings']=kept
 result['status']='blocked' if any(f['severity']=='block' for f in kept) else 'review_required'
 from src.application.source_facts import attachment_claim_audit
 extra=attachment_claim_audit(reply or '',run.email,runtime.get('attachment_manifest',[]))['findings']
 result['findings'].extend(extra)
 additional=audit_reply(run.email,reply or '',runtime)
 result['findings'].extend(dict(f,finding_id=digest(f)) for f in additional['findings'])
 result['service_review']=additional
 if extra or any(f['severity']=='block' for f in additional['findings']):result['status']='blocked'
 return result
