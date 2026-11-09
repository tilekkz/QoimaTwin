/* Actual clock helpers with a delayed motion installation boundary. CPU only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.resolve(__dirname, '../src/adaptive-v3/twin/twinPage.ts'), 'utf8');
const ast = ts.createSourceFile('twinPage.ts', source, ts.ScriptTarget.Latest, true);
const names = ['syncPlay', 'setPlaying', 'tick', 'setSpeed'];
const helpers = ast.statements.filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name?.text));
assert.equal(helpers.length, names.length);
const play = {disabled: false, attributes: {}, setAttribute(key, value) {this.attributes[key] = value;}};
const focus = [{disabled: false}, {disabled: false}, {disabled: false}];
const speedButtons = [1, 4, 8].map(value => ({dataset: {speed: String(value)}, attributes: {},
  setAttribute(key, value) {this.attributes[key] = value;}}));
const frames = new Map();
let serial = 0;
const context = vm.createContext({
  motionReady: false, phase: 'ready', playing: true, t: 0, raf: 0, last: 0, speed: 4,
  play, $$: selector => selector === '[data-speed]' ? speedButtons : focus,
  PLAY: 'play', PAUSE: 'pause', DEMO_DURATION_S: 240,
  performance: {now: () => 100}, silenceAudio() {}, cuesBetween() {},
  reconcileReducedMotion: () => false,
  requestAnimationFrame(callback) {frames.set(++serial, callback); return serial;},
  cancelAnimationFrame(id) {frames.delete(id);},
  seek(at) {context.t = at;},
});
vm.runInContext(ts.transpileModule(helpers.map(node => node.getText(ast)).join('\n'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText, context);
context.setPlaying(true);
assert.equal(frames.size, 0, 'The default clock waits for motion installation');
assert.equal(context.t, 0);
assert.equal(play.disabled, true);
assert.ok(focus.every(button => button.disabled));
context.tick(200);
assert.equal(context.t, 0, 'A stale callback cannot consume the episode during preparation');
context.setPlaying(false);
context.t = 73;
context.motionReady = true;
context.setPlaying(context.playing);
assert.equal(context.t, 73, 'A paused URL time survives motion installation');
assert.equal(frames.size, 0);
assert.equal(play.disabled, false);
context.setPlaying(true);
assert.equal(frames.size, 1);
assert.ok(focus.every(button => !button.disabled));
const callback = [...frames.values()][0];
frames.clear();
callback(200);
assert.equal(context.t, 73.4, 'The installed episode advances from its retained time');
assert.equal(frames.size, 1);
context.setPlaying(false);
assert.equal(frames.size, 0);
context.setSpeed(1);
assert.equal(context.speed, 1);
assert.deepEqual(speedButtons.map(button => button.attributes['aria-pressed']), ['true', 'false', 'false']);
context.setSpeed(0);
assert.equal(context.speed, 1, 'An unsupported speed cannot change the clock');
console.log(JSON.stringify({passed: true, checks: 9, browser: false, delayed_motion: true}));
