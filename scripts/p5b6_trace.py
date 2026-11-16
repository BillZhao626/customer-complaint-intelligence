"""Real LangChain SDK, strictly MockTransport, saved response replay; zero inference."""
import argparse
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    import httpx
    from importlib.metadata import version
    from src.application.p5b3_runtime import Analyzer
    from src.application.analysis_service import AnalysisService
    from src.application.product_workflow import ProductStore
    from src.domain.contracts import AnalysisRun,digest
    from src.infrastructure.v3_live_settings import V3PilotSettings
    from src.infrastructure.pilot_budget import PilotBudget
    from src.infrastructure.repository import Repository
    from src.application.research_insights import file_hash
    source=ROOT/'.local/p5b5r2/R3/CAL-08-T1'
    original=AnalysisRun.model_validate_json((source/'run.json').read_text(encoding='utf-8'))
    frozen=json.loads((source/'frozen-input.json').read_text(encoding='utf-8'))
    if digest(frozen['messages'])!=original.config.parameters['messages_hash']:raise ValueError('Historical messages mismatch')
    requests=[]
    def respond(request):
        data=json.loads(request.content);requests.append(data)
        from src.application.p39_experiment import wire_payload
        if str(request.url)!='https://api.deepseek.com/chat/completions' or data!=wire_payload([tuple(m) for m in frozen['messages']]):raise ValueError('Wire mismatch')
        return httpx.Response(200,json=dict(id='offline-saved-response-replay',object='chat.completion',created=1,model='deepseek-flash',
            choices=[dict(index=0,message=dict(role='assistant',content=original.attempts[0].raw_output),finish_reason='stop')],
            usage=dict(prompt_tokens=100,completion_tokens=100,total_tokens=200)))
    analyzer=Analyzer(V3PilotSettings('offline-placeholder-no-secret',True,max_tokens=4000,max_attempts=1),out,mock_http_transport=httpx.MockTransport(respond))
    analyzer.messages=lambda email,repair=False:[tuple(m) for m in frozen['messages']]
    analyzer.config=original.config.model_copy(update=dict(parameters=dict(original.config.parameters,product_transport='offline_mock_http',experiment='p5b6-sdk-replay')))
    class MockOnlyBudget(PilotBudget):
        def reserve(self,run_id,attempt_no,input_hash,messages,max_tokens):
            # This fixture cannot reserve a real provider call. No historical
            # authorization or pricing limits are changed or borrowed.
            if not isinstance(analyzer.mock_http_transport,httpx.MockTransport) or analyzer.provider is not None or input_hash!=original.input_hash or attempt_no!=1:
                raise ValueError('MockTransport fixture only')
            with self.connection() as c:
                if c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]:raise ValueError('Single mock request only')
                c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(run_id,1,input_hash,0.,'OFFLINE_REPLAY'))
            return 0.
        def estimate_cost(self,metadata):return 0.
    budget=MockOnlyBudget.create(out/'offline-fixture-budget.sqlite3',[original.input_hash],dict(config=analyzer.config.model_dump(),identity='MOCK_ONLY_NO_PAID_AUTHORIZATION'))
    repo=Repository(out/'analysis.sqlite3');run=AnalysisService(repo,analyzer,budget=budget).analyze(original.email)
    budget.halt('OFFLINE_REPLAY_COMPLETED')
    product=ProductStore(ROOT/'.local/p4'/('p5b6-sdk-'+out.name)/'product.sqlite3')
    case=product.create(run,'P5-B6 SDK MockTransport replay of saved R3 output')
    report=dict(identity='CURRENT_LANGCHAIN_SDK_MOCK_HTTP_SAVED_RESPONSE_REPLAY_NOT_NEW_INFERENCE',new_paid_calls=0,mock_http_requests=len(requests),
        status=run.status,input_hash=run.input_hash,run_id=run.run_id,case_id=case['case_id'],source_run_id=original.run_id,
        dependencies={k:version(k) for k in ('langchain','langchain-core','langchain-openai','pydantic','httpx')},
        historical_files={str(p.relative_to(ROOT)):file_hash(p) for p in source.glob('*') if p.is_file()},
        raw_equal=run.attempts[0].raw_output==original.attempts[0].raw_output,result_equal=run.result==original.result,
        stages=[dict(stage=a.stage,parse=a.parse_status,contract=a.contract_status,normalization=a.normalization_status,business=a.business_status) for a in run.attempts],
        product_state=case['state'],reply_present=bool(case['draft']),reloaded_equal=repo.get(run.run_id)==run,
        original_dispatch=original.attempts[0].metadata.get('dispatch'),model_snapshot='unavailable',
        module_path=['p5b5r2_pipeline.messages / frozen messages','p5b3_runtime.Analyzer.request','deepseek.DeepSeekAnalyzer.make_client','langchain_openai.ChatOpenAI.ainvoke','httpx.MockTransport for this replay; historical DeepSeek for original','AnalysisService + project validators','Repository SQLite','ProductStore draft/review','research_insights deterministic aggregation'])
    (out/'run.json').write_text(run.model_dump_json(indent=2),encoding='utf-8')
    (out/'TRACE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('identity','new_paid_calls','mock_http_requests','status','raw_equal','result_equal','reply_present','reloaded_equal')}))
    return int(run.status!='succeeded' or len(requests)!=1 or not report['result_equal'])


if __name__=='__main__':sys.exit(main())
