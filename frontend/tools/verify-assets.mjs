import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import validator from 'gltf-validator';

const directory = new URL('../public/models/', import.meta.url);
const files = (await readdir(directory)).filter((name) => name.endsWith('.glb'));
if (!files.length) throw new Error('No GLB assets. Run tools/export-calibration.ps1 first.');
for (const file of files) {
  const path = new URL(file, directory);
  const bytes = await readFile(path);
  const result = await validator.validateBytes(new Uint8Array(bytes), { uri: file });
  console.log(JSON.stringify({ file: fileURLToPath(path), bytes: bytes.length, issues: result.issues }));
  if (result.issues.numErrors) process.exitCode = 1;
}
