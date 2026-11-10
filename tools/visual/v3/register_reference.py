"""Root-only registry update AFTER actual independent reference image review."""
from pathlib import Path
import argparse,datetime,hashlib,html,json,re,shutil
ROOT=Path(__file__).resolve().parents[3]
def meta(path):
    p=ROOT/path
    return dict(path=path,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
    parser=argparse.ArgumentParser();parser.add_argument('review_record');args=parser.parse_args()
    review=json.loads(Path(args.review_record).read_text(encoding='utf-8'))
    assert review['root_actual_saved_png_opened'] is True
    rid,task,asset,name=(review[k] for k in ['reference_id','task_id','asset_id','prefix'])
    assert all(re.fullmatch(r'[A-Za-z0-9_.-]+',v) for v in [rid,task,asset,name])
    base=ROOT/'assets/references/v3';artifact=meta(f'assets/references/v3/{name}.png')
    assert artifact['sha256']==review['expected_sha256']
    artifact['dimensions_px']=review['dimensions_px']
    ep=f'docs/adaptive-v3/evidence/{task}-reference.json'
    e=dict(review,status='reference_root_PASS_model_PENDING',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected_artifact=artifact)
    (ROOT/ep).write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest=base/'manifest.json';m=json.loads(manifest.read_text(encoding='utf-8'))
    assert not any(r['reference_id']==rid for r in m['references']),'Already registered; do not silently replace'
    m['references'].append(dict(reference_id=rid,root_acceptance='PASS',creator_review_status='VERIFY',artifact=artifact,
        provenance=meta(f'assets/references/v3/provenance/{name}.json'),evidence=meta(ep),card=f'docs/adaptive-v3/tasks/{task}.md',
        use='Independent production four views; exact declared targets govern geometry. Model/action acceptance separate.'))
    m['prompts'].append(meta(f'assets/references/v3/prompts/{name}.txt'))
    m['reference_count']=len(m['references']);m['asset_reference_bindings'][asset]=rid
    manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    catalog=base/'contact-sheet.html';s=catalog.read_text(encoding='utf-8')
    s=re.sub(r'\d+ current concepts',f"{m['reference_count']} current concepts",s)
    s=s.replace('</main>',f'<section class="summary"><h2>{html.escape(rid)} · reference root PASS</h2><img src="{name}.png" alt="Independent front side rear quarter"><p>{html.escape(review["root_review"])}</p></section></main>')
    catalog.write_text(s,encoding='utf-8')
    rp=base/'review.md';rp.write_text(rp.read_text(encoding='utf-8')+'\n\n'+rid+' root PASS: '+review['root_review']+'\n',encoding='utf-8')
    for folder in ['frontend/public/references/v3','frontend/dist/references/v3']:
        for file in ['manifest.json','contact-sheet.html','review.md',name+'.png',name+'.targets.json']:
            shutil.copy2(base/file,ROOT/folder/file)
    print(json.dumps(dict(registered=rid,current_concepts=m['reference_count'],model_accepted=False)))
if __name__=='__main__':main()
