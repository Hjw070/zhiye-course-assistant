const assert=require('node:assert/strict');
const fs=require('node:fs');
globalThis.window=globalThis;
require('../web/sample-data.js');
require('../web/app.js');
const {SearchEngine,splitDocument}=globalThis.ZhiyeSearch;
const e=new SearchEngine();for(const d of ZHIYE_DEMO)e.add(d.name,d.text);
for(const [q,term] of [['如何缓解过拟合？','正则化'],['精确率与召回率有什么区别？','TP / (TP + FN)'],['什么是机会成本？','放弃']]){const hits=e.search(q);assert(hits.length);assert(hits[0].chunk.text.includes(term));const lines=e.documents.get(hits[0].chunk.source).split(/\r?\n/);assert.equal(lines.slice(hits[0].chunk.start-1,hits[0].chunk.end).join('\n'),hits[0].chunk.text);}
assert.equal(e.search('火星上有多少家咖啡馆？').length,0);
e.add('自定义.txt','番茄种植需要充足阳光。');assert.equal(e.search('番茄种植')[0].chunk.source,'自定义.txt');
e.add('自定义.txt','海洋生态系统');assert.equal(e.search('番茄种植').length,0);
assert.equal(splitDocument('长行','缓存'.repeat(500)).length,3);
assert.equal(new SearchEngine().search('任何问题').length,0);
console.log('Browser retrieval checks passed: examples, source lines, unknown query, import/update, long lines, empty library.');
