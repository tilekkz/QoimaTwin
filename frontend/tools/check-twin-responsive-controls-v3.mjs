import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const markup = await readFile(new URL('../twin-v3.html', import.meta.url), 'utf8');
const controls = [
  ['id="tw-menu-btn"', 'QoimaTwin'],
  ['data-mode="side"', 'Рядом'],
  ['data-mode="swipe"', 'Шторка'],
  ['data-open="now"', 'Состояние'],
  ['data-open="diff"', 'Изменения'],
];
for (const [attribute, name] of controls) {
  const buttons = [...markup.matchAll(/<button\b[^>]*>/g)]
    .map(match => match[0]).filter(tag => tag.includes(attribute));
  assert.equal(buttons.length, 1, 'Unique comparison control ' + name);
  assert.ok(buttons[0].includes(`aria-label="${name}"`),
    'The icon-only narrow-screen control needs its accessible name: ' + name);
}
console.log(JSON.stringify({passed: true, controls: controls.length, browser: false}));
