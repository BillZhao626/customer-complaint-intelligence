from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from review import EVIDENCE, create_review, read
class ReplyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.replies = []
        self.in_reply = False
    def handle_starttag(self, tag, attrs):
        if tag == 'p' and dict(attrs).get('class') == 'reply':
            self.replies.append('')
            self.in_reply = True
    def handle_endtag(self, tag):
        if tag == 'p':
            self.in_reply = False
    def handle_data(self, data):
        if self.in_reply:
            self.replies[-1] += data
def verify():
    with TemporaryDirectory(prefix='complaint-review-check-') as directory:
        with TestClient(create_review(Path(directory)/'qa.sqlite3')) as client:
            assert client.get('/').status_code == 200
            assert client.get('/api/review/health').json()['paid_enabled'] is False
            headers = {'x-p5-token':client.get('/api/session').json()['token']}
            rows = {r['case_id']:r for r in client.get('/api/r8/quality').json()['cases']}
            assert len(rows) == 5
            assert client.get('/api/review/health').json()['replays'] == 14
            assert rows['R7H-012']['events']
            for case_id, code in [('R11OG-06-en','UNVERIFIED_SYNC_MUTATION'),
                                  ('R7H-015','SENSITIVE_EMAIL_INTAKE')]:
                route = '/api/cases/' + rows[case_id]['product_case_id']
                detail = client.get(route).json()
                assert detail['quality']['status'] == 'blocked'
                assert code in {f['code'] for f in detail['quality']['findings']}
                assert 'approve' not in detail['allowed_actions']
                if detail['triage']['requires_takeover']:
                    response = client.post(route+'/actions', headers=headers, json=dict(
                        action='take_over', revision=detail['revision'],
                        operation_id='takeover-'+case_id, reason='Offline verification'))
                    assert response.status_code == 200
                    detail = client.get(route).json()
                response = client.post(route+'/actions', headers=headers, json=dict(
                    action='approve', revision=detail['revision'], operation_id='approve-'+case_id,
                    reason='Offline verification',
                    checks=dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True)))
                assert response.status_code == 409
            response = client.post('/api/p5b5r2/live', headers=headers, json=dict(
                subject='Synthetic', body='Closed route test.', synthetic_confirmed=True,
                operation_id='live-closed-test'))
            assert response.status_code == 409
            data = client.get('/api/research/insights?source=b8-r5-audited').json()
            for group, metric in [('product_category','negative'),('store_location','complaints')]:
                metric = next(r[metric] for r in data['groups'][group] if r[metric]['member_ids'])
                member = client.get('/api/research/member',
                    params=dict(source='b8-r5-audited', member_id=metric['member_ids'][0])).json()
                assert member['email']['body'] and member['run_id'] == metric['member_ids'][0]
            result = client.get('/api/research/classification').json()['reports'][0]['fields']['sentiment']
            assert (result['correct'], result['n']) == (78, 80)
            data = client.get('/api/research/insights?source=b8-r6-policy').json()
            rows = {r['values']['store_location']: (r['complaints']['numerator'],r['complaints']['denominator'])
                    for r in data['groups']['store_location']}
            assert rows['Wenzhou Lucheng Store'] == (2,11)
            assert rows['Nanjing Xinjiekou Store'] == (0,6)
            assert sum(n>0 for n,_ in rows.values()) == 3
            for key in ['p10-alt','p16']:
                response = client.get('/portfolio/cases/'+key, follow_redirects=False)
                assert response.status_code == 307
            comparison = read(EVIDENCE/'portfolio-praise-comparison.json')
            assert comparison['replies'][1]['body'] == read(EVIDENCE/'portfolio/p10.json')['slot']['reply']
            saved = read(EVIDENCE/'portfolio-case-metrics.json')['case']
            compare = client.get('/portfolio/yoga')
            assert compare.status_code == 200 and '售后核查待处理' in compare.text
            parsed = ReplyParser()
            parsed.feed(compare.text)
            assert parsed.replies == [row['reply'] for row in saved['replies']]
            for row in saved['replies']:
                key = 'yoga-' + row['key']
                redirect = client.get(f'/portfolio/cases/{key}', follow_redirects=False)
                assert redirect.status_code == 307
                c = redirect.headers['location'].split('=',1)[1]
                route = '/api/cases/' + c
                before = client.get(route).json()
                assert before['draft']['body'] == row['reply']
                assert before['state'] not in ('approved', 'simulated_sent')
                detail = client.get('/api/p5b5r2/cases/' + c).json()
                assert detail['timeline'][0]['body'] == saved['email']
                assert any(e['kind']=='aftersales_request' and e['status']=='created'
                           for e in detail['local_events'])
                assert row['review'] in compare.text
            # Saving a local edit creates a new revision. The historical
            # comparison and its evaluation continue to refer to the original.
            assert 'save_edit' in before['allowed_actions']
            saved_edit = client.post(route+'/actions', headers=headers, json=dict(
                action='save_draft', revision=before['revision'],
                operation_id='qa-edit', body=before['draft']['body']+'\n\nOffline local review edit.'))
            assert saved_edit.status_code == 200
            current = client.get(route).json()
            assert current['current_version'] == before['current_version'] + 1
            assert client.get('/portfolio/yoga').text == compare.text
            assert 'request_changes' in current['allowed_actions']
            rejected = client.post(route+'/actions', headers=headers, json=dict(
                action='request_changes', revision=current['revision'],
                operation_id='qa-return', reason='演示退回修改'))
            assert rejected.status_code == 200
    print('Packaged API, classification, member evidence, reply review and closed live route verified.')
if __name__ == '__main__':
    verify()
