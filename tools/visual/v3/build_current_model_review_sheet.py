"""Compose existing actual browser captures and their bound references for review."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps

ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--run',type=Path,required=True)
 args=parser.parse_args();run=args.run.resolve(strict=True)
 assert run.is_relative_to(ROOT/'work'), 'Review inputs must stay in the repository work folder'
 refs=json.loads((ROOT/'frontend/public/references/v3/manifest.json').read_text(encoding='utf-8'))
 by_id={r['reference_id']:r for r in refs['references']}
 records=[]
 for folder in sorted(run.iterdir()):
  if not folder.is_dir() or not all((folder/(v+'.png')).is_file() for v in ['front','rear','side','quarter']):continue
  entry=by_id.get(refs['asset_reference_bindings'].get(folder.name))
  reference=ROOT/'frontend/public/references/v3'/Path(entry['artifact']['path']).name if entry else None
  cells=[reference]+[folder/(v+'.png') for v in ['front','rear','side','quarter']]
  records.append({'asset_id':folder.name,'cells':cells,'reference_id':entry['reference_id'] if entry else None})
 output=run/'review-sheets';output.mkdir(exist_ok=True)
 cell_w,cell_h,row_h=244,194,226
 index=[]
 for start in range(0,len(records),3):
  part=records[start:start+3];sheet=Image.new('RGB',(cell_w*5,50+row_h*len(part)),'#f4f5f0');draw=ImageDraw.Draw(sheet)
  for col,title in enumerate(['Bound reference','Native front','Native rear','Native side','Native quarter']):draw.text((col*cell_w+8,10),title,fill='#163e45')
  for row,record in enumerate(part):
   top=50+row*row_h
   for col,p in enumerate(record['cells']):
    left=col*cell_w
    if p and p.is_file():
     with Image.open(p) as source:
      thumb=ImageOps.contain(source.convert('RGB'),(cell_w-10,cell_h-8))
      sheet.paste(thumb,(left+(cell_w-thumb.width)//2,top+(cell_h-thumb.height)//2))
    else:draw.text((left+8,top+70),'No assigned reference',fill='#6c7975')
   draw.text((8,top+cell_h+3),record['asset_id'],fill='#163e45')
  p=output/f'{start//3+1:02d}.png';sheet.save(p)
  index.append({'sheet':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'assets':[{'asset_id':r['asset_id'],'reference_id':r['reference_id'],'source_files':[{'path':q.relative_to(ROOT).as_posix(),'sha256':sha(q)} for q in r['cells'] if q and q.is_file()]} for r in part]})
 (output/'index.json').write_text(json.dumps({'scope':'Derived review sheets only; no new rendering or automatic visual acceptance','sheets':index},indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'sheets':len(index),'models':len(records),'output':str(output)}))

if __name__=='__main__':main()
