import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const source = new URL('../src/adaptive-v3/twin/twinOperationView.ts', import.meta.url);
const code = ts.transpileModule(await fs.readFile(source, 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
}).outputText;
const {operationPanels} = await import('data:text/javascript,' + encodeURIComponent(code));
const rendererSource = await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinRender.ts', import.meta.url,
), 'utf8');
const ast = ts.createSourceFile('twinRender.ts', rendererSource, ts.ScriptTarget.Latest, true);
let passFunction;
function findPasses(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'passes') passFunction = node;
  ts.forEachChild(node, findPasses);
}
findPasses(ast);
assert(passFunction, 'Test the real renderer pass function');
const passCode = ts.transpileModule(passFunction.getText(ast), {
  compilerOptions: {target: ts.ScriptTarget.ES2022},
}).outputText;
const realPasses = new Function('mode', 'operationFocus', 'split', 'region', 'fit',
  'NO_SHIFT', 'B_SHIFT', 'operationPanels', 'W', 'H', passCode + '\nreturn passes(W,H);');
const noShift = {name: 'source-space'};
const bShift = {name: 'warehouse-B-space'};
const html = await fs.readFile(new URL('../twin-v3.html', import.meta.url), 'utf8');
const page = await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinPage.ts', import.meta.url,
), 'utf8');
assert.match(html, /data-operation-view="flow"/);
assert.match(html, /data-operation-view="warehouse"/);
assert.match(page, /setOperationFocus\(operationFocus\)/);
assert.match(page, /searchParams\.set\('view',operationFocus\?'flow':'warehouse'\)/);

let cases = 0;
for (const [width, height] of [[1280, 720], [1920, 1080], [390, 844], [320, 720], [844, 390]]) {
  const narrow = width < 720;
  const margin = narrow ? 8 : 14;
  const region = {x: margin, y: margin, w: width - margin * 2, h: height - margin * 2};
  const before = structuredClone(region);
  const panels = operationPanels(region, narrow);
  assert.deepEqual(panels.map(panel => panel.variant), ['A', 'B']);
  for (const panel of panels) {
    assert.equal(panel.rect.x, region.x);
    assert.equal(panel.rect.w, region.w);
    assert(panel.rect.h > 0);
    assert(panel.rect.y >= region.y);
    assert(panel.rect.y + panel.rect.h <= region.y + region.h);
  }
  assert(panels[0].rect.y + panels[0].rect.h < panels[1].rect.y);
  assert.deepEqual(region, before);
  assert.deepEqual(operationPanels(region, narrow), panels);
  panels[0].rect.w = 1;
  assert.equal(operationPanels(region, narrow)[0].rect.w, region.w);
  const actual = realPasses('side', true, .5, () => region, () => 1,
    noShift, bShift, operationPanels, width, height);
  assert(actual[0].vp.y + actual[0].vp.h < actual[1].vp.y);
  assert(actual.every(pass => pass.shift === noShift));
  assert(actual.every(pass => pass.vp === pass.sc && pass.vp.w === region.w));
  const legacy = realPasses('side', false, .5, () => region, () => 1,
    noShift, bShift, operationPanels, width, height);
  assert.deepEqual(legacy.map(pass => pass.shift), [noShift, bShift]);
  const swipe = realPasses('swipe', true, .5, () => region, () => 1,
    noShift, bShift, operationPanels, width, height);
  assert(swipe.every(pass => pass.vp === region && pass.shift === noShift));
  assert.equal(swipe[0].sc.w + swipe[1].sc.w, region.w);
  cases++;
}
console.log(JSON.stringify({passed: true, viewport_cases: cases, paired_full_width: true}));
