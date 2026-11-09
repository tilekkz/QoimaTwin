"""Snapshot the built desktop viewer, with source hashes and the audited local server."""
import ast
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = Path('C:/Users/izbas/Documents/Codex/2026-11-09/qoimatwin-character-motion-naturalness/outputs')
PAGES = ['index.html', 'home-v3.html', 'twin-v3.html', 'warehouse-v3.html', 'stand-v3.html', 'staff-v3.html', 'skills-v3.html', 'motion-v3.html', 'long-motion-v3.html', 'heavy-inbound-v3.html']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(dist=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    name = 'QoimaTwin_V3_Desktop_' + now.strftime('%Y%m%d_%H%M%SZ')
    target = OUTPUTS / name
    assert not target.exists()
    dist = (dist or ROOT / 'frontend/dist').resolve(strict=True)
    for page in PAGES:
        assert (dist / page).is_file(), page
    assert sha(dist / 'models/v3/worker-base.glb') == '542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163'
    for relative in ['data/v3/motion-review/manifest.json', 'data/v3/long-motion/manifest.json']:
        manifest_path = dist / relative
        manifest = json.loads(manifest_path.read_bytes())
        for key, ref in manifest['sources'].items():
            path = (manifest_path.parent / ref['url']).resolve()
            assert path.is_relative_to(dist.resolve()) and path.is_file(), key
            assert sha(path) == ref['sha256'], key
    helper = ROOT / 'tools/visual/v3/package_preserved_v2.py'
    assert sha(helper) == '5598d8b93690bc020201688eabbe100688a86154a8f54b64a21ec8b0c385372a'
    constants = {}
    for node in ast.parse(helper.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for variable in node.targets:
                if isinstance(variable, ast.Name) and variable.id in ('SERVER', 'LAUNCHER'):
                    constants[variable.id] = ast.literal_eval(node.value)
    server = constants['SERVER'].replace('QoimaTwin V2', 'QoimaTwin V3 Desktop').replace('entire V2 ZIP', 'entire desktop ZIP').replace("'4192'", "'4226'").replace('QOIMA_PORT=4193', 'QOIMA_PORT=4227')
    marker = "try {\n    if ((await stat(target)).isDirectory())"
    assert server.count(marker) == 1
    server = server.replace(marker, "try {\n    if (pathname === '/') target = resolve(root, 'home-v3.html');\n    if ((await stat(target)).isDirectory())")
    # The preserved helper predates the local recorded episode's MP4 type.
    server = server.replace("'.wav':'audio/wav'", "'.mp4':'video/mp4', '.webm':'video/webm', '.wav':'audio/wav'")
    launcher = constants['LAUNCHER'].replace('V2', 'V3 Desktop').replace('4192', '4226').replace('preserved polished version', 'desktop viewer')
    target.mkdir(parents=True)
    shutil.copytree(dist, target / 'viewer')
    (target / 'server.mjs').write_text(server, encoding='utf-8')
    (target / 'Run_V3.cmd').write_bytes(launcher.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    subprocess.run(['node', '--check', str(target / 'server.mjs')], check=True, capture_output=True)
    handoff = ROOT / 'docs/adaptive-v3/handoff/desktop-20261109'
    if handoff.is_dir():
        shutil.copytree(handoff, target / 'handoff')
    readme = '''# QoimaTwin V3 · desktop

Распакуйте ZIP целиком и запустите Run_V3.cmd. Требуется Node.js 22.12+.
Адрес: http://127.0.0.1:4226/ . Данные, модели и страницы работают локально.

- «Сравнение»: общий обзор прямоугольного склада, вид сверху, поиск, сценарии и звук.
- «Команда»: распределение ролей с проверкой навыков, путём до поста, возвратом и сбросом.
- motion-v3.html: исходный персонаж с коробкой ближе к телу; воспроизведение и перемотка.
- long-motion-v3.html: отдельный записанный по времени пример движения длинномера.
- heavy-inbound-v3.html: одна паллета от приёмки до ячейки, общий clock и учёт груза.

Сравнения явно обозначены как визуальные или расчётные примеры. Операционный движок,
фактические очереди и полный цикл приёмки/отгрузки ещё не подключены к этому стенду.
Оценка перестановок учитывает путь туда/обратно и резерв на обработку, без очередей.
Телефонная версия в эту сдачу не входит. Внешний вид исходного персонажа сохранён.

Файлы handoff содержат состав моделей, карту анимаций и источники.
release.json фиксирует точные байты этого снимка; это локальная сборка текущей рабочей ветки.
'''
    (target / 'README.md').write_text(readme, encoding='utf-8')
    files = {}
    for path in sorted(target.rglob('*')):
        assert not path.is_symlink() and not (hasattr(path, 'is_junction') and path.is_junction())
        if path.is_file():
            files[path.relative_to(target).as_posix()] = dict(bytes=path.stat().st_size, sha256=sha(path))
    sources = {}
    for folder in ['frontend/src/adaptive-v3', 'frontend/public/data/v3']:
        for path in sorted((ROOT / folder).rglob('*')):
            if path.is_file() and path.suffix in ('.ts', '.css', '.json'):
                sources[path.relative_to(ROOT).as_posix()] = sha(path)
    release = dict(schema_id='qoima.desktop-release.v1', created_utc=now.isoformat(), desktop_only=True, branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(), git_base=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), includes_uncommitted_workspace=True, full_TZ_complete=False, backend_integration_complete=False, original_character_sha256=sha(dist/'models/v3/worker-base.glb'), pages=PAGES, files=files, source_hashes=sources, local_server_provenance=dict(source=helper.relative_to(ROOT).as_posix(), sha256=sha(helper), changes=['display label', 'loopback port4226', 'home page root', 'MP4/WebM MIME']))
    (target / 'release.json').write_text(json.dumps(release, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    archive = target.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(target.rglob('*')):
            if path.is_file():
                z.write(path, path.relative_to(target.parent).as_posix())
    result = dict(folder=str(target), archive=str(archive), bytes=archive.stat().st_size, sha256=sha(archive), pages=len(PAGES), manifest_files=len(files), original_character_preserved=True)
    (OUTPUTS / 'V3_desktop_latest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, help='Verified cold-build dist directory')
    package(parser.parse_args().dist)
