import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const canvas = readFileSync(new URL('../review/canvas.html', import.meta.url), 'utf8');
const library = readFileSync(new URL('../review/v2.html', import.meta.url), 'utf8');
const block = (text, start, end) => text.slice(text.indexOf(start), text.indexOf(end, text.indexOf(start)));
function response(revision = 1, status = 200) {
  return { status, ok: status === 200, json: async () => ({ revision, saved: '2026-09-30 22:15', paths: ['image.png'], feedback: { comment: 'saved' } }) };
}
function canvasHarness() {
  const pending = [], timers = new Map();
  let timerId = 0;
  const context = vm.createContext({ window: {}, document: {activeElement:null}, status() {}, toast() { return null; }, openEditor: null, cropState: null,
    setTimeout(fn) { timers.set(++timerId, fn); return timerId; }, clearTimeout(id) { timers.delete(id); },
    fetch(url, options) { return new Promise(resolve => pending.push({ url, body: JSON.parse(options.body), resolve })); }
  });
  vm.runInContext('let board = {schema:1,revision:0,items:{},groups:{},custom:{preserve:true}}, dirty=false,saveT=null,BOARD="main";', context);
  vm.runInContext(block(canvas, 'let saveFlight =', 'addEventListener("beforeunload"'), context);
  return { pending, timers, context, edit(value) { vm.runInContext(`board.items.latest=${JSON.stringify(value)};dirty=true;queueSave();`, context); }, flush() { return context.window.hyimgFlush(); } };
}
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

test('immediate flush cancels debounce and writes latest edit exactly once, retaining unknown fields', async () => {
  const h = canvasHarness();
  h.edit('first'); h.edit('latest');
  const flushing = h.flush();
  assert.equal(h.pending.length, 1);
  assert.equal(h.timers.size, 0);
  assert.equal(h.pending[0].body.items.latest, 'latest');
  assert.equal(h.pending[0].body.custom.preserve, true);
  h.pending[0].resolve(response());
  assert.equal(await flushing, true);
  assert.equal(await h.flush(), true);
  assert.equal(h.pending.length, 1);
});

test('flush serializes changes arriving during an in-flight request with updated revision', async () => {
  const h = canvasHarness(); h.edit('first');
  const initial = vm.runInContext('save()', h.context);
  h.edit('second');
  const flushing = h.flush();
  assert.equal(h.pending.length, 1);
  h.pending[0].resolve(response(7)); await tick();
  assert.equal(h.pending.length, 2);
  assert.equal(h.pending[1].body.revision, 7);
  assert.equal(h.pending[1].body.items.latest, 'second');
  h.pending[1].resolve(response(8));
  assert.equal(await initial, true);
  assert.equal(await flushing, true);
  assert.equal(h.timers.size, 0);
});

for (const status of [409, 500]) test(`flush returns false and retains dirty state after HTTP ${status}`, async () => {
  const h = canvasHarness(); h.edit('retain');
  const flushing = h.flush(); h.pending[0].resolve(response(1, status));
  assert.equal(await flushing, false);
  assert.equal(vm.runInContext('dirty', h.context), true);
});

test('clean board flush performs no request', async () => {
  const h = canvasHarness(); assert.equal(await h.flush(), true); assert.equal(h.pending.length, 0);
});

function libraryHarness() {
  const pending = [], timers = new Map(), saved = {};
  let timer = 0, delegateCalls = 0;
  const frame = { getAttribute: () => '/canvas?embed=1', contentWindow: { hyimgFlush: async () => { delegateCalls++; return true; } } };
  const context = vm.createContext({ window: {}, $: selector => selector === '#cvFrame' ? frame : saved,
    setTimeout(fn) { timers.set(++timer, fn); return timer; }, clearTimeout(id) { timers.delete(id); },
    fetch(url, options) { return new Promise(resolve => pending.push({ url, body: JSON.parse(options.body), resolve })); }
  });
  vm.runInContext('let cur=0,view=[{path:"image.png",name:"image"}],items=view,saveTimer=null,editing=null,current="";function state(){return {comment:current}};const pendingAnswers=new Map(),failedAnswers=new Set();let answerTail=Promise.resolve(true);', context);
  vm.runInContext(block(library, 'let feedbackTail =', '// Off-screen batches'), context);
  vm.runInContext(block(library, 'function saveSoon()', 'function setVerdict'), context);
  return { context, pending, timers, frame, delegated: () => delegateCalls };
}

test('library flush drains debounced ratings and waits before delegating to canvas', async () => {
  const h = libraryHarness(); vm.runInContext('current="latest";saveSoon()', h.context);
  const flushing = h.context.window.hyimgFlush(); await tick();
  assert.equal(h.pending.length, 1); assert.equal(h.pending[0].body.comment, 'latest');
  assert.equal(h.delegated(), 0);
  h.pending[0].resolve(response());
  assert.equal(await flushing, true); assert.equal(h.delegated(), 1); assert.equal(h.timers.size, 0);
});

test('library saves are serialized and a failed rating cancels flush', async () => {
  const h = libraryHarness();
  vm.runInContext('current="first";save();current="second";save()', h.context);
  const flushing = h.context.window.hyimgFlush(); await tick();
  assert.equal(h.pending.length, 1); h.pending[0].resolve(response()); await tick();
  assert.equal(h.pending.length, 2); assert.equal(h.pending[1].body.comment, 'second');
  h.pending[1].resolve(response(1, 500));
  assert.equal(await flushing, false); assert.equal(h.delegated(), 0);
});

test('library refuses success while a loaded canvas has no flush handler or reports failure', async () => {
  const h = libraryHarness(); h.frame.contentWindow.hyimgFlush = undefined;
  assert.equal(await h.context.window.hyimgFlush(), false);
  h.frame.contentWindow.hyimgFlush = async () => false;
  assert.equal(await h.context.window.hyimgFlush(), false);
});


test('canvas refuses success during upload/page operation or an unresolved page save failure', async () => {
  const h = canvasHarness();
  vm.runInContext('canvasOperations=1', h.context);
  assert.equal(await h.flush(), false);
  vm.runInContext('canvasOperations=0;pagesFailed=true', h.context);
  assert.equal(await h.flush(), false);
  assert.equal(h.pending.length, 0);
});

test('library flush starts and drains pending answer tasks', async () => {
  const h = libraryHarness();
  vm.runInContext('const ansTimers={};', h.context);
  vm.runInContext(block(library, 'function saveAnswer(key)', '$("#qblock").addEventListener'), h.context);
  let finish;
  h.context.answerTask = () => new Promise(resolve => { finish = resolve; });
  vm.runInContext('pendingAnswers.set("image/question",answerTask)', h.context);
  const flushing = h.context.window.hyimgFlush(); await tick();
  assert.equal(h.delegated(), 0);
  finish(true);
  assert.equal(await flushing, true);
  assert.equal(h.delegated(), 1);
});


test('full HTML scripts parse without syntax errors', () => {
  for (const html of [canvas, library]) {
    for (const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
  }
});

test('library rechecks ratings created while waiting for canvas flush', async () => {
  const h = libraryHarness(); let finish;
  h.frame.contentWindow.hyimgFlush = () => new Promise(resolve => { finish = resolve; });
  const flushing = h.context.window.hyimgFlush(); await tick();
  vm.runInContext('current="during canvas flush";save()', h.context); await tick();
  h.frame.contentWindow.hyimgFlush = async () => true;
  finish(true); await tick();
  let done = false; flushing.then(() => { done = true; }); await tick();
  assert.equal(done, false);
  h.pending[0].resolve(response());
  assert.equal(await flushing, true);
});
