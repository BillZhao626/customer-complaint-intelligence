"""R2 business paths: explicit synthetic requests, temporary stores, zero model calls."""
from pathlib import Path
import os
import socket
import tempfile
import unittest
from unittest.mock import patch

from src.application.p5b5r2_pipeline import (
    ConversationState, ConversationStore, ActionStore, LocalFacts, plan, messages,
)
from src.domain.contracts import EmailInput


def state(*texts, conversation='fixture-r2'):
    result = ConversationState(conversation)
    for text in texts:
        result.update('customer', text)
    return result


def active(events):
    return [e for e in events if e['status'] in {'created', 'handoff_pending', 'executed'}]


class P5B5R2ActionTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, dict(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false',
                                                       LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'))
        self.environment.start()
        self.addCleanup(self.environment.stop)
        def no_network(*args, **kwargs):
            raise AssertionError('R2 business fixture tests prohibit network access')
        for attribute in ('connect', 'connect_ex'):
            guard = patch.object(socket.socket, attribute, no_network)
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(socket, 'create_connection', no_network)
        guard.start()
        self.addCleanup(guard.stop)

    def test_known_lookup_is_scoped_and_carried_to_generation_context(self):
        with tempfile.TemporaryDirectory() as directory:
            s = state('查订单DEMO-TEST-21的包裹物流。')
            email = EmailInput(email_id='fixture-known', subject='物流', body=s.customers)
            fact = dict(input_hash=email.input_hash, kind='logistics_lookup', authority='AUTHORIZED_FIXTURE',
                        source_url='fixture://warehouse/21', version='fixture-v1', observed_at='2026-10-30',
                        quote='仓库扫描：已交接待揽收', conclusion='仓库已交接，承运商尚无揽收确认')
            runtime = ActionStore(Path(directory)/'actions.db').execute(s, email.input_hash, facts=LocalFacts([fact]))
            look = next(e for e in runtime['events'] if e['kind'] == 'logistics_lookup' and e['status'] == 'executed')
            self.assertEqual(look['payload']['result']['status'], 'KNOWN')
            self.assertEqual(look['payload']['result']['facts'], [fact])
            self.assertFalse(any(e['kind'] == 'logistics_followup' for e in runtime['events']))
            prompt = '\n'.join(text for _, text in messages(email, runtime))
            self.assertIn('仓库已交接，承运商尚无揽收确认', prompt)
            self.assertFalse(look['payload']['external_execution'])

    def test_unknown_logistics_and_pickup_create_distinct_internal_followups(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = ActionStore(Path(directory)/'actions.db').execute(
                state('包裹物流没动，约好的旧床取件也没来。订单DEMO-TEST-22。'), 'fixture-unknown')
            created = {e['kind']: e for e in runtime['events'] if e['status'] == 'created'}
            self.assertIn('logistics_followup', created)
            self.assertIn('pickup_followup', created)
            self.assertEqual(created['logistics_followup']['payload']['action']['owner'], 'logistics')
            self.assertEqual(created['pickup_followup']['payload']['action']['owner'], 'collection_service')
            for event in runtime['events']:
                if event['status'] == 'executed':
                    self.assertEqual(event['payload']['result']['status'], 'UNKNOWN')
                    self.assertFalse(event['payload']['external_execution'])

    def test_identical_request_reopened_store_does_not_duplicate_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'actions.db'
            s = state('请查物流，订单DEMO-TEST-23。')
            before = ActionStore(path).execute(s, 'stable-input')
            after = ActionStore(path).execute(s, 'stable-input')
            self.assertEqual(before, after)
            self.assertEqual(len({e['event_id'] for e in after['events']}), len(after['events']))
            self.assertEqual(ActionStore(path).list('other-input'), [])

    def test_cross_input_and_unapproved_facts_never_become_known(self):
        action = {'kind': 'logistics_lookup'}
        other = dict(input_hash='other-input', kind='logistics_lookup', authority='AUTHORIZED_FIXTURE',
                     source_url='fixture://other', version='v1', observed_at='2026-10-30', quote='other data')
        self.assertEqual(LocalFacts([other]).lookup(action, 'this-input')['status'], 'UNKNOWN')
        bad = dict(other, input_hash='this-input', authority='UNAPPROVED_NOTE')
        with self.assertRaises(ValueError):
            LocalFacts([bad]).lookup(action, 'this-input')

    def test_lookup_failure_has_failed_receipt_without_execution_claim(self):
        class FailedFacts:
            def lookup(self, *args):
                raise TimeoutError('offline fixture')
        with tempfile.TemporaryDirectory() as directory:
            runtime = ActionStore(Path(directory)/'actions.db').execute(state('查物流。'), 'failure-input', facts=FailedFacts())
            self.assertIn('failed', {e['status'] for e in runtime['events']})
            self.assertNotIn('executed', {e['status'] for e in runtime['events']})

    def test_multi_issue_tasks_link_to_their_issue_and_preserve_customer_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            s = state('抽屉滑出来磕腿，周六取旧床没人来，发票漏项。订单DEMO-TEST-24。')
            runtime = ActionStore(Path(directory)/'actions.db').execute(s, 'multi-input')
            ids = {i['issue_id'] for i in runtime['context']['issues']}
            for event in active(runtime['events']):
                action = event['payload']['action']
                self.assertTrue(action['issue_ids'])
                self.assertTrue(set(action['issue_ids']) <= ids)
                self.assertEqual(action['customer_goal'], s.extract()['latest_request'])
                self.assertIn('DEMO-TEST-24', action['order_identifiers'])
                if action['kind'] == 'invoice_request':
                    self.assertEqual(action['issue_ids'], ['issue-invoice'])
                if action['kind'] == 'pickup_followup':
                    self.assertEqual(action['issue_ids'], ['issue-pickup'])
            handoff = next(e for e in runtime['events'] if e['kind'] == 'handoff_request' and e['status'] == 'handoff_pending')
            self.assertTrue({'issue-safety', 'issue-pickup', 'issue-invoice'} <= set(handoff['payload']['action']['issue_ids']))

    def test_human_request_is_pending_and_refusal_keeps_background_knowledge_work(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ActionStore(Path(directory)/'actions.db')
            request = store.execute(state('我要人工客服接手，别再自动回复。', conversation='wants-human'), 'wants-input')
            self.assertTrue(any(e['status'] == 'handoff_pending' for e in request['events']))
            self.assertFalse(any(e['status'] in {'connected', 'handoff_connected'} for e in request['events']))
            refusal = store.execute(state('不要转人工，C200的USB能开会吗？', conversation='refuses-human'), 'refuses-input')
            self.assertTrue(any(e['kind'] == 'human_input_request' and e['status'] == 'created' for e in refusal['events']))
            self.assertFalse(any(e['kind'] == 'handoff_request' for e in refusal['events']))

    def test_installation_failure_complaint_is_not_customer_cancellation(self):
        ctx, actions = plan(state('安装两次取消了，我不想再空等。'))
        kinds = {a['kind'] for a in actions}
        self.assertFalse(ctx['installation_cancelled'])
        self.assertIn('installer_schedule_lookup', kinds)
        self.assertIn('installation_request', kinds)
        self.assertNotIn('installation_cancellation_request', kinds)

    def test_explicit_cancel_replaces_schedule_request_without_external_booking_change(self):
        s = state('预约安装周一上午。', '我要取消安装，不要再安排师傅了。')
        ctx, actions = plan(s)
        self.assertTrue(ctx['installation_cancelled'])
        self.assertIn('installation_cancellation_request', {a['kind'] for a in actions})
        self.assertFalse({'installation_request', 'installer_schedule_lookup'} & {a['kind'] for a in actions})
        with tempfile.TemporaryDirectory() as directory:
            runtime = ActionStore(Path(directory)/'actions.db').execute(s, 'cancel-input')
            self.assertTrue(any(e['kind'] == 'installation_cancellation_request' and e['status'] == 'created' for e in runtime['events']))
            self.assertFalse(any(e['payload'].get('external_execution') for e in runtime['events']))

    def test_resolved_aftersales_not_reopened_when_only_invoice_remains(self):
        _, actions = plan(state('台灯坏了，想退货。', '台灯修好了，不需要售后。现在只查发票。'))
        kinds = {a['kind'] for a in actions}
        self.assertIn('invoice_request', kinds)
        self.assertNotIn('aftersales_request', kinds)

    def test_cancelled_and_resolved_requests_stay_inactive_on_later_unrelated_turn(self):
        _, cancelled = plan(state('预约安装周一上午。', '我要取消安装，不要再安排师傅了。', '另外帮我核实发票漏项。'))
        self.assertFalse({'installation_request', 'installer_schedule_lookup'} & {a['kind'] for a in cancelled})
        _, resolved = plan(state('台灯坏了，想退货。', '售后已解决，不用处理了。', '另外帮我核实发票漏项。'))
        self.assertNotIn('aftersales_request', {a['kind'] for a in resolved})

    def test_schedule_billing_and_aftersales_are_distinct_executors(self):
        _, billing = plan(state('产品正常，不需要维修。安装时多收钱，收据对不上。'))
        self.assertEqual({a['kind'] for a in billing}, {'billing_request'})
        self.assertEqual({a['owner'] for a in billing}, {'billing'})
        _, schedule = plan(state('安装两次没来，只有周三下午在家。'))
        self.assertIn('installer_schedule_lookup', {a['kind'] for a in schedule})
        self.assertNotIn('logistics_lookup', {a['kind'] for a in schedule})
        _, aftersales = plan(state('耳机断音，我还没决定维修还是换货。'))
        self.assertEqual({a['kind'] for a in aftersales}, {'aftersales_request'})
        self.assertEqual({a['owner'] for a in aftersales}, {'aftersales'})

    def test_request_revision_appends_superseded_event_preserving_old_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'actions.db'
            s = state('台灯坏了，我想退货。')
            old = ActionStore(path).execute(s, 'return-input')
            old_event = next(e for e in old['events'] if e['kind'] == 'aftersales_request' and e['status'] == 'created')
            s.update('customer', '改成换货，不退货了。')
            new = ActionStore(path).execute(s, 'exchange-input')
            old_read = ActionStore(path).list('return-input')
            self.assertEqual(next(e for e in old_read if e['event_id'] == old_event['event_id']), old_event)
            self.assertTrue(any(e['status'] == 'superseded' and e['payload']['previous_event_id'] == old_event['event_id'] for e in new['events']))
            self.assertEqual(new['context']['preferred_outcome'], 'exchange')
            self.assertEqual(ActionStore(path).execute(s, 'exchange-input'), new)

    def test_persistent_conversation_replays_current_order_preference_and_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'messages.db'
            store = ConversationStore(path)
            store.update('thread', 'customer', '订单DEMO-OLD-24，周一安装。', 'op-1')
            store.update('thread', 'assistant', '订单DEMO-FAKE-24，已预约。', 'op-2')
            text = '号码写错，更正为DEMO-NEW-24。只有周三下午在家，不要直接约。'
            current = store.update('thread', 'customer', text, 'op-3')
            restored = ConversationStore(path).load('thread')
            self.assertEqual(restored.extract(), current.extract())
            self.assertEqual(restored.identifiers, ['DEMO-NEW-24'])
            self.assertIn('周三下午', restored.availability)
            self.assertEqual(len(restored.messages), 3)
            self.assertEqual(len(ConversationStore(path).update('thread', 'customer', text, 'op-3').messages), 3)
            self.assertEqual(ConversationStore(path).load('another-thread').messages, [])

    def test_conversation_operation_conflict_and_invalid_role_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConversationStore(Path(directory)/'messages.db')
            store.update('thread', 'customer', '查物流', 'same-op')
            with self.assertRaises(ValueError):
                store.update('thread', 'customer', '改成查发票', 'same-op')
            with self.assertRaises(ValueError):
                store.update('thread', 'tool', 'pretend receipt', 'other-op')


if __name__ == '__main__':
    unittest.main()
