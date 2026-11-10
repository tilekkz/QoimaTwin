"""Package only the pinned, independently built preserved V2 frontend.

No npm install/build, server/browser launch or modification of source archives.
Run from any directory with Python 3.10+ and Node 22.12+ available on PATH.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = ROOT / "work/v3/v2-build"
DIST = SNAPSHOT / "frontend/dist"
NAME = "QoimaTwin_V2_Polished"
OUT = ROOT.parents[1] / "outputs" / NAME
ZIP = OUT.with_suffix(".zip")
BRANCH = "codex/twin-v2-polished"
COMMIT = "cb5777f108478aabe3b7117a19d2b471ad79d2de"
LOCK_SHA = "957df69d2e01a197e08968480ac5eeb3afaa135bddb087af0e1e3360514129a9"
FINGERPRINT = ("index-DOPf_3RA.js", "largeWarehouse-DhonVUbu.js")

SERVER = r'''import http from 'node:http';
import {readFile, realpath, stat} from 'node:fs/promises';
import {dirname, extname, isAbsolute, relative, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 12)) {
  console.error('QoimaTwin V2 requires Node.js >=22.12.0.'); process.exit(1);
}
const portText = process.env.QOIMA_PORT ?? '4192';
const port = Number(portText);
if (!/^\d+$/.test(portText) || !Number.isInteger(port) || port < 1 || port > 65535) {
  console.error('QOIMA_PORT must be an integer between 1 and 65535.'); process.exit(1);
}
let root;
try { root = await realpath(resolve(dirname(fileURLToPath(import.meta.url)), 'viewer')); }
catch { console.error('Viewer directory is missing. Extract the entire V2 ZIP first.'); process.exit(1); }
const inside = target => {
  const part = relative(root, target);
  return part === '' || (part !== '..' && !part.startsWith('..' + sep) && !isAbsolute(part));
};
const types = {'.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8',
  '.glb':'model/gltf-binary', '.png':'image/png', '.jpg':'image/jpeg',
  '.jpeg':'image/jpeg', '.webp':'image/webp', '.svg':'image/svg+xml', '.mp3':'audio/mpeg',
  '.wav':'audio/wav', '.ogg':'audio/ogg', '.ico':'image/x-icon'};
const server = http.createServer(async (request, response) => {
  const head = request.method === 'HEAD';
  const fail = (status, message, extra = {}) => {
    response.writeHead(status, {'Content-Type':'text/plain; charset=utf-8',
      'Content-Length':Buffer.byteLength(message), ...extra});
    response.end(head ? undefined : message);
  };
  if (request.method !== 'GET' && !head) {
    request.resume(); fail(405, 'Only GET and HEAD are supported.', {Allow:'GET, HEAD'}); return;
  }
  let pathname;
  try { pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname); }
  catch { fail(400, 'Invalid request path.'); return; }
  if (pathname.includes('\0') || pathname.includes(':')) { fail(400, 'Invalid request path.'); return; }
  let target = resolve(root, '.' + pathname.replaceAll('\\', '/'));
  if (!inside(target)) { fail(403, 'Path is outside the viewer.'); return; }
  try {
    if ((await stat(target)).isDirectory()) target = resolve(target, 'index.html');
    target = await realpath(target);
    if (!inside(target)) { fail(403, 'Path is outside the viewer.'); return; }
    const info = await stat(target);
    if (!info.isFile()) { fail(404, 'File not found.'); return; }
    const data = head ? undefined : await readFile(target);
    response.writeHead(200, {'Content-Type':types[extname(target).toLowerCase()] || 'application/octet-stream',
      'Content-Length':data ? data.length : info.size, 'Cache-Control':'no-cache',
      'X-Content-Type-Options':'nosniff'});
    response.end(data);
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') fail(404, 'File not found.');
    else if (error.code === 'EACCES' || error.code === 'EPERM') fail(403, 'File access denied.');
    else fail(500, 'Unable to read the requested file.');
  }
});
server.on('error', error => {
  console.error(error.code === 'EADDRINUSE'
    ? `QoimaTwin V2: port ${port} is already in use. Close that server or set QOIMA_PORT=4193.`
    : `QoimaTwin V2 cannot bind 127.0.0.1:${port}: ${error.message}`);
  process.exitCode = 1;
});
server.listen(port, '127.0.0.1', () => {
  console.log(`QoimaTwin V2: http://127.0.0.1:${port}/`);
  console.log('Open this URL in a WebGL2 browser. Keep this window open; Ctrl+C stops the server.');
});
'''

LAUNCHER = r'''@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is missing from PATH. Install Node.js 22.12 or newer, then retry.
  pause
  exit /b 1
)
node -e "const [a,b]=process.versions.node.split('.').map(Number);if(a<22||(a===22&&b<12)){console.error('Node.js 22.12 or newer is required.');process.exit(1)}"
if errorlevel 1 (
  pause
  exit /b 1
)
if not defined QOIMA_PORT set "QOIMA_PORT=4192"
echo QoimaTwin V2 - preserved polished version
echo Open http://127.0.0.1:%QOIMA_PORT%/ in your browser.
node "%~dp0server.mjs"
set "QOIMA_EXIT=%ERRORLEVEL%"
echo Server stopped. Exit code: %QOIMA_EXIT%
pause
exit /b %QOIMA_EXIT%
'''

README = f'''# QoimaTwin — отдельная сохранённая V2 Polished

Это автономная статическая версия склада 72×48 м из ветки **{BRANCH}**.
Точный commit: **{COMMIT}**. Главная сборка: **{FINGERPRINT[0]}**;
модуль склада: **{FINGERPRINT[1]}**. Файлы viewer скопированы побайтно
из изолированной сборки этого commit; V3 в пакет не добавлялась.

## Запуск в Windows

1. Полностью распакуйте ZIP, сохранив папку **{NAME}** и все вложенные файлы.
2. Нужен установленный **Node.js 22.12.0 или новее**, доступный командой node,
   и браузер с WebGL2. npm install, интернет и backend для визуального демо не нужны.
3. Запустите **Run_V2.cmd** и откройте **http://127.0.0.1:4192/** в браузере.
   Держите окно сервера открытым. **Ctrl+C** останавливает сервер.

Не открывайте viewer/index.html через file://: ES-модули и GLB загружаются через HTTP.
Сервер слушает только 127.0.0.1. Он не публикует папку в локальную сеть.

Ручной запуск из папки пакета: **node server.mjs**.
Если 4192 занят, в PowerShell: **$env:QOIMA_PORT='4193'; node ./server.mjs**,
затем откройте http://127.0.0.1:4193/. Значение QOIMA_PORT также учитывает launcher.
Пустое/нечисловое значение или порт вне 1…65535 отклоняются явно.

## Что смотреть

Обзор склада, камеры «Сверху», «Поток / упаковка», «Приёмка», «Отгрузка»;
нижние кнопки открывают отдельные модели с четырьмя ракурсами. Кнопка «Референсы»
показывает сохранённые листы. Таймлайн, «Следовать P01», «Следовать заказу»,
скорость, звук и спокойный режим относятся к сохранённой V2 visual-fixture.
Проверка метрических осей/масштаба: http://127.0.0.1:4192/?calibration=v2
(при другом порте замените 4192).

Данные визуального демо синтетические. Это самостоятельный visual-fixture/replay
viewer, а не подключённый производственный складской движок, полный журнал
остатков или доказательство складских KPI. «Открыть Run v2» принимает совместимый
локальный JSON через сохранённый адаптер; доступность кнопки не означает полноту
backend-интеграции. В этом пакете нет backend/API-сервера или производственной БД.

## Состав и воспроизводимость

- **viewer/** — точные HTML/JS/CSS, модели, референсы и статические данные dist V2.
- **server.mjs** — локальный сервер GET/HEAD с проверкой границ viewer.
- **Run_V2.cmd** — Windows launcher с проверкой Node.
- **package-manifest.json** — отсортированные относительные пути, размеры и SHA256
  каждого файла пакета, кроме самого manifest во избежание самоссылки.

Хеш manifest и ZIP записывается в project evidence H08.1. В ZIP ровно одна
корневая папка {NAME}; зависимости node_modules, исходный checkout, junction,
секреты и временные каталоги не поставляются. Повторная упаковка выполняется
project helper tools/visual/v3/package_preserved_v2.py из сохранённого dist;
этот helper не изменяет V2 source/branch и не пересобирает приложение.

Отдельный пакет V3 и руководство сравнения относятся к родительской задаче H08.
Этот архив содержит только сохранённую V2.
'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files(root: Path) -> list[Path]:
    result = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(folder) / name
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError(f"Unexpected link inside package input/output: {path}")
        result.extend(Path(folder) / name for name in names)
    return sorted(result, key=lambda p: p.relative_to(root).as_posix())


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify_snapshot() -> dict:
    if git("rev-parse", BRANCH).decode().strip() != COMMIT:
        raise ValueError("Preserved branch no longer points at the pinned V2 commit")
    if sha256(SNAPSHOT / "frontend/package-lock.json") != LOCK_SHA:
        raise ValueError("Archived V2 lock differs from the accepted installed lock")
    records = git("ls-tree", "-r", "-z", COMMIT, "--", "frontend", "contracts").split(b"\0")
    expected = set()
    for record in filter(None, records):
        info, raw_name = record.split(b"\t", 1)
        mode, kind, oid = info.decode().split()
        name = raw_name.decode("utf-8")
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"Unexpected archived Git entry: {name}")
        path = SNAPSHOT / name
        digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != oid:
            raise ValueError(f"Archived input is not pinned Git content: {name}")
        expected.add(name)
    actual = set()
    for part in ("frontend", "contracts"):
        for folder, dirs, names in os.walk(SNAPSHOT / part, followlinks=False):
            if Path(folder) == SNAPSHOT / "frontend":
                dirs[:] = [name for name in dirs if name not in {"dist", "node_modules"}]
            actual.update((Path(folder) / name).relative_to(SNAPSHOT).as_posix() for name in names)
    if actual != expected:
        raise ValueError(f"Unexpected archived source paths: {sorted(actual ^ expected)}")
    return {"git_files_verified": len(expected), "lock_sha256": LOCK_SHA,
            "commit_time": git("show", "-s", "--format=%cI", COMMIT).decode().strip()}


def reject_v3(paths: list[Path]) -> None:
    forbidden = (b"qoima-144x72-v3", b"/models/v3/", b"/references/v3/")
    for path in paths:
        relative = path.relative_to(DIST)
        if "v3" in [part.lower() for part in relative.parts]:
            raise ValueError(f"V3 path in preserved dist: {relative}")
        if path.suffix.lower() in {".js", ".json", ".html", ".css"}:
            if any(value in path.read_bytes() for value in forbidden):
                raise ValueError(f"V3 runtime marker in preserved dist: {relative}")
        if path.suffix.lower() == ".glb":
            with path.open("rb") as stream:
                header = stream.read(20)
                magic, version, length, size, chunk = struct.unpack("<4sIIII", header)
                if magic != b"glTF" or version != 2 or length != path.stat().st_size or chunk != 0x4E4F534A:
                    raise ValueError(f"Invalid preserved GLB: {relative}")
                data = json.loads(stream.read(size))
            for node in data.get("nodes", []):
                extra = node.get("extras", {})
                if extra.get("namespace") == "v3" or "144x72-v3" in str(extra.get("layout_version", "")):
                    raise ValueError(f"V3 GLB metadata in preserved dist: {relative}")


def main() -> None:
    archived = verify_snapshot()
    source_files = files(DIST)
    if not source_files or not (DIST / "index.html").is_file():
        raise ValueError("Root-built preserved dist is missing")
    index = (DIST / "index.html").read_text(encoding="utf-8")
    if FINGERPRINT[0] not in index or any(not (DIST / "assets" / name).is_file() for name in FINGERPRINT):
        raise ValueError("Preserved build fingerprint differs")
    reject_v3(source_files)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.is_symlink() or (hasattr(OUT, "is_junction") and OUT.is_junction()):
        raise ValueError("Output must be the owned real package directory")
    OUT.mkdir(exist_ok=True)
    shutil.copytree(DIST, OUT / "viewer", dirs_exist_ok=True)
    (OUT / "server.mjs").write_text(SERVER, encoding="utf-8", newline="\n")
    (OUT / "Run_V2.cmd").write_text(LAUNCHER, encoding="ascii", newline="\r\n")
    (OUT / "README_RU.md").write_text(README, encoding="utf-8", newline="\n")
    source_map = {p.relative_to(DIST).as_posix(): (p.stat().st_size, sha256(p)) for p in source_files}
    copied_map = {p.relative_to(OUT / "viewer").as_posix(): (p.stat().st_size, sha256(p))
                  for p in files(OUT / "viewer")}
    if source_map != copied_map:
        raise ValueError("Packaged viewer differs from isolated V2 dist")
    expected_paths = {"viewer/" + name for name in source_map} | {
        "server.mjs", "Run_V2.cmd", "README_RU.md", "package-manifest.json"}
    if {p.relative_to(OUT).as_posix() for p in files(OUT)} - expected_paths:
        raise ValueError("Unexpected existing files in owned package; no automatic deletion performed")
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node is required for server syntax verification")
    subprocess.run([node, "--check", str(OUT / "server.mjs")], check=True)
    manifest = {"package": NAME, "version": "preserved-v2-polished", "branch": BRANCH,
                "commit": COMMIT, "node_requirement": ">=22.12.0", "default_port": 4192,
                "bind_host": "127.0.0.1", "environment_port_override": "QOIMA_PORT",
                "archived_inputs": archived, "build_fingerprint": list(FINGERPRINT),
                "viewer_files": len(source_map), "manifest_excludes_itself": True,
                "files": [{"path": p.relative_to(OUT).as_posix(), "bytes": p.stat().st_size,
                           "sha256": sha256(p)} for p in files(OUT) if p != OUT / "package-manifest.json"]}
    (OUT / "package-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                               encoding="utf-8", newline="\n")
    package_files = files(OUT)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in package_files:
            info = zipfile.ZipInfo(NAME + "/" + path.relative_to(OUT).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    temporary = Path(tempfile.mkdtemp(prefix=".verify-zip-", dir=OUT)).resolve()
    if temporary.parent != OUT.resolve():
        raise ValueError("Temporary extraction escaped owned output")
    try:
        with zipfile.ZipFile(ZIP) as archive:
            expected_names = {NAME + "/" + p.relative_to(OUT).as_posix() for p in package_files}
            if set(archive.namelist()) != expected_names or archive.testzip() is not None:
                raise ValueError("ZIP paths or CRC differ")
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or any(p in {"", ".", ".."} for p in path.parts) or "\\" in info.filename or ":" in info.filename:
                    raise ValueError("Unsafe ZIP path")
            archive.extractall(temporary)
        extracted = temporary / NAME
        if {(p.relative_to(extracted).as_posix(), p.stat().st_size, sha256(p)) for p in files(extracted)} != {
                (p.relative_to(OUT).as_posix(), p.stat().st_size, sha256(p)) for p in package_files}:
            raise ValueError("Actual ZIP extraction differs from package")
    finally:
        # This exact task-created child was resolved and checked above; never
        # remove output/source parents or compute a deletion through another shell.
        if temporary.parent != OUT.resolve() or not temporary.name.startswith(".verify-zip-"):
            raise ValueError("Refusing unconfined temporary cleanup")
        shutil.rmtree(temporary)
    evidence = {"task_id": "H08.1", "owner": "rack_crate", "status": "VERIFY",
                "packaging_helper_sha256": sha256(Path(__file__).resolve()),
                "branch": BRANCH, "commit": COMMIT, "archived_input_checks": archived,
                "package_path": str(OUT), "zip_path": str(ZIP), "zip_bytes": ZIP.stat().st_size,
                "zip_sha256": sha256(ZIP), "manifest_sha256": sha256(OUT / "package-manifest.json"),
                "viewer_files": len(source_map), "viewer_bytes": sum(v[0] for v in source_map.values()),
                "package_files": len(package_files), "viewer_byte_match": True,
                "v3_paths_runtime_markers_and_GLb_namespaces_absent": True,
                "per_file_manifest_verified": True, "zip_CRC_and_path_checks": True,
                "actual_zip_extraction_byte_match": True, "temporary_extraction_removed": True,
                "server_node_syntax_check_exit_code": 0, "server_launched_by_creator": False,
                "browser_or_GPU_launched": False, "build_or_install_performed_by_creator": False,
                "launch_command": f'node "{OUT / "server.mjs"}"',
                "launcher": str(OUT / "Run_V2.cmd"), "default_URL": "http://127.0.0.1:4192/",
                "root_launch_and_browser_QA": "pending; root decides PASS",
                "limits": ["Static preserved V2 visual-fixture/replay; backend and full ledger/KPI integration not included.",
                           "Parent H08 still requires final V3 package, dual comparison guide and publication."],
                "graph": {"project": "qoima-twin", "generation": "2026-11-06T22:22:36Z", "tier": 2,
                          "coverage": "New helper missing, archived work paths excluded; exact direct current-source/artifact fallback used."}}
    (ROOT / "docs/adaptive-v3/evidence/H08.1.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
