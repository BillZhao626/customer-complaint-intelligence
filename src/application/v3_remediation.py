"""Deterministic derived views, never mutation or a new model prediction."""
from src.domain.analysis_v3 import AnalysisV3, stored_analysis, to_v2
from src.domain.contracts import digest
from pathlib import Path
from hashlib import sha256

RULE_VERSION='p37-derived-view-2'
HANDLING_POLICY='product-before-store-v1'
HANDLING_BASIS='P3.5 owner operational decision: inspect product damage before rescheduling store service; not customer preference'


def order_equal_ties(value, policy=None):
    if policy not in (None,HANDLING_POLICY):raise ValueError('Unapproved/unknown handling policy')
    if policy is None:return value,[],['No explicit handling policy; model order preserved']
    active=[i for i in value.issues if i.issue_kind=='complaint' and i.resolution=='unresolved']
    rank={'product issue':0,'store service issue':1}
    groups={}
    for i in active:
        if i.handling_priority is not None:groups.setdefault(i.handling_priority,[]).append(i)
    changes=[];notes=[];ordered=[]
    # Missing priorities or any unresolved tie leave all operational ranks intact.
    if len(active)!=sum(len(g) for g in groups.values()):
        return value,[],['Missing handling order; explicit policy cannot infer a complete plan']
    for priority,group in sorted(groups.items()):
        if len(group)==1:ordered+=group;continue
        if any(i.customer_importance!='equal' or i.business_process not in rank for i in group):
            return value,[],['Tie outside approved equal/product/store scope; researcher policy required']
        keys=[(i.urgency!='high',rank[i.business_process]) for i in group]
        if len(set(keys))!=len(keys):
            return value,[],['Policy cannot distinguish tied processes; no arbitrary ID/text ordering']
        ordered+=sorted(group,key=lambda i:(i.urgency!='high',rank[i.business_process]))
    if not any(len(g)>1 for g in groups.values()):return value,[],['No equal-priority tie; model order preserved']
    # Do not apply a local tie breaker if an earlier low-risk group would hide high risk.
    if any(i.urgency=='high' and any(j.urgency!='high' for j in ordered[:n]) for n,i in enumerate(ordered)):
        return value,[],['Safety order conflict across groups; researcher review required']
    updates={}
    for number,issue in enumerate(ordered,1):
        rationale=HANDLING_BASIS+f'; handling position {number}; responsibility remains unverified'
        updates[issue.issue_id]=dict(handling_priority=number,priority_rationale=rationale)
        for field,new in updates[issue.issue_id].items():
            old=getattr(issue,field)
            if old!=new:changes.append(dict(issue_id=issue.issue_id,field=field,old=old,new=new,reason=HANDLING_BASIS))
    data=value.model_dump()
    data['issues']=[dict(i,**updates.get(i['issue_id'],{})) for i in data['issues']]
    return AnalysisV3.model_validate(data),changes,notes


def derive(run, projection='customer-primary-v2-safe', handling=None):
    original=stored_analysis(run)
    value,changes,notes=order_equal_ties(original,handling)
    value.validate_input(run.email)
    result,diagnostics=to_v2(value,projection)
    payload=dict(kind='DETERMINISTIC_DERIVED_VIEW_NOT_MODEL_RUN',rule_version=RULE_VERSION,
        rule_source_hash=digest({str(p.name):sha256(p.read_text(encoding='utf8').encode('utf8')).hexdigest()
            for p in (Path(__file__),Path(__file__).resolve().parents[1]/'domain/v3_compatibility.py')}),
        parent_run_id=run.run_id,input_hash=run.input_hash,parent_config_hash=digest(run.config.model_dump()),
        parent_output_hash=run.metadata['analysis_v3_hash'],parent_raw_hashes=[digest(a.raw_output) for a in run.attempts],
        projection_policy=projection,handling_policy=handling,policy_basis=HANDLING_BASIS if handling else None,
        analysis=value.model_dump(),analysis_hash=digest(value.model_dump()),projection=result.model_dump(),
        projection_hash=digest(result.model_dump()),changes=changes,diagnostics=notes+diagnostics,
        human_review_status='pending',model_calls=0)
    payload['derived_id']=digest(payload)
    return payload


def verify_derived(run, packet):
    expected=derive(run,packet['projection_policy'],packet['handling_policy'])
    if packet!=expected:raise ValueError('Derived identity/parent/output mismatch')
    return packet
