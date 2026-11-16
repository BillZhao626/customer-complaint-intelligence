import test from 'node:test';import assert from 'node:assert/strict';
import {summarizeLocalReceipts,type Receipt} from '../src/action-evidence.ts';
const event=(kind:string,status:string,input_hash='current',event_id=kind):Receipt=>({kind,status,input_hash,event_id});
test('UNKNOWN lookup does not imply created business task',()=>{assert.equal(summarizeLocalReceipts([event('knowledge_lookup','executed')],'current'),'已执行本地查询；尚无内部任务创建回执。外部处理结果未知。')});
test('requested and stale receipts cannot authorize created UI text',()=>{const s=summarizeLocalReceipts([event('aftersales_request','requested'),event('billing_request','created','old')],'current');assert.ok(s.includes('尚无内部任务创建回执'))});
test('created receipts counted once and never claim external completion',()=>{const a=event('aftersales_request','created');const s=summarizeLocalReceipts([a,a,event('handoff_request','handoff_pending')],'current');assert.ok(s.includes('2项内部待处理请求'));assert.ok(s.includes('外部处理结果未知'))});
test('missing current hash is unassessable',()=>{assert.ok(summarizeLocalReceipts([event('aftersales_request','created')],undefined).includes('尚未核对'))});
