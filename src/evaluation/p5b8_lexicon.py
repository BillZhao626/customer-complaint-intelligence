"""Original bilingual word baseline v2, separate from the frozen LLM prompts."""
import re
from src.application.p5b8_pipeline import POS,NEG
VERSION='p5b8-original-lexicon-2'
def predict(text):
    text=text.lower();hits=[];occupied=set();matches=[]
    for t,p in [(x,1) for x in POS+['好','赞美','满意度高']]+[(x,-1) for x in NEG+['差','不耐烦','慢得离谱']]:
        for m in re.finditer(re.escape(t),text):matches.append((m.start(),m.end(),t,p))
    for s,e,t,p in sorted(matches,key=lambda x:-(x[1]-x[0])):
        if any(k in occupied for k in range(s,e)):continue
        if t.isascii() and ((s and text[s-1].isalpha()) or (e<len(text) and text[e].isalpha() and t not in ('frustrat','thank'))):continue
        occupied.update(range(s,e));before=text[max(0,s-18):s]
        neg=bool(re.search(r'(?:没有|并非|不是|不|没|not |no |never )\s*$',before));score=-p if neg else p
        if neg and p<0:score=0
        # Do not turn a courtesy closing into substantive positive feedback.
        courtesy=t in ('谢谢','感谢','thank') and bool(re.search(r'(谢谢[。！!\s]*$|thanks?[.!\s]*$|thank you[.!\s]*$)',text[s:]))
        if courtesy:score=0
        w=2 if re.search(r'但是|然而|但|but |however',before) else 1
        hits.append(dict(quote=text[s:e],start=s,end=e,score=score*w,negated=neg,courtesy=courtesy))
    pos=any(h['score']>0 for h in hits);neg=any(h['score']<0 for h in hits);total=sum(h['score'] for h in hits)
    return dict(version=VERSION,expressed_sentiment='mixed' if pos and neg else 'positive' if pos else 'negative' if neg else 'neutral',legacy_three='negative' if total<0 else 'positive' if total>0 else 'neutral',hits=hits)
