"""Recompute new research artifacts without API calls or historical writes."""
import os
import sys
import json
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    from src.application.research_insights import ResearchInsights,read_csv
    from src.evaluation.classification_research import build_report
    from src.dataset.research_generation import plan,audit
    catalog=ResearchInsights(ROOT);report=build_report(ROOT,catalog)
    def write(name,data):
        with (out/name).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    write('classification.json',report);write('sources.json',catalog.catalog());write('generation-plan.json',plan())
    for source in catalog.sources:write('insights-'+source+'.json',catalog.snapshot(source))
    emails=read_csv(ROOT/'data/synthetic/customer_emails_full_v1.csv')
    write('generation-comparison.json',dict(status='LIVE_GENERATION_PENDING',template_source='400 records / 55 historical program templates, not LLM-generated',
        template_audit=audit([r['email_body'] for r in emails]),llm_generated=dict(n=0,naturalness=None,diversity=None,classification_difficulty=None),
        conclusion='UNKNOWN: no new paid generation authorized. No comparison improvement claim.',
        human_review=dict(blinded=True,dimensions=['naturalness','coherence','plausible_information_omission','scenario_fidelity','privacy','diversity'],scores=[0,1,2],reviewers=[],
            rubric='0: implausible or contradictory; 1: plausible but formulaic/awkward; 2: ordinary coherent customer wording; no prefilled ratings.',
            selection='First review one per 55 historical template families and all 9 proposed generated cells; compare by language/scenario. Disagreements adjudicated, exclusions logged.')))
    print(json.dumps({'output':str(out),'sources':len(catalog.sources),'reports':len(report['reports']),'overlap':report['overlap']['n'],'new_paid_calls':0}))


if __name__=='__main__':main()
