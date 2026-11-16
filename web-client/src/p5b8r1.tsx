import React,{useEffect,useState} from 'react';
import {api} from './api';
import './p5b8r1.css';
export const r1=()=>document.documentElement.dataset.study==='p5b8r1';
const labels:Record<string,string>={POSITIVE_EXPLICIT:'明确正面',NEGATIVE_EXPLICIT:'明确负面',NEUTRAL_ORDINARY:'普通中性',NEUTRAL_NEGATIVE_EXPERIENCE:'中性表达＋负面体验',MIXED_MULTI_ASPECT:'混合反馈'};
export function R1Readiness({select}:{select:(id:string)=>void}){
 const [s,setS]=useState<Record<string,any>|null>(null),[error,setError]=useState('');
 useEffect(()=>{api<Record<string,any>>('/api/b8r1/status').then(setS).catch(e=>setError(String(e)))},[]);
 return <aside className="r1-readiness" aria-label="情绪贡献消融准备状态"><div><span className="r1-pill">待新增实验授权</span><h2>情绪标签是否带来额外帮助？</h2><p>24案两组输入已冻结，均保留完整原文、Issue、事实与动作回执，仅增减显式情绪标签。尚未生成本轮回复，也没有新的Judge分数。</p></div><div className="r1-counts"><span><b>24</b>已曝光开发案例</span><span><b>0 / 48</b>新回复派发</span><span><b>¥0</b>本轮费用</span></div><p>下方是历史实验：90对首次回复，27对已自动评分、63对未评分。旧A的2项改善包含JSON失败混杂，不能证明情绪标签的独立贡献。旧398次账本已关闭；自动可审状态未获人类质量认证。</p>{error&&<p role="status">{error}</p>}<details><summary>查看24案分层与原始邮件</summary><p>类别采用模型暂定标签；混合6案来自同一合成家族，不是独立人工Gold。</p>{s&&Object.entries(s.strata).map(([key,n])=><div className="r1-stratum" key={key}><strong>{labels[key]} · {String(n)}封</strong><div>{s.cases.filter((c:any)=>c.stratum===key).map((c:any)=><button key={c.case_id} onClick={()=>select(c.case_id)}>{c.case_id} · {c.language==='en'?'英文':'中文'} →</button>)}</div></div>)}</details><a className="research-link" href="/api/b8r1/package">下载完整离线证据包</a></aside>
}
