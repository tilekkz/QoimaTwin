import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const source = await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinPage.ts', import.meta.url,
), 'utf8');
const ast = ts.createSourceFile('twinPage.ts', source, ts.ScriptTarget.Latest, true);
let declaration;
function find(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'goStep') declaration = node;
  ts.forEachChild(node, find);
}
find(ast);
assert(declaration);
const code = ts.transpileModule(declaration.getText(ast), {
  compilerOptions: {target: ts.ScriptTarget.ES2022},
}).outputText;
const execute = new Function('context', 'with(context){' + code + ';goStep(0);}');
const element = () => ({textContent: '', style: {}, dataset: {},
  classList: {toggle() {}}, offsetWidth: 1});
function run(motionReady) {
  const calls = [];
  const step = {title: 'Runtime flow step', text: 'The actual queued frame', t: 138,
    mode: 'side', view: 'flow', focus: {target: [106.5, 1, 4], span: 52}};
  const context = {
    phase: 'ready', layoutBusy: false, motionReady, layoutEnabled: true, stepIndex: -1,
    presenterSteps: [step], PRESENTER_STEPS: [{...step, title: 'Legacy step', t: 104}],
    app: element(), present: element(), pStep: element(), pTitle: element(), pText: element(),
    pDots: {children: [element()]}, pPrev: element(), pNext: element(),
    phone: {matches: false}, HOME_DIR: [0, 1.15, 1], openScn: null,
    show() {}, setPop() {}, select() {}, setPlaying() {}, setSheet() {}, openScenario() {},
    setLayoutMode(value) {calls.push(['layout', value]);},
    setOperationView(value) {calls.push(['view', value]);},
    setMode(value) {calls.push(['mode', value]);},
    seek(value) {calls.push(['time', value]);},
    focusFor(value) {return value;}, fly() {},
  };
  execute(context);
  return {calls, context};
}
const ready = run(true);
assert.equal(ready.context.pTitle.textContent, 'Runtime flow step');
assert.deepEqual(ready.calls.filter(call => call[0] === 'time'), [['time', 138]]);
assert.deepEqual(ready.calls.filter(call => call[0] === 'view'), [['view', true]]);
assert.equal(ready.calls.filter(call => call[0] === 'layout').length, 0);
assert.equal(run(false).calls.length, 0);
console.log(JSON.stringify({passed: true, presenter_binding_checks: 5}));
