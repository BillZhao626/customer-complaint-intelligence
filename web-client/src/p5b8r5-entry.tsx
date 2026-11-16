import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import Product from './p5b5';
import {Insights,Classification} from './research';
import './p5b5.css';
import './p5b5r2.css';
import './p5b7.css';
import './research.css';
import {api} from './api';
function ImportSaved(){
 const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
 async function load(){setBusy(true);try{const r=await api<{imported:number}>('/api/b8/import',{identity:'P5B8_SAVED_REAL_CHAIN'});setMessage('已载入'+r.imported+'封已保存邮件；刷新会话查看。')}catch(e){setMessage(String(e))}finally{setBusy(false)}}
 return <div><button disabled={busy} onClick={load} title="载入已保存的合成邮件与真实分析，不调用模型">{busy?'载入中':'载入邮件'}</button>{message&&<small role="status">{message}</small>}</div>
}
createRoot(document.getElementById('root')!).render(<Product r2 b7 controlledLive historicalStudy importControl={<ImportSaved/>} qualityPage={<Classification/>} researchPages={{insights:<Insights defaultSource="b8-r5-audited"/>,classification:<Classification/>}}/>);
