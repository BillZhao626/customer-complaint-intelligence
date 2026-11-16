"""Narrow extensions: explicit current deadline and reported prior service failure."""
import re
from src.application.urgency_context_v1 import signals as old_signals, visible, active_clauses, positive

def signals(text, *, already_visible=False):
    d=old_signals(text,already_visible=already_visible)
    masked=text if already_visible else visible(text)
    for c in active_clauses(masked):
        # Near-term use + affirmative necessity; a date mention or refusal alone is insufficient.
        if positive(c,r'(?:明天|明日|今晚|今天).{0,8}(?:要|必须|需要)(?:送人|送礼|用|使用)|(?:必须|务必|需要).{0,12}(?:明天|明日|今晚|今天)(?:前|之前|使用|送人)|\b(?:need|must|have to).{0,35}(?:tomorrow|tonight|today)\b'):
            d['deadline'].append(c.strip())
        prior=re.search(r'前面|此前|之前|一直|多次|反复|\bprevious|\bagain|\brepeated',c,re.I)
        failure=re.search(r'没人看|没人处理|未解决|没.{0,5}解决|无效|自动回复|no one.{0,10}(?:read|help)|not resolved|automated repl',c,re.I)
        if prior and failure and not re.search(r'已解决|现在解决|now resolved',c,re.I):
            d['repeated_failure'].append(c.strip())
    return d
