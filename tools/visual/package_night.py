"""Build the user-facing, offline night delivery. No deletion of source work."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {'node_modules', 'dist', 'test-results', 'playwright-report', '__pycache__', '.venv', '.git', 'work', '.vite'}


def ignored(directory, names):
    return [name for name in names if name in EXCLUDED or name.endswith(('.log', '.blend1', '.blend2', '.pyc'))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    required = ['work/night-video/QoimaTwin_Night_Demo.mp4', 'work/night-video/poster.png',
                'docs/visual/PERFORMANCE.json', 'docs/visual/BROWSER_QA.json',
                'assets/v2/asset-manifest.json', 'assets/v2/visual-checks.json']
    for name in required:
        if not (ROOT / name).is_file():
            raise ValueError('Required delivery evidence missing: ' + name)
    if json.loads((ROOT / 'assets/v2/visual-checks.json').read_text(encoding='utf-8'))['status'] != 'passed':
        raise ValueError('Final model validation is not passed')
    browser_qa = json.loads((ROOT / 'docs/visual/BROWSER_QA.json').read_text(encoding='utf-8'))
    if browser_qa.get('status') != 'passed' or browser_qa.get('execution', {}).get('exitCode') != 0:
        raise ValueError('Final browser QA is not passed')
    output = Path(args.output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Delivery must be outside the repository')
    output.mkdir(parents=True, exist_ok=True)
    project = output / 'project'
    project.mkdir(exist_ok=True)
    for directory in ['frontend', 'assets', 'tools', 'docs', 'contracts']:
        shutil.copytree(ROOT / directory, project / directory, ignore=ignored, dirs_exist_ok=True)
    for path in ROOT.iterdir():
        if path.is_file() and path.suffix in {'.md', '.json', '.pdf'}:
            shutil.copy2(path, project / path.name)
    viewer = output / 'viewer'
    shutil.copytree(ROOT / 'frontend/dist', viewer, dirs_exist_ok=True)
    for name in ['server.mjs', 'START_VIEWER.ps1', 'start-viewer.cmd']:
        shutil.copy2(ROOT / 'tools/visual' / name, output / name)
    qa = output / 'qa'
    shutil.copytree(ROOT / 'assets/v2/qa', qa / 'reference-render', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'assets/v2/qa-browser', qa / 'glb-contact-sheets', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'work/v2-browser-results-final.json', qa / 'browser-results.json')
    browser = ROOT / 'frontend/test-results/v2-runtime'
    if browser.exists():
        shutil.copytree(browser, qa / 'browser', dirs_exist_ok=True)
    for path in (ROOT / 'assets/references/v2').glob('personnel-*-after.png'):
        (qa / 'contacts').mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, qa / 'contacts' / path.name)
    for path in (ROOT / 'assets/references/v2').glob('personnel-*-contact.png'):
        (qa / 'contacts').mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, qa / 'contacts' / path.name)
    for path in (ROOT / 'frontend/test-results').glob('performance-*.png'):
        shutil.copy2(path, qa / path.name)
    for path in (ROOT / 'frontend/test-results').glob('package-*.png'):
        shutil.copy2(path, qa / path.name)
    video = ROOT / 'work/night-video/QoimaTwin_Night_Demo.mp4'
    poster = ROOT / 'work/night-video/poster.png'
    if video.exists():
        shutil.copy2(video, output / video.name)
    if poster.exists():
        shutil.copy2(poster, output / 'poster.png')
    for name in ['MEDIA_VERIFICATION.json', 'recording.json']:
        shutil.copy2(ROOT / 'work/night-video' / name, qa / name)
    for extension in ['*.mp4', '*.png', '*.json']:
        for path in (ROOT / 'work/night-video/action-clips').glob(extension):
            (output / 'action-clips').mkdir(exist_ok=True)
            shutil.copy2(path, output / 'action-clips' / path.name)
    shutil.copytree(ROOT / 'work/night-video/control-frames', qa / 'video-frames', dirs_exist_ok=True)
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    try:
        remote_commit = subprocess.check_output(['git', 'rev-parse', '--verify', 'refs/remotes/origin/' + branch], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        remote_commit = None
    published = remote_commit == commit
    manifest = json.loads((ROOT / 'assets/v2/asset-manifest.json').read_text(encoding='utf-8'))
    performance = json.loads((ROOT / 'docs/visual/PERFORMANCE.json').read_text(encoding='utf-8'))
    metrics = '\n'.join(f"- {result['mode']}: median {result['medianFps']:.1f} FPS, p95 {result['p95FrameMs']:.1f} ms; max {result['maxCalls']} calls / {result['maxTriangles']:,} triangles." for result in performance['reports'])
    readme = f'''# QoimaTwin — утренний пакет

Открой **start-viewer.cmd**, затем адрес, указанный в окне: **http://127.0.0.1:4180**.
Проверенная команда из этой папки:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\\START_VIEWER.ps1
```

Нужен установленный Node.js 22.12+; на этом ноутбуке проверен Node 24.19.
Установка npm-пакетов и доступ к API/CDN для готового viewer не нужны.
Окно сервера оставить открытым; Ctrl+C завершает сервер.

Поставлена visual/frontend-часть: склад 72×48 м, 288 стеллажей, 864 адреса,
600 начальных партий, 24 сотрудника, 2 погрузчика, 6 постов, 179 ячеек линии
и 19 открытых узлов. Можно вращать/приближать сцену, выбирать адрес/человека/груз,
открывать 21 отдельный стенд и четыре ракурса, смотреть референсы, управлять
временем и следовать заказу. Звук изначально выключен.

**Данные показа — VISUAL DEMO / synthetic.** Это согласованная визуальная
фикстура, не DES, прогноз или доказательство экономии. Backend/API/ledger
Армана не подменены. Импорт inline Run v2 доступен, ограничения адаптера
описаны отдельно; A/B без двух реальных совместимых результатов не показан.

## Где лежат файлы

- [Видео](QoimaTwin_Night_Demo.mp4) · [контрольный кадр](poster.png).
- Отдельные реальные клипы действий: `action-clips/` (pick, handoff, pack,
  forklift load, scan). Запись без звука; SFX включаются в самом viewer.
- [Визуальная приёмка](visual-review.html): reference/render и кадры GLB.
- Редактируемые Blender: `project/assets/v2/blender/`.
- Финальные 23 GLB: `project/frontend/public/models/v2/`.
- [Manifest](project/assets/v2/asset-manifest.json): bounds, axes, origins, pivots,
  anchors, LOD, источники и SHA256.
- Источники и builders: `project/tools/blender/`, frontend: `project/frontend/`.
- [Контакты/интеграция](project/docs/visual/MOTION_AND_INTEGRATION.md),
  [модели](project/docs/visual/MODEL_QA.md),
  [производительность](project/docs/visual/PERFORMANCE.json),
  [resume](project/docs/visual/NIGHT_RESUME.md).

Геометрия/экспорты проверены независимым бинарным валидатором и Khronos.
84 финальных ракурса сверены с референсами; экспортированные GLB проверены
в браузере. Play/pause/reset/seek, остановка тары, контакты вил/паллеты,
посадка водителей, muted/reduced-motion и локальная загрузка проверены.
Итоговый прогон: 30/30, включая 16 проверок ядра replay/аудио и 14 браузерных.

## Фактический замер

1366×768, low, headless Chrome, один viewport, fixture 10×, звук выключен,
по 60 с на обзор и следование P01. Это замер визуальной фикстуры в полном
масштабе, не проверка массового backend-потока или пропускной способности.

{metrics}

Полные условия/GPU и память доступны в PERFORMANCE.json.

Ветка: `{branch}`. Commit: `{commit}`.
Проверенный remote-tracking ref origin совпадает с commit: **{'да' if published else 'нет'}**.
Код/контракты расчётной части не переписаны. Источники/права:
[SOURCES_AND_RIGHTS](project/docs/visual/SOURCES_AND_RIGHTS.md).
'''
    (output / 'README_MORNING.md').write_text(readme, encoding='utf-8')
    licenses = []
    for library in ['three', 'vue', 'vite']:
        path = ROOT / 'frontend/node_modules' / library / 'LICENSE'
        if not path.exists():
            path = path.with_name('LICENSE.md')
        if path.exists():
            licenses.append(library + '\n' + '=' * 60 + '\n' + path.read_text(encoding='utf-8'))
    (output / 'THIRD_PARTY_WEB_LICENSES.txt').write_text('\n\n'.join(licenses), encoding='utf-8')
    sheets = sorted((qa / 'reference-render').glob('*-reference-render.png'))
    figures = ''.join(f'<figure><h2>{path.stem.replace("-reference-render", "")}</h2><a href="qa/reference-render/{path.name}"><img src="qa/reference-render/{path.name}" loading="lazy"></a></figure>' for path in sheets)
    (output / 'visual-review.html').write_text('''<!doctype html><meta charset="utf-8"><title>QoimaTwin visual review</title><style>body{margin:32px;background:#e9e8df;color:#30483f;font:14px Segoe UI,sans-serif}h1{font-weight:400}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}figure{margin:0;background:#f6f4e9;padding:16px;border:1px solid #c7cebe}h2{font-size:15px;font-weight:500}img{width:100%;display:block}a{color:inherit}@media(max-width:800px){main{grid-template-columns:1fr}}</style><h1>QoimaTwin / 21 families</h1><p>Reference sheets + front, side, rear and three-quarter renders. Final GLB screenshots: <a href="qa/browser/overview.png">warehouse</a>; individual four-angle captures are in qa/browser/, comparison sheets in qa/glb-contact-sheets/. All data is a synthetic visual fixture; see README_MORNING.md.</p><main>''' + figures + '</main>', encoding='utf-8')
    delivery = {'branch': branch, 'commit': commit, 'originBranchCommit': remote_commit, 'publishedCommitMatches': published, 'asset_manifest': 'project/assets/v2/asset-manifest.json', 'performance': performance, 'files': []}
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'DELIVERY_MANIFEST.json':
            delivery['files'].append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (output / 'DELIVERY_MANIFEST.json').write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                target.write(path, output.name + '/' + path.relative_to(output).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as source:
        if source.testzip() is not None:
            raise ValueError('Delivery archive CRC check failed')
    archive.with_suffix('.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest, 'files': len(delivery['files']), 'manifest_assets': len(manifest.get('assets', []))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
