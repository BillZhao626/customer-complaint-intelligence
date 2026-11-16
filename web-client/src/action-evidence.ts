export type Receipt={event_id:string;input_hash:string;kind:string;status:string};
export function summarizeLocalReceipts(events:Receipt[],inputHash:string|undefined):string{
 if(!inputHash)return '本次处理回执尚未核对。外部处理结果未知。';
 const current=[...new Map(events.filter(e=>e.input_hash===inputHash&&e.event_id).map(e=>[e.event_id,e])).values()];
 const lookup=current.some(e=>e.kind==='knowledge_lookup'&&e.status==='executed');
 const tasks=current.filter(e=>e.kind!=='knowledge_lookup'&&['created','handoff_pending'].includes(e.status)).length;
 return `${lookup?'已执行本地查询':'尚无本地查询完成回执'}；${tasks?`已创建${tasks}项内部待处理请求`:'尚无内部任务创建回执'}。外部处理结果未知。`;
}
