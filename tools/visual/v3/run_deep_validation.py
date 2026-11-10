"""Run the tracked Python validation manifest against a DIFFERENT isolated repo.

Launch this controlling driver from the source checkout; --repo points at a fresh
isolated worktree/export. Child SCRIPT paths always belong to that target repo,
while --python may name the controlling checkout's existing virtualenv Python.
No installs, downloads, deletes, moves or evidence repairs are performed.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

SOURCE_REPO = Path(__file__).resolve().parents[3]
SUITE_PATH = Path(__file__).with_name('deep_validation_suite.json')
SCHEMA_ID = 'qoima.deep-validation-suite.v1'
MODES = {'check_only', 'check_only_conditional_write', 'isolated_report_write', 'owned_output'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def inside(root, relative, must_exist=False):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('INVALID_REPOSITORY_PATH: ' + str(relative))
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('OUTSIDE_REPOSITORY: ' + relative)
    resolved = (root / p).resolve(strict=must_exist)
    if not resolved.is_relative_to(root):
        raise ValueError('SYMLINK_ESCAPES_ISOLATED_REPOSITORY: ' + relative)
    return resolved


def validate_suite(data):
    allowed = {'schema_id', 'schema_version', 'description', 'offline_intended', 'execution_policy', 'source_documents', 'commands'}
    if set(data) != allowed or data['schema_id'] != SCHEMA_ID or data['schema_version'] != '1.0.0':
        raise ValueError('UNSUPPORTED_SUITE_SCHEMA')
    if data['offline_intended'] is not True or not isinstance(data['commands'], list) or len(data['commands']) != 28:
        raise ValueError('EXACT_28_OFFLINE_COMMANDS_REQUIRED')
    ids = set()
    fields = {'id', 'script', 'args', 'cwd', 'timeout_s', 'mode', 'required_existing_paths', 'write_hazards', 'note'}
    for row in data['commands']:
        if set(row) != fields or not isinstance(row['id'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,80}', row['id']) or row['id'] in ids:
            raise ValueError('INVALID_OR_DUPLICATE_COMMAND')
        ids.add(row['id'])
        if not isinstance(row['script'], str) or not row['script'].startswith('tools/visual/v3/') or not row['script'].endswith('.py'):
            raise ValueError('ONLY_TRACKED_VISUAL_PYTHON_SCRIPTS_ALLOWED')
        if row['mode'] not in MODES or row['cwd'] != '.' or type(row['timeout_s']) is not int or not 1 <= row['timeout_s'] <= 3600:
            raise ValueError('INVALID_COMMAND_MODE_CWD_OR_TIMEOUT')
        for name in ['args', 'required_existing_paths', 'write_hazards']:
            if not isinstance(row[name], list) or not all(isinstance(x, str) for x in row[name]):
                raise ValueError('INVALID_COMMAND_LIST: ' + name)
        if '--freeze-inputs' in row['args']:
            raise ValueError('INPUT_FREEZING_IS_FORBIDDEN')
        if row['mode'].startswith('check_only') and '--check-only' not in row['args']:
            raise ValueError('CHECK_ONLY_FLAG_REQUIRED')
        if row['mode'] == 'owned_output' and ('--output' not in row['args'] or row['args'].index('--output') + 1 >= len(row['args']) or not row['args'][row['args'].index('--output') + 1].startswith('{out}/')):
            raise ValueError('OWNED_OUTPUT_REQUIRED')
        if Path(row['script']).name == 'build_adapted_assignment.py' and 'docs/v3/contract-proposals/adaptation-evaluation-v3.json' not in row['required_existing_paths']:
            raise ValueError('C11_EXISTING_EVALUATION_REQUIRED')
    return data


class WindowsJob:
    """Kill-on-close containment for exactly this driver's newly spawned child tree."""
    def __init__(self, process):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong), ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ['read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes']]
        class Limits(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.kernel.SetInformationJobObject.restype = w.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = w.BOOL
        self.kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        self.kernel.TerminateJobObject.restype = w.BOOL
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.kernel.CloseHandle.restype = w.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        try:
            if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.kernel.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise

    def terminate(self):
        if self.handle and not self.kernel.TerminateJobObject(self.handle, 124):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def canonical_output_guards(suite):
    paths = set()
    for row in suite['commands']:
        for rel in row['write_hazards']:
            if not rel.startswith('{out}') and '*' not in rel:
                p = inside(SOURCE_REPO, rel)
                if p.is_file():
                    paths.add(p)
    packet = SOURCE_REPO / 'docs/v3/contract-proposals/n2-n3-physical-interfaces-v1'
    if packet.is_dir():
        paths.update(p for p in packet.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.update([Path(__file__).resolve(), SUITE_PATH.resolve()])
    return {str(p): digest(p) for p in sorted(paths)}


def prepare_command(row, repo, python, out):
    script = inside(repo, row['script'], must_exist=True)
    source_script = inside(SOURCE_REPO, row['script'])
    if source_script.exists() and os.path.samefile(script, source_script):
        raise ValueError('CHILD_SCRIPT_IS_SOURCE_OR_HARDLINK: ' + row['script'])
    for rel in row['required_existing_paths']:
        p = inside(repo, rel, must_exist=True)
        if not p.is_file():
            raise ValueError('REQUIRED_BASELINE_FILE_MISSING: ' + rel)
    for rel in row['write_hazards']:
        if rel.startswith('{out}/'):
            target = (out / rel[len('{out}/'):]).resolve()
            if not target.is_relative_to(out):
                raise ValueError('OUTPUT_ESCAPES_OWNED_REPORT_DIR')
        else:
            target = inside(repo, rel)
            original = inside(SOURCE_REPO, rel)
            if target.is_file() and original.is_file() and os.path.samefile(target, original):
                raise ValueError('EVIDENCE_IS_HARDLINKED_TO_SOURCE: ' + rel)
    args = []
    for value in row['args']:
        if '{out}' in value:
            if not value.startswith('{out}/'):
                raise ValueError('INVALID_OUTPUT_PLACEHOLDER')
            target = (out / value[len('{out}/'):]).resolve()
            if not target.is_relative_to(out):
                raise ValueError('OUTPUT_ESCAPES_OWNED_REPORT_DIR')
            args.append(str(target))
        else:
            args.append(value)
    return [str(python), '-X', 'utf8', '-B', str(script), *args], script


def run_one(row, repo, python, out, env):
    start = time.monotonic()
    result = {'id': row['id'], 'script': row['script'], 'mode': row['mode'], 'write_hazards': row['write_hazards'], 'started_at_utc': utc(), 'timeout_s': row['timeout_s'], 'executed': False, 'passed': False, 'status': 'PRECONDITION_FAILED', 'exit_code': None, 'timed_out': False}
    stdout_path, stderr_path = out / (row['id'] + '.stdout.txt'), out / (row['id'] + '.stderr.txt')
    process = job = None
    try:
        script = inside(repo, row['script'], must_exist=True)
        result.update(script_sha256_before=digest(script))
        command, script = prepare_command(row, repo, python, out)
        result.update(command=command, cwd=str(repo))
        with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
            kwargs = {'cwd': repo, 'env': env, 'stdin': subprocess.DEVNULL, 'stdout': stdout, 'stderr': stderr}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs['start_new_session'] = True
            process = subprocess.Popen(command, **kwargs)
            result.update(executed=True, pid=process.pid, process_started_at_utc=utc())
            if os.name == 'nt':
                job = WindowsJob(process)
            try:
                result['exit_code'] = process.wait(timeout=row['timeout_s'])
                result['status'] = 'PASSED' if process.returncode == 0 else 'FAILED'
                result['passed'] = process.returncode == 0
            except subprocess.TimeoutExpired:
                result.update(status='TIMED_OUT', timed_out=True)
                if job:
                    job.terminate()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                result['exit_code'] = process.wait(timeout=10)
        result['script_sha256_after'] = digest(script)
        if result['script_sha256_after'] != result['script_sha256_before']:
            result.update(passed=False, status='SOURCE_SCRIPT_CHANGED_DURING_RUN')
    except KeyboardInterrupt:
        result.update(passed=False, status='CANCELLED', interrupted=True)
        if process and process.poll() is None:
            if job:
                job.terminate()
            elif os.name != 'nt':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.terminate()
            result['exit_code'] = process.wait(timeout=10)
    except Exception as error:
        result.update(passed=False, status='INFRASTRUCTURE_ERROR' if result['executed'] else 'PRECONDITION_FAILED', error=f'{type(error).__name__}: {error}')
        if process and process.poll() is None:
            if job:
                job.terminate()
            else:
                process.terminate()  # Exactly this tracked newly spawned child.
            try:
                result['exit_code'] = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                result['exit_code'] = process.wait(timeout=10)
    finally:
        if job:
            job.close()  # Any descendant left by this child is contained in its job.
        result['elapsed_s'] = round(time.monotonic() - start, 6)
        result['finished_at_utc'] = utc()
        for label, p in [('stdout', stdout_path), ('stderr', stderr_path)]:
            if not p.exists():
                p.write_bytes(b'')
            if p.exists():
                result[label] = {'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)}
        result['owned_child_exited'] = process is None or process.poll() is not None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='Absolute DIFFERENT isolated worktree/export root')
    parser.add_argument('--python', type=Path, required=True, help='Absolute existing Python EXE; may be the source checkout virtualenv')
    parser.add_argument('--out', type=Path, required=True, help='Absolute NEW output directory; existing paths are refused')
    args = parser.parse_args()
    for key in ['repo', 'python', 'out']:
        if not getattr(args, key).is_absolute():
            parser.error('--' + key + ' must be absolute')
    repo, python, out = args.repo.resolve(strict=True), args.python.resolve(strict=True), args.out.resolve()
    if not repo.is_dir() or not python.is_file():
        parser.error('Repository directory and Python EXE must exist')
    if repo == SOURCE_REPO or os.path.samefile(repo, SOURCE_REPO):
        parser.error('Refusing the controlling/source repository; provide a DIFFERENT isolated worktree/export')
    if out.exists():
        parser.error('Refusing existing --out path; use a new owned report directory')
    for rel in ['tools', 'docs', 'assets', 'contracts', 'frontend/public']:
        p = inside(repo, rel, must_exist=True)
        if not p.is_dir():
            parser.error('Required isolated repository directory missing: ' + rel)
    suite_raw = SUITE_PATH.read_bytes()
    suite = validate_suite(json.loads(suite_raw))
    guards = canonical_output_guards(suite)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'suite.json').write_bytes(suite_raw)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    if hasattr(signal, 'SIGTERM'):
        def stop_owned(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop_owned)
    results, began = [], time.monotonic()
    for row in suite['commands']:
        result = run_one(row, repo, python, out, env)
        results.append(result)
        progress = {'schema_id': 'qoima.deep-validation-progress.v1', 'results': results, 'elapsed_s': round(time.monotonic() - began, 6)}
        (out / 'progress.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: result[k] for k in ['id', 'status', 'passed', 'exit_code', 'elapsed_s']}, ensure_ascii=False), flush=True)
        if result.get('interrupted'):
            break
    changed = [p for p, expected in guards.items() if not Path(p).is_file() or digest(p) != expected]
    report = {'schema_id': 'qoima.deep-validation-run.v1', 'passed': all(r['passed'] for r in results) and not changed, 'source_kind': 'visual_fixture', 'engine_operation': False, 'controller_source_repo': str(SOURCE_REPO), 'isolated_repo': str(repo), 'python_executable': str(python), 'suite_sha256': hashlib.sha256(suite_raw).hexdigest(), 'driver_sha256': digest(__file__), 'command_count': len(results), 'planned_command_count': len(suite['commands']), 'cancelled': any(r.get('interrupted') for r in results), 'passed_count': sum(r['passed'] for r in results), 'failed_count': sum(not r['passed'] for r in results), 'canonical_source_guards': guards, 'canonical_source_drift': changed, 'results': results, 'elapsed_s': round(time.monotonic() - began, 6), 'finished_at_utc': utc(), 'limitations': ['Offline intent is established by the reviewed manifest/scripts, not an OS-level network sandbox.', 'Legacy validators may rewrite evidence ONLY inside the isolated target; stale check-only artifacts are preserved as failures.', 'This report is validation evidence, not authoritative engine output or a completion claim for unimplemented workflows.']}
    (out / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'commands': len(results), 'failures': report['failed_count'], 'canonical_source_drift': changed, 'out': str(out)}, ensure_ascii=False), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
