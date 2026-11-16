"""Live thread continuation reuses existing immutable thread links and review gates."""
import json
from src.application.mail_threads import MailThreads,assemble_context
from src.application.product_workflow import Conflict,timestamp
from src.application.p5b3_runtime import generate
from src.application.p5b3_actions import journal
from src.domain.contracts import EmailInput,digest

def follow_up(store,parent_id,body):
    parent=store.get(parent_id)
    if not parent or not parent['receipt'] or parent['state']!='simulated_sent' or parent['quality']['status']=='blocked':
        raise Conflict('先完成前轮审核与模拟；分析阻断不能绕过')
    threads=MailThreads(store); subject='Re: '+parent['run'].email.subject
    current=dict(subject=subject,body=body)
    existing=threads.child(parent_id)
    if existing:
        if threads.link(existing)['current']!=current:raise Conflict('已有后续消息')
        return store.get(existing)
    messages=threads.messages(parent_id); h=digest(messages)
    email=EmailInput(email_id='b3-thread-'+digest(dict(parent=parent_id,**current))[:24],subject=subject,body=assemble_context(messages,subject,body))
    case=generate(email,stage='ui-followup',candidate=True,store=store,context_hash=h)
    with threads.connect() as c:
        c.execute('INSERT INTO thread_links VALUES(?,?,?,?,?,?,?,?)',(case['case_id'],parent_id,json.dumps(messages,ensure_ascii=False),h,json.dumps(current,ensure_ascii=False),digest(current),digest(parent['receipt']),timestamp()))
    return case

def continue_with_knowledge(store,case_id):
    parent=store.get(case_id)
    if not parent:raise KeyError(case_id)
    tasks=journal(store).list(parent['run'].input_hash)
    notes=[e['payload'] for t in tasks for e in t['events'] if e['kind']=='knowledge_supplied']
    if not notes:raise ValueError('No scoped knowledge supplement')
    email=parent['run'].email.model_copy(update=dict(email_id=parent['run'].email.email_id+'-knowledge-'+digest(notes)[:12]))
    return generate(email,stage='ui-knowledge',candidate=True,store=store,extra_runtime=dict(scoped_facts=notes,knowledge_parent_run=parent['run'].run_id))
