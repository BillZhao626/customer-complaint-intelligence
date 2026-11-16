import React from 'react';
import {createRoot} from 'react-dom/client';
import Product from './p5b5';
import {R2Quality} from './p5b5r2';
import {Insights,Classification} from './research';
import './p5b5.css';
import './p5b5r2.css';
import './research.css';
createRoot(document.getElementById('root')!).render(<Product r2 qualityPage={<R2Quality/>} researchPages={{insights:<Insights/>,classification:<Classification/>}}/>);
