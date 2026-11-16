"""Preserve inherited gates; scope each independent action predicate."""
import re
from src.application.p5b8r2_guard import assess as previous
VERSION='p5b8r3-predicate-scope-1'
def assess(reply,runtime,h):
    # Each conjunct must be checked: an early negation or supported task cannot
    # hide a later unsupported assertion in the same sentence.
    text=re.sub(r'(?<=[，,])\s*(?=并|且|但|and\b)|(?:并且|而且)|\band\s+(?=(?:I|we|have|has|already)\b)', '\n',reply,flags=re.I)
    out=previous(text,runtime,h)
    # Quotes must stay exact source substrings, including reports and Judge input.
    for group in ('assessments','findings'):
        out[group]=[a for a in out[group] if a['quote'] in reply]
    out['version']=VERSION;return out
