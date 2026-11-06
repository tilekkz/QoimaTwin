# Frontend dependencies

Runtime direct dependencies actually used by the preparation scaffold:

- Three.js 0.169.0 (including GLTFLoader and OrbitControls), MIT.
  https://github.com/mrdoob/three.js/tree/r169 — full notice: licenses/three-LICENSE.txt.
- Vue 3.5.45 and Vue runtime packages, MIT.
  https://github.com/vuejs/core — full notice: licenses/vue-LICENSE.txt.

Exact versions/integrity of all direct and transitive dependencies are recorded
in package-lock.json. Dev tools include Vite/plugin-vue (MIT), TypeScript
(Apache-2.0), vue-tsc (MIT), Playwright (Apache-2.0), gltf-validator (Apache-2.0),
and Three type definitions (MIT). Their complete package license files remain
in the installed packages; these tools are not shipped as runtime application
code in the current production bundle.

The donor archive remains separately attributed by the root
THIRD_PARTY_NOTICES.md and donors/smart-warehouse-LICENSE.txt. No donor scene,
AGV animation or decorative KPI has been copied into this scaffold. The local
calibration asset was generated for this project using tools/blender/export_calibration.py.

Historical UCI attribution and data transformations are documented in the root
notices/data manifest. No UCI records are rendered as a real warehouse run in
the preparation screen.
