"""Encode the real viewer recordings and retain verifiable media metadata."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffmpeg', required=True)
    args = parser.parse_args()
    ffmpeg = Path(args.ffmpeg)
    ffprobe = ffmpeg.with_name('ffprobe.exe' if ffmpeg.suffix == '.exe' else 'ffprobe')
    directory = ROOT / 'work/night-video'
    capture = json.loads((directory / 'recording.json').read_text(encoding='utf-8'))
    if capture['wallDuration'] < 90:
        raise ValueError('Actual viewer capture must contain at least 90 seconds')
    clips = json.loads((directory / 'action-clips/clips.json').read_text(encoding='utf-8'))
    jobs = [(directory / 'viewer-recording.webm', directory / 'QoimaTwin_Night_Demo.mp4', capture['readyOffset'], 90)]
    jobs.extend((directory / 'action-clips' / (clip['name'] + '.webm'),
                 directory / 'action-clips' / (clip['name'] + '.mp4'), clip['readyOffset'], clip['duration']) for clip in clips)
    evidence = []
    for source, target, start, duration in jobs:
        subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(start), '-i', str(source),
                        '-t', str(duration), '-an', '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264',
                        '-preset', 'fast', '-crf', '20', '-movflags', '+faststart', str(target)], check=True)
        probe = json.loads(subprocess.check_output([str(ffprobe), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(target)], text=True))
        stream = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        actual_duration = float(probe['format']['duration'])
        if abs(actual_duration - duration) > .12 or (stream['width'], stream['height']) != (1366, 768):
            raise ValueError('Incorrect encoded duration or dimensions: ' + str(target))
        evidence.append({'path': target.relative_to(directory).as_posix(), 'bytes': target.stat().st_size,
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'duration_s': actual_duration,
                         'codec': stream['codec_name'], 'pixel_format': stream['pix_fmt'],
                         'width': stream['width'], 'height': stream['height'], 'frame_rate': stream['avg_frame_rate'],
                         'source_trim_s': start, 'audio': 'muted capture; no audio stream'})
        print(target.name + ': ' + str(actual_duration) + 's', flush=True)
    frames = directory / 'control-frames'
    frames.mkdir(exist_ok=True)
    for second in [8, 24, 44, 66, 84]:
        subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(second),
                        '-i', str(jobs[0][1]), '-frames:v', '1', str(frames / f'{second:02d}s.png')], check=True)
    report = {'kind': 'actual interactive Vue/Three.js viewer recordings; synthetic visual fixture; no rendered stand-in scenes',
              'main_capture': capture, 'action_clips': clips, 'encoded_files': evidence,
              'control_frames': [f'control-frames/{second:02d}s.png' for second in [8, 24, 44, 66, 84]]}
    (directory / 'MEDIA_VERIFICATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
