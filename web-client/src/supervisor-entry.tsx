import React from 'react';
import {createRoot} from 'react-dom/client';
import Product from './p5b5';
import {Insights, Classification} from './research';
import './p5b5.css';
import './p5b5r2.css';
import './p5b7.css';
import './research.css';
import './portfolio-demo.css';

createRoot(document.getElementById('root')!).render(
  <Product r2 b7 historicalStudy qualityPage={<><div className="portfolio-case-link"><a href="/portfolio/yoga">查看瑜伽垫异味案例 · 两份保存回复 ↗</a></div><Classification/></>}
    researchPages={{insights:<Insights defaultSource="b8-r5-audited"/>, classification:<Classification/>}}/>
);