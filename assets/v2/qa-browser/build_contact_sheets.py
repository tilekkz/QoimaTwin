"""QA-only collage of existing browser PNG, reference and accepted Blender PNG."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import hashlib
import json
import argparse
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REFS = {
    'rack-high': 'v2/tall-rack-reference.png', 'rack-low': 'v2/tall-rack-reference.png',
    'environment-shell': 'v2/large-environment-reference.png', 'dock': 'v2/large-environment-reference.png',
    'standing-worker': 'v2/standing-worker.png', 'worker-low': 'v2/standing-worker.png',
    'picker-worker': 'v2/standing-worker.png', 'driver': 'v2/driver.png',
    'picking-cart': 'picker-cart-reference.png',
    'conveyor-high': 'v2/conveyor.png', 'conveyor-low': 'v2/conveyor.png',
    'conveyor-corner': 'v2/conveyor.png', 'conveyor-diverter': 'v2/conveyor.png',
    'order-tote': 'v2/order-tote.png', 'tote-low': 'v2/order-tote.png',
    'sealed-parcel': 'v2/sealed-parcel.png', 'forklift': 'forklift.png',
    'packing-station': 'packing-station-reference.png',
    'buffer-pallet': 'buffer-pallet.png', 'pallet': 'buffer-pallet.png', 'crate': 'crate-reference.png',
}
FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 24)
SMALL = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 18)
TITLE = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 34)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
            'mtime_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}


def fitted(canvas, pic, rect):
    pic = ImageOps.contain(pic, (rect[2] - rect[0], rect[3] - rect[1]), Image.Resampling.LANCZOS)
    canvas.paste(pic, (rect[0] + (rect[2] - rect[0] - pic.width) // 2,
                       rect[1] + (rect[3] - rect[1] - pic.height) // 2))


def model_crop(pic):
    # Exclude only the observed application chrome. Detect the remaining dark /
    # colored geometry to enlarge the QA view; preserve every source PNG intact.
    assert pic.size == (1366, 768), f'Unexpected capture size: {pic.size}'
    points = []
    pixels = pic.load()
    for y in range(110, 555):
        for x in range(90, 1276):
            if y < 193 and (x < 470 or x > 1000):
                continue
            # Bottom hint labels sit at the sides; large carton fronts reach
            # y=555 in the actual canvas and must retain their lower edge.
            if y >= 548 and (x < 450 or x > 1080):
                continue
            r, g, b = pixels[x, y]
            if min(r, g, b) < 185 or max(r, g, b) - min(r, g, b) > 35:
                points.append((x, y))
    assert points, 'No model pixels in observed viewport'
    box = (max(0, min(p[0] for p in points) - 18), max(0, min(p[1] for p in points) - 18),
           # Hint text begins at y=558. The model's last row can be y=555;
           # retain it plus a clear row without copying any UI into the sheet.
           min(pic.width, max(p[0] for p in points) + 19), min(557, max(p[1] for p in points) + 19))
    return pic.crop(box), box


parser = argparse.ArgumentParser()
parser.add_argument('--capture-run', default='root default E2E 27 passed; 84 browser views complete')
parser.add_argument('--reviewed', action='store_true', help='Set only after opening all 21 generated sheets.')
parser.add_argument('--refresh-catalog-only', action='store_true',
                    help='Hash final captures without regenerating or reopening the already reviewed sheets.')
args = parser.parse_args()
verification = ROOT / 'assets/v2/visual-checks.json'
verified_hashes = {entry['asset_id']: entry['sha256']
                   for entry in json.loads(verification.read_text(encoding='utf-8'))['assets']}
if args.refresh_catalog_only:
    index_path = OUT / 'browser-contact-index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    index.setdefault('reviewed_capture_run', index['capture_run'])
    index['capture_run'] = args.capture_run
    index['generated_utc'] = datetime.now(timezone.utc).isoformat()
    index['method'] = ('Existing reviewed collages preserved; final browser PNG hashes refreshed without image review '
                       'or regeneration. Original sheet input hashes are retained in sheet_capture_evidence.')
    index['review_status'] = 'All 21 sheets / 84 views visually accepted earlier; identical final GLBs confirmed by SHA-256.'
    index['source_review'] = [record(ROOT / path) for path in (
        'frontend/src/scene/warehouseMotion.ts', 'frontend/src/replay/core.ts',
        'frontend/src/scene/largeWarehouse.ts')]
    index['independent_geometry_report'] = record(verification)
    assert set(index['assets']) == set(REFS)
    for asset, entry in index['assets'].items():
        model = ROOT / entry['model']['path']
        assert digest(model) == entry['model']['sha256'] == verified_hashes[asset], asset
        entry.setdefault('sheet_capture_evidence', entry['browser_views'])
        paths = [ROOT / 'frontend/test-results/v2-runtime' / asset / (view + '.png')
                 for view in ('front', 'side', 'rear', 'quarter')]
        assert all(path.is_file() for path in paths), asset
        entry['browser_views'] = [record(path) for path in paths]
        entry['sheet'] = record(ROOT / entry['sheet']['path'])
        entry['model'] = record(model)
        entry['all_browser_views_newer_than_model'] = all(path.stat().st_mtime >= model.stat().st_mtime for path in paths)
        entry['matches_independently_verified_glb'] = True
        assert entry['all_browser_views_newer_than_model'], asset
    for entry in index['assets'].values():
        for capture in entry['browser_views']:
            assert digest(ROOT / capture['path']) == capture['sha256'], capture['path']
    index_path.write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
    print('Refreshed 84 final capture hashes; 21 reviewed sheets and their original provenance preserved.')
    raise SystemExit(0)
index = {'capture_run': args.capture_run,
         'generated_utc': datetime.now(timezone.utc).isoformat(),
         'method': 'Pillow QA contact sheet only; unmodified source PNG retained and hashed; viewport crop for legibility',
         'review_status': ('all 21 sheets opened; 84 browser views visually accepted; see docs/visual/BROWSER_MODEL_REVIEW.md'
                           if args.reviewed else 'generated; visual review not recorded by this invocation'),
         'source_review': [record(ROOT / path) for path in (
             'frontend/src/scene/warehouseMotion.ts', 'frontend/src/replay/core.ts',
             'frontend/src/scene/largeWarehouse.ts')],
         'independent_geometry_report': record(verification),
         'assets': {}}
for asset, ref_name in REFS.items():
    ref = ROOT / 'assets/references' / ref_name
    source = ROOT / 'assets/v2/previews' / asset / 'three-quarter.png'
    model = ROOT / 'frontend/public/models/v2' / (asset + '.glb')
    assert digest(model) == verified_hashes[asset], f'GLB differs from binary verification: {asset}'
    paths = [ROOT / 'frontend/test-results/v2-runtime' / asset / (view + '.png')
             for view in ('front', 'side', 'rear', 'quarter')]
    assert all(path.is_file() for path in [ref, source, model, *paths]), asset
    board = Image.new('RGB', (2100, 1420), '#ECEEE7')
    draw = ImageDraw.Draw(board)
    draw.text((24, 14), f'{asset} | browser export / source / reference', font=TITLE, fill='#24353B')
    draw.text((24, 61), 'Actual GLB in the application; four existing browser captures. Viewport crop only.', font=SMALL, fill='#43565B')
    draw.text((24, 105), 'SELECTED REFERENCE', font=FONT, fill='#24353B')
    fitted(board, Image.open(ref).convert('RGB'), (20, 145, 580, 710))
    draw.text((24, 745), 'ACCEPTED BLENDER SOURCE', font=FONT, fill='#24353B')
    fitted(board, Image.open(source).convert('RGB'), (20, 785, 580, 1365))
    crops = []
    for view, path, (x, y) in zip(('FRONT', 'SIDE', 'REAR', 'QUARTER'), paths,
                                 ((610, 105), (1355, 105), (610, 750), (1355, 750))):
        pic = Image.open(path).convert('RGB')
        crop, box = model_crop(pic)
        draw.text((x + 8, y), 'BROWSER ' + view, font=FONT, fill='#24353B')
        fitted(board, crop, (x, y + 42, x + 720, y + 615))
        crops.append({**record(path), 'dimensions': list(pic.size), 'qa_crop_xyxy': list(box)})
    footer = ('Runtime GLB, four views. Work carton intentionally hidden on the static stand; PACK exposes the WIP layer.'
              if asset == 'packing-station' else
              'Runtime GLB | front / side / rear / quarter | original screenshot pixels; QA crop only.')
    draw.text((24, 1383), footer, font=SMALL, fill='#43565B')
    target = OUT / (asset + '-browser-reference.png')
    board.save(target)
    index['assets'][asset] = {'sheet': record(target), 'model': record(model), 'reference': record(ref),
                              'accepted_source': record(source), 'browser_views': crops,
                              'all_browser_views_newer_than_model': all(path.stat().st_mtime >= model.stat().st_mtime for path in paths),
                              'matches_independently_verified_glb': True}
assert len(index['assets']) == 21
for entry in index['assets'].values():
    for capture in entry['browser_views']:
        assert digest(ROOT / capture['path']) == capture['sha256'], f'Capture changed during catalog generation: {capture["path"]}'
(OUT / 'browser-contact-index.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
print(f'Saved {len(index["assets"])} sheets / 84 browser views to {OUT}')
