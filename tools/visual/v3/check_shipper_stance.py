"""Recompute S01 sole grounding from current runtime frames and matching native proof."""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/shipper/P06.2'
RUNTIME = BASE / 'runtime-native-poses.json'
NATIVE = BASE / 'native-path-checks.json'
OUT = BASE / 'stance-checks.json'
EPS = 2e-6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    assert type(value) in (int, float) and math.isfinite(value), ('Invalid numeric primitive', value)
    return value


def vector(value):
    assert isinstance(value, list) and len(value) == 3
    return [number(x) for x in value]


def calculate(runtime, native, runtime_sha, native_sha):
    assert runtime['engine_operation'] is False and native['engine_operation'] is False
    assert native['passed'] is True and native['failure'] is None
    assert native['runtime_pose_sha256'] == runtime_sha, 'Native proof belongs to another runtime'
    frames = runtime['frames']
    assert len(frames) == len(native['frames']) == native['native_frames'] == 594
    assert runtime['checks']['runtime_frames'] == 2954 and runtime['checks']['arbitrary_seeks'] == 100
    assert [(f['mode'], f['time']) for f in frames] == [(f['mode'], f['time']) for f in native['frames']]
    assert collections.Counter(f['mode'] for f in frames) == dict(place=541, scan=51, idle=1, blocked=1)
    base = {foot['side']: vector(foot['world']) for foot in frames[0]['state']['actualFeet']}
    assert set(base) == {'L', 'R'}
    previous, last_stance = {}, {}
    lift_events = collections.defaultdict(list)
    maximum_error = maximum_slip = 0
    samples = 0
    for frame, physical in zip(frames, native['frames']):
        at = number(frame['time'])
        state = frame['state']
        assert state['engine_operation'] is False and state['inventory_mutated'] is False
        assert len(state['actualFeet']) == 2 and {x['side'] for x in state['actualFeet']} == {'L', 'R'}
        assert number(physical['maximum_stance_boot_floor_error_m']) < EPS
        assert all(number(x) >= -EPS for x in physical['boot_floor_heights_m'])
        assert physical['heavy_pallet_unmoved'] is True
        for foot in state['actualFeet']:
            side, point, target = foot['side'], vector(foot['world']), foot['target']
            lift, travel = number(target['lift']), number(target['travel'])
            assert type(target['stance']) is bool and 0 <= lift <= .012 + 1e-12 and 0 <= travel <= .16 + 1e-12
            expected = [base[side][0], lift, base[side][2] - travel]
            maximum_error = max(maximum_error, math.dist(point, expected))
            key = (frame['mode'], side)
            if key in previous and target['stance'] and previous[key]['target']['stance']:
                maximum_slip = max(maximum_slip, math.dist(point, previous[key]['world']))
            previous[key] = foot
            if frame['mode'] == 'place':
                if last_stance.get(side) is True and target['stance'] is False:
                    lift_events[side].append(at)
                last_stance[side] = target['stance']
            samples += 1
        displacement = number(state['displacement_m'])
        assert not state['scanning'] or displacement == 0
        if frame['mode'] == 'place' and at >= 11.4:
            assert displacement == .16
        if frame['mode'] == 'place' and at >= 23:
            assert abs(number(state['body_distance_m'])) < 1e-12
    assert maximum_error < EPS and maximum_slip < EPS
    assert samples == 1188
    assert all(len([t for t in lift_events[side] if t < 17]) == 2 and
               len([t for t in lift_events[side] if t >= 17]) == 2 for side in ['L', 'R'])
    return dict(passed=True, source_kind='visual_fixture_runtime_grounding', engine_operation=False,
        frames=594, foot_samples=samples, maximum_absolute_sole_anchor_target_error_m=maximum_error,
        maximum_consecutive_stance_slip_m=maximum_slip, forward_step_together_cycles=2,
        backward_step_together_cycles=2, actual_swing_starts_s=dict(lift_events),
        scan_static_and_parcel_displacement_and_body_return_checks=True,
        native_boot_support_agreement=True, runtime_pose_sha256=runtime_sha,
        native_report_ref=dict(path=NATIVE.relative_to(ROOT).as_posix(), sha256=native_sha),
        scope='Current actual594runtime poses/1188sole-world targets, consecutive stance slip and independently matching native boot support. Original2forward/2return step-together cycles. No gait speed, operational shipment or whole-warehouse certification.')


def document():
    runtime = json.loads(RUNTIME.read_text(encoding='utf8'))
    native = json.loads(NATIVE.read_text(encoding='utf8'))
    pinned = {RUNTIME: sha(RUNTIME), NATIVE: sha(NATIVE), Path(__file__): sha(Path(__file__))}
    for report in [runtime, native]:
        for relative, expected in report['input_hashes'].items():
            path = (ROOT / relative).resolve()
            assert path.is_relative_to(ROOT.resolve()) and sha(path) == expected, ('Stale grounding source', relative)
    result = calculate(runtime, native, pinned[RUNTIME], pinned[NATIVE])
    result['input_hashes'] = {RUNTIME.relative_to(ROOT).as_posix(): pinned[RUNTIME],
                            Path(__file__).relative_to(ROOT).as_posix(): pinned[Path(__file__)]}
    for path, expected in pinned.items():
        assert sha(path) == expected, ('Concurrent grounding input change', path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    result = document()
    blob = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if args.check_only:
        before = OUT.stat()
        assert OUT.read_bytes() == blob, 'Stale grounding report; full recomputation differs'
        assert OUT.stat().st_mtime_ns == before.st_mtime_ns
    else:
        temporary = OUT.with_suffix('.json.tmp')
        temporary.write_bytes(blob)
        temporary.replace(OUT)
    print(json.dumps(dict(passed=True, check_only=args.check_only, frames=result['frames'],
        foot_samples=result['foot_samples'], maximum_error_m=result['maximum_absolute_sole_anchor_target_error_m'],
        maximum_slip_m=result['maximum_consecutive_stance_slip_m'], sha256=sha(OUT))))


if __name__ == '__main__':
    main()
