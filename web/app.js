/* 浏览器本地检索；不上传用户资料，不调用外部模型。 */
(function () {
  'use strict';
  const stops = new Set(['什么','怎么','如何','哪些','一个','这个','是否','请问','以及','我们','可以','进行','the','is','a','an','of','to','and','in']);
  function tokenize(text) {
    const tokens = text.toLowerCase().match(/[a-z0-9]+/g) || [];
    for (const run of text.match(/[\u4e00-\u9fff]+/g) || []) for(let i=0;i<run.length-1;i++) tokens.push(run.slice(i,i+2));
    return tokens.filter(t=>!stops.has(t));
  }
  function splitDocument(source, text) {
    const chunks=[]; let buffer=[],start=1,end=1;
    function flush(){if(buffer.length){chunks.push({source,start,end,text:buffer.join('\n')});buffer=[];}}
    text.split(/\r?\n/).forEach((line,index)=>{
      const n=index+1;
      if(!line.trim()){flush();return;}
      if(buffer.length && buffer.reduce((sum,s)=>sum+s.length+1,0)+line.length>480)flush();
      if(!buffer.length)start=n;
      end=n;
      if(line.length>480){flush();for(let i=0;i<line.length;i+=480)chunks.push({source,start:n,end:n,text:line.slice(i,i+480)});}
      else buffer.push(line);
    });flush();return chunks;
  }
  class SearchEngine {
    constructor(){this.documents=new Map();this.chunks=[];this.vectors=[];this.idf=new Map();}
    add(source,text){if(!text.trim())throw new Error('资料内容为空。');let total=text.length;for(const [name,t] of this.documents)if(name!==source)total+=t.length;if(total>3000000)throw new Error('资料总量请控制在300万字符以内。');this.documents.set(source,text);this.rebuild();}
    rebuild(){this.chunks=[...this.documents].flatMap(([s,t])=>splitDocument(s,t));const counts=this.chunks.map(c=>{const m=new Map();for(const t of tokenize(c.text))m.set(t,(m.get(t)||0)+1);return m;});const df=new Map();for(const count of counts)for(const t of count.keys())df.set(t,(df.get(t)||0)+1);this.idf=new Map([...df].map(([t,f])=>[t,Math.log((counts.length+1)/(f+1))+1]));this.vectors=counts.map(c=>this.vector(c));}
    vector(count){const v=new Map();for(const [t,f] of count)if(this.idf.has(t))v.set(t,(1+Math.log(f))*this.idf.get(t));const norm=Math.sqrt([...v.values()].reduce((sum,x)=>sum+x*x,0))||1;return new Map([...v].map(([t,x])=>[t,x/norm]));}
    search(question){const count=new Map();for(const t of tokenize(question))count.set(t,(count.get(t)||0)+1);const query=this.vector(count);return this.chunks.map((chunk,i)=>({chunk,score:[...query].reduce((sum,[t,x])=>sum+x*(this.vectors[i].get(t)||0),0)})).filter(h=>h.score>=.10).sort((a,b)=>b.score-a.score).slice(0,3);}
  }
  globalThis.ZhiyeSearch={SearchEngine,tokenize,splitDocument};
  if(typeof document==='undefined')return;
  const $=id=>document.getElementById(id);let engine=new SearchEngine();const history=[];
  const status=text=>$('status').textContent=text;
  function refresh(){const list=$('library');list.replaceChildren();for(const name of engine.documents.keys()){const li=document.createElement('li');li.textContent=name;list.append(li);}$('stats').textContent=`${engine.documents.size} 份资料 · ${engine.chunks.length} 个片段`;}
  function loadDemo(){engine=new SearchEngine();for(const d of window.ZHIYE_DEMO)engine.add(d.name,d.text);refresh();status('已加载演示资料 · 当前页面采用离线检索与原文摘录');}
  function render(question,hits){const root=$('result');root.replaceChildren();$('hit-count').textContent=`${hits.length} 个相关片段`;
    if(!hits.length){const box=document.createElement('div');box.className='no-result';const title=document.createElement('h3');title.textContent='未检索到足够相关的资料片段';const p=document.createElement('p');p.textContent='请换用资料中的关键词，或导入相关资料。这不代表资料中一定没有答案。';box.append(title,p);root.append(box);}
    else {const note=document.createElement('p');note.className='answer-note';note.textContent='以下为相关原文摘录。每个片段保留来源与行号，便于你核对。';root.append(note);hits.forEach((h,i)=>{const box=document.createElement('article');box.className='hit';const title=document.createElement('h3');title.textContent=`[${i+1}] ${h.chunk.source} · 第 ${h.chunk.start}–${h.chunk.end} 行`;const score=document.createElement('p');score.className='score';score.textContent=`检索相似度 ${h.score.toFixed(3)}（不是答案正确率）`;const quote=document.createElement('div');quote.className='quote';quote.textContent=h.chunk.text;box.append(title,score,quote);root.append(box);});}
    history.push({question,hits});status(`检索完成 · ${hits.length} 个相关片段 · 请核对原文依据`);
  }
  function ask(){const question=$('question').value.trim();if(!question){status('请先输入问题。');$('question').focus();return;}if(question.length>2000){status('问题请控制在2000字以内。');return;}render(question,engine.search(question));}
  $('question-form').addEventListener('submit',e=>{e.preventDefault();ask();});
  $('question').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();ask();}});
  document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>{$('question').value=button.dataset.question;ask();}));
  $('reset').addEventListener('click',loadDemo);
  $('files').addEventListener('change',async e=>{let success=0;const errors=[];for(const file of e.target.files){try{if(!/\.(txt|md)$/i.test(file.name))throw new Error('只支持TXT和Markdown。');if(file.size>1024*1024)throw new Error('单份资料不能超过1MB。');const bytes=await file.arrayBuffer();if(new Uint8Array(bytes).includes(0))throw new Error('文件似乎不是纯文本。');let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{text=new TextDecoder('gb18030',{fatal:true}).decode(bytes);}engine.add(file.name,text.replace(/^\uFEFF/,''));success++;}catch(error){errors.push(`${file.name}：${error.message}`);}}refresh();status(`已导入 ${success} 份资料。`+(errors.length?' '+errors.join('；'):' 同名文件再次导入会更新内容。'));e.target.value='';});
  $('export').addEventListener('click',()=>{if(!history.length){status('还没有问答记录，请先提问。');return;}const content='# 知页 · 问答记录\n\n模式：浏览器离线检索与原文摘录\n\n'+history.map(({question,hits})=>'## '+question+'\n\n'+(hits.length?hits.map((h,i)=>`[${i+1}] ${h.chunk.source} · 第 ${h.chunk.start}–${h.chunk.end} 行\n\n${h.chunk.text}`).join('\n\n'):'未检索到足够相关的资料片段。')).join('\n\n---\n\n');const url=URL.createObjectURL(new Blob([content],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='知页问答记录.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status('已导出问答记录。');});
  loadDemo();
})();
