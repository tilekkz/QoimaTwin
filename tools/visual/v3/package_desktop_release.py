"""Snapshot a verified desktop viewer; preflight every input before publishing anything."""
import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = Path('C:/Users/izbas/Documents/Codex/2026-11-09/qoimatwin-character-motion-naturalness/outputs')
PAGES = ['index.html', 'home-v3.html', 'twin-v3.html', 'warehouse-v3.html', 'stand-v3.html', 'staff-v3.html', 'skills-v3.html', 'motion-v3.html', 'original-cart-v3.html', 'long-motion-v3.html', 'heavy-inbound-v3.html', 'scenario-v3.html', 'native-pair-v3.html']
HANDOFF_FILES = ['asset-manifest.json', 'animation-event-map.json', 'credits.md', 'checks.json']
ORIGINAL_WORKER = '542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163'
SERVER_HELPER = '5598d8b93690bc020201688eabbe100688a86154a8f54b64a21ec8b0c385372a'
QA_LIMIT_BYTES = 100 * 1024 * 1024
QA_FILES = [
 'docs/adaptive-v3/evidence/Q03-current-numeric-20261110.json',
 'docs/adaptive-v3/evidence/Q12.json',
 'docs/adaptive-v3/evidence/deep-production-regression-20261110/aggregate-45-checks.json',
 'docs/adaptive-v3/evidence/deep-production-regression-20261110/harness-repair-allowlist.json',
 'docs/adaptive-v3/evidence/current-model-review-20261110/root-review.json',
 'docs/adaptive-v3/evidence/current-model-review-20261110/native-30-models.json',
 'docs/adaptive-v3/evidence/current-model-review-20261110/new-components-3-models-12-views.json',
 'docs/adaptive-v3/evidence/final-composition-review-20261110/receipt.json',
 'docs/adaptive-v3/evidence/final-composition-review-20261110/review.md',
 'docs/adaptive-v3/evidence/final-composition-review-20261110/native-protocol-review.md',
 'docs/adaptive-v3/evidence/final-composition-review-20261110/native-protocol-receipt.json',
] + [f'assets/v3/iterations/model-review-current-20261110/{i:02}.png' for i in range(1, 11)] + ['assets/v3/iterations/model-review-current-20261110/11-new-components.png']
QA_GROUPS = {
 'docs/adaptive-v3/evidence/final-browser-desktop-20261110/current-full-N0-N4': ['checks.json', 'N2-terminal.json', 'N3-terminal.json', 'N4-restored.json', 'fresh-process-absence.json', 'small-source.png', 'small-PK02.png', 'small-gate.png', 'source-native-mount.png', 'source-whole-outside-retained.png', 'final-whole-warehouse-2700.png'],
 'docs/adaptive-v3/evidence/final-browser-desktop-20261110/block-rebuild-six-cases': ['checks.json', 'layout-bounds.json', 'hero-snapshot.json', 'home-twin-blocks.jpg'],
 'docs/adaptive-v3/evidence/deep-official-regression-20261110': ['index.json', 'browser15-PASS.json', 'replay18-PASS.json'],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def plain(path, root=None):
    info = path.lstat()
    require(not path.is_symlink() and not (getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)), 'Reparse point/symlink is not a package input: ' + str(path))
    resolved = path.resolve(strict=True)
    if root is not None:
        require(resolved.is_relative_to(root), 'Input escapes selected source: ' + str(path))
    return resolved


def tree(folder):
    require(plain(folder).is_dir(), 'Required directory: ' + str(folder))
    result = {}
    for item in sorted(folder.rglob('*')):
        plain(item, folder)
        if item.is_file():
            result[item.relative_to(folder).as_posix()] = dict(bytes=item.stat().st_size, sha256=sha(item))
    return result


def runtime_paths(source):
    paths = []
    for folder in ['frontend/src', 'frontend/public']:
        require(plain(source / folder, source).is_dir(), 'Required runtime directory: ' + folder)
        for item in sorted((source / folder).rglob('*')):
            plain(item, source)
            if item.is_file():
                paths.append(item.relative_to(source).as_posix())
    paths.extend(p.relative_to(source).as_posix() for p in sorted((source / 'frontend').glob('*.html')))
    paths.extend('frontend/' + name for name in ['package.json', 'package-lock.json', 'vite.config.ts'])
    for relative in paths:
        require(plain(source / relative, source).is_file(), 'Required runtime file: ' + relative)
    return sorted(set(paths))


def git_runtime(source, source_commit, git_repo):
    repository = (git_repo or source).resolve(strict=True)
    top = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=repository, text=True).strip()).resolve(strict=True)
    require(top == repository, '--git-repo must be the exact Git root')
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', (source_commit or 'HEAD') + '^{commit}'], cwd=repository, text=True).strip()
    records = subprocess.check_output(['git', 'ls-tree', '-rz', '--full-tree', commit, '--', 'frontend'], cwd=repository)
    blobs = {}
    for record in records.split(b'\0'):
        if not record:
            continue
        header, relative = record.split(b'\t', 1)
        mode, kind, oid = header.split()
        relative = relative.decode('utf-8')
        selected = relative.startswith(('frontend/src/', 'frontend/public/')) or relative in ['frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.ts'] or (Path(relative).parent.as_posix() == 'frontend' and relative.endswith('.html'))
        if selected:
            require(kind == b'blob' and mode in [b'100644', b'100755'], 'Runtime source is not a regular Git blob: ' + relative)
            blobs[relative] = oid.decode('ascii')
    paths = runtime_paths(source)
    require(set(paths) == set(blobs), 'Runtime paths differ from commit; missing=' + repr(sorted(set(blobs) - set(paths))) + '; extra=' + repr(sorted(set(paths) - set(blobs))))
    sources = {}
    for relative in paths:
        data = (source / relative).read_bytes()
        algorithm = hashlib.sha1 if len(blobs[relative]) == 40 else hashlib.sha256
        require(algorithm(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest() == blobs[relative], 'Uncommitted runtime source: ' + relative)
        sources[relative] = hashlib.sha256(data).hexdigest()
    return commit, sources


def copy_files(source, target, files):
    for relative, expected in files.items():
        original = source / relative
        require(plain(original, source).is_file(), 'Input disappeared: ' + str(original))
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        require(destination.stat().st_size == expected['bytes'] and sha(destination) == expected['sha256'], 'Input changed during copy: ' + str(original))


def remove_created(path, parent):
    # Only this invocation's freshly-created staging/published path is passed here.
    require(path.name.startswith(('.qoima-desktop-', 'QoimaTwin_V3_Desktop_')) and path.parent.resolve() == parent.resolve() and path.resolve().is_relative_to(parent.resolve()) and not path.is_symlink(), 'Unsafe transaction cleanup: ' + str(path))
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


README = '''# QoimaTwin V3 · desktop

Распакуйте ZIP целиком и запустите Run_V3.cmd. Требуется Node.js 22.12+.
Адрес: http://127.0.0.1:4226/ . Данные, модели и страницы работают локально.

- «Сравнение»: общий обзор прямоугольного склада, вид сверху, поиск, сценарии и звук.
- «Команда»: распределение ролей с проверкой навыков, путём до поста, возвратом и сбросом.
- motion-v3.html: исходный персонаж с коробкой ближе к телу; воспроизведение и перемотка.
- original-cart-v3.html: исходный персонаж берёт тележку, толкает, отпускает и отходит; обратное воспроизведение и перемотка.
- long-motion-v3.html: отдельный записанный по времени пример движения длинномера.
- heavy-inbound-v3.html: одна паллета от приёмки до ячейки, общий clock и учёт груза.
- scenario-v3.html: общие заявки N0–N4, конечные ресурсы, маршруты и роли в 3D; незавершённые действия показаны как ожидающие.
- native-pair-v3.html: просмотр сохранённых baseline/candidate NDJSON; выберите файлы или подключите API.

Сценарии используют зафиксированные демонстрационные входы. Общая сцена показывает
передачи исходных коробов, приёмку, конечные очереди, занятость ресурсов и возвраты.
Исходный длинномер проходит восточные ворота и остаётся на F02 снаружи; разгрузка
получателем не показана. Неподдерживаемые действия имеют причину и не считаются выполненными.
Оценка двух перестановок включает подход, обработку, пути и ожидание ресурсов;
для текущих адресов переносы не окупаются. Это не измерение активного труда и не KPI движка.
Авторитетный операционный backend относится к отдельной интеграции.
Телефонная версия в эту сдачу не входит. Внешний вид исходного персонажа сохранён.

Файлы handoff содержат состав моделей, карту анимаций и источники.
release.json фиксирует точные байты сборки, исходников и Git-коммит поставки.
'''

def package(dist=None, *, source_repo=None, outputs=None, source_commit=None, acceptance=None, video=None, git_repo=None, qa=()):
    source = (source_repo or ROOT).resolve(strict=True)
    output = (outputs or OUTPUTS).resolve()
    dist = (dist or source / 'frontend/dist').resolve(strict=True)
    require(dist.is_relative_to(source), 'Build must belong to selected source')
    require(not output.is_relative_to(dist), 'Output must not be inside dist')
    now = datetime.datetime.now(datetime.timezone.utc)
    name = 'QoimaTwin_V3_Desktop_' + now.strftime('%Y%m%d_%H%M%SZ')
    target, archive = output / name, output / (name + '.zip')
    require(not target.exists() and not archive.exists(), 'Release folder/ZIP already exists')
    commit, sources = git_runtime(source, source_commit, git_repo)
    dist_files = tree(dist)
    for page in PAGES:
        require(page in dist_files, 'Required page: ' + page)
    require(dist_files.get('models/v3/worker-base.glb', {}).get('sha256') == ORIGINAL_WORKER, 'Original worker changed')
    for relative, expected in sources.items():
        if relative.startswith('frontend/public/'):
            public = relative.removeprefix('frontend/public/')
            require(dist_files.get(public, {}).get('sha256') == expected, 'Build public resource differs from selected source: ' + public)
    for relative in ['data/v3/motion-review/manifest.json', 'data/v3/long-motion/manifest.json']:
        manifest_path = dist / relative
        for logical, ref in json.loads(manifest_path.read_bytes())['sources'].items():
            payload = (manifest_path.parent / ref['url']).resolve(strict=True)
            require(payload.is_relative_to(dist) and plain(payload, dist).is_file(), 'Portable source escapes dist: ' + logical)
            require(sha(payload) == ref['sha256'] and payload.stat().st_size == ref['bytes'], 'Portable source fingerprint: ' + logical)
    helper = source / 'tools/visual/v3/package_preserved_v2.py'
    require(plain(helper, source).is_file() and sha(helper) == SERVER_HELPER, 'Audited server helper changed')
    constants = {}
    for node in ast.parse(helper.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for variable in node.targets:
                if isinstance(variable, ast.Name) and variable.id in ['SERVER', 'LAUNCHER']:
                    constants[variable.id] = ast.literal_eval(node.value)
    server = constants['SERVER'].replace('QoimaTwin V2', 'QoimaTwin V3 Desktop').replace('entire V2 ZIP', 'entire desktop ZIP').replace("'4192'", "'4226'").replace('QOIMA_PORT=4193', 'QOIMA_PORT=4227')
    marker = "try {\n    if ((await stat(target)).isDirectory())"
    require(server.count(marker) == 1, 'Audited server patch marker changed')
    server = server.replace(marker, "try {\n    if (pathname === '/') target = resolve(root, 'home-v3.html');\n    if ((await stat(target)).isDirectory())")
    server = server.replace("'.wav':'audio/wav'", "'.mp4':'video/mp4', '.webm':'video/webm', '.wav':'audio/wav'")
    launcher = constants['LAUNCHER'].replace('V2', 'V3 Desktop').replace('4192', '4226').replace('preserved polished version', 'desktop viewer')
    subprocess.run(['node', '--check', '--input-type=module'], input=server, text=True, check=True, capture_output=True, timeout=30)
    handoff = source / 'docs/adaptive-v3/handoff/runtime-20261110'
    handoff_files = {}
    for leaf in HANDOFF_FILES:
        candidate = handoff / leaf
        require(plain(candidate, source).is_file(), 'Required handoff file: ' + leaf)
        handoff_files[leaf] = dict(bytes=candidate.stat().st_size, sha256=sha(candidate))
    handoff_checks = json.loads((handoff / 'checks.json').read_bytes())
    require(handoff_checks.get('passed') is True and handoff_checks.get('asset_count') == 39 and handoff_checks.get('validator_errors') == 0, 'Current39-asset handoff must pass')
    for relative, expected in handoff_checks['source_hashes'].items():
        original = source / relative
        require(plain(original, source).is_file() and sha(original) == expected, 'Stale runtime handoff source: ' + relative)
    for relative in HANDOFF_FILES[:-1]:
        require(handoff_files[relative]['sha256'] == handoff_checks['artifacts'][relative], 'Handoff artifact changed: ' + relative)
    acceptance_data = None
    acceptance_row = None
    if acceptance:
        acceptance = acceptance.resolve(strict=True)
        require(plain(acceptance).is_file(), 'Acceptance must be a regular file')
        acceptance_data = json.loads(acceptance.read_bytes())
        require(acceptance_data.get('passed') is True, 'Acceptance report has unresolved failures')
        for relative, expected in acceptance_data.get('source_hashes', {}).items():
            if relative.startswith(('frontend/src/', 'frontend/public/')) or relative in sources:
                require(sources.get(relative) == expected, 'Acceptance runtime source differs: ' + relative)
        if acceptance_data.get('git_source_commit'):
            require(acceptance_data['git_source_commit'] == commit, 'Acceptance commit differs')
        acceptance_row = dict(bytes=acceptance.stat().st_size, sha256=sha(acceptance))
    video_row = None
    if video:
        video = video.resolve(strict=True)
        require(plain(video).is_file() and video.suffix.lower() == '.mp4' and video.stat().st_size > 0, 'Video must be an actual MP4 file')
        video_row = dict(bytes=video.stat().st_size, sha256=sha(video))
    qa_paths = QA_FILES + [folder + '/' + leaf for folder, leaves in QA_GROUPS.items() for leaf in leaves]
    explicit = []
    for item in qa:
        candidate = Path(item)
        candidate = candidate if candidate.is_absolute() else source / candidate
        candidate = plain(candidate, source)
        require(candidate.is_file(), '--qa accepts a file, not a historical directory')
        explicit.append(candidate.relative_to(source).as_posix())
    qa_files, omitted = {}, []
    for relative in dict.fromkeys(qa_paths + explicit):
        candidate = source / relative
        if not candidate.exists():
            omitted.append(relative)
            continue
        require(plain(candidate, source).is_file(), 'QA delivery input must be a regular file')
        qa_files[relative] = dict(bytes=candidate.stat().st_size, sha256=sha(candidate))
    qa_bytes = sum(row['bytes'] for row in qa_files.values())
    require(qa_bytes <= QA_LIMIT_BYTES, 'Compact QA delivery exceeds100MiB')
    payload_bytes = sum(row['bytes'] for row in dist_files.values()) + sum(row['bytes'] for row in handoff_files.values()) + qa_bytes + (video_row or {}).get('bytes', 0)
    ancestor = output
    while not ancestor.exists():
        ancestor = ancestor.parent
    require(ancestor.is_dir(), 'Output parent must be a directory')
    require(shutil.disk_usage(ancestor).free >= payload_bytes * 2 + 16 * 1024 * 1024, 'Not enough free space for payload and ZIP transaction')
    # All source, format, commit, report, input and capacity checks above are read-only.
    created_directories = []
    cursor = output
    while not cursor.exists():
        created_directories.append(cursor)
        cursor = cursor.parent
    stage = None
    published = []
    try:
        output.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.qoima-desktop-', dir=output)).resolve(strict=True)
        require(stage.parent == output and stage.name.startswith('.qoima-desktop-'), 'Unexpected staging path')
        staged_target = stage / name
        staged_target.mkdir()
        copy_files(dist, staged_target / 'viewer', dist_files)
        (staged_target / 'server.mjs').write_text(server, encoding='utf-8')
        (staged_target / 'Run_V3.cmd').write_bytes(launcher.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
        copy_files(handoff, staged_target / 'handoff', handoff_files)
        copy_files(source, staged_target / 'qa', qa_files)
        qa_index = dict(schema_id='qoima.desktop-qa-delivery.v1', scope='Compact copies of selected current receipts and11model review sheets; original proof scope/status retained, no global gate inferred.', files=qa_files, bytes=qa_bytes, omitted_optional=omitted)
        (staged_target / 'qa/index.json').parent.mkdir(exist_ok=True)
        (staged_target / 'qa/index.json').write_text(json.dumps(qa_index, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if acceptance:
            shutil.copyfile(acceptance, staged_target / 'acceptance.json')
            require(sha(staged_target / 'acceptance.json') == acceptance_row['sha256'], 'Acceptance changed during copy')
        if video:
            shutil.copyfile(video, staged_target / 'QoimaTwin_V3_Overview.mp4')
            require(sha(staged_target / 'QoimaTwin_V3_Overview.mp4') == video_row['sha256'], 'Video changed during copy')
        (staged_target / 'README.md').write_text(README + '\nSelected current QA receipts and review sheets: qa/index.json. Missing optional copies are explicitly listed there.\n', encoding='utf-8')
        require(runtime_paths(source) == sorted(sources), 'Runtime file set changed during packaging')
        for relative, expected in sources.items():
            require(sha(source / relative) == expected, 'Runtime changed during packaging: ' + relative)
        files = tree(staged_target)
        release = dict(schema_id='qoima.desktop-release.v2', created_utc=now.isoformat(), desktop_only=True, git_source_commit=commit, source_runtime_matches_commit=True, build_public_resources_match_source=True, full_TZ_complete=bool(acceptance_data and acceptance_data.get('full_visual_TZ_complete') is True), backend_integration_complete=False, original_character_sha256=ORIGINAL_WORKER, pages=PAGES, files=files, manifest_excludes=['release.json'], source_hashes=sources, acceptance=acceptance_row, video=video_row, qa_delivery=dict(files=len(qa_files), bytes=qa_bytes, omitted_optional=omitted), local_server_provenance=dict(source=helper.relative_to(source).as_posix(), sha256=SERVER_HELPER, changes=['display label', 'loopback port4226', 'home page root', 'MP4/WebM MIME']))
        release_path = staged_target / 'release.json'
        release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        staged_archive = stage / archive.name
        with zipfile.ZipFile(staged_archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for item in sorted(staged_target.rglob('*')):
                if item.is_file():
                    z.write(item, item.relative_to(stage).as_posix(), compress_type=zipfile.ZIP_STORED if item.suffix.lower() == '.mp4' else zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(staged_archive) as z:
            require(z.testzip() is None, 'Package ZIP CRC verification failed')
        result = dict(folder=str(target), archive=str(archive), bytes=staged_archive.stat().st_size, sha256=sha(staged_archive), pages=len(PAGES), manifest_files=len(files), package_files=len(files)+1, release_sha256=sha(release_path), original_character_preserved=True)
        # Same-filesystem publication. Roll back only paths created by this invocation.
        require(not target.exists() and not archive.exists(), 'Concurrent release target appeared')
        staged_target.rename(target)
        published.append(target)
        staged_archive.rename(archive)
        published.append(archive)
        latest = stage / 'latest.json'
        latest.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        os.replace(latest, output / 'V3_desktop_latest.json')
    except BaseException:
        for item in reversed(published):
            remove_created(item, output)
        raise
    finally:
        if stage is not None and stage.exists():
            remove_created(stage, output)
        for directory in created_directories:
            if directory.exists():
                if any(directory.iterdir()):
                    break
                directory.rmdir()
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, help='Verified cold-build dist directory')
    parser.add_argument('--repo', type=Path, help='Selected verified source snapshot')
    parser.add_argument('--git-repo', type=Path, help='Git object repository for an exported source snapshot (defaults to --repo)')
    parser.add_argument('--outputs', type=Path, help='Owned package output directory')
    parser.add_argument('--source-commit', help='Commit whose complete runtime file set and bytes must match')
    parser.add_argument('--acceptance', type=Path, help='Passing root acceptance report')
    parser.add_argument('--video', type=Path, help='Actual recorded overview MP4')
    parser.add_argument('--qa', type=Path, action='append', default=[], help='Additional compact QA file inside --repo; no directories')
    args = parser.parse_args()
    package(args.dist, source_repo=args.repo, outputs=args.outputs, source_commit=args.source_commit, acceptance=args.acceptance, video=args.video, git_repo=args.git_repo, qa=args.qa)
