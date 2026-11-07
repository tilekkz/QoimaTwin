from pathlib import Path
import json,sys,datetime,re,subprocess
root=Path(__file__).resolve().parents[3]; doc=root/'docs/adaptive-v3'
id,status,owner=sys.argv[1:4]; note=sys.argv[4] if len(sys.argv)>4 else ''
p=doc/'task-state.json'; state=json.loads(p.read_text(encoding='utf-8'))
row=next(r for r in state['tasks'] if r['id']==id)
if status=='ACTIVE':
    assert not [r['id'] for r in state['tasks'] if r['status']=='ACTIVE' and r['owner']==owner and r['id']!=id]
if status in ['ACTIVE','PASS']:
    assert all(next(r for r in state['tasks'] if r['id']==dep)['status']=='PASS' for dep in row['depends_on'])
if status=='PASS':
    assert all(next(r for r in state['tasks'] if r['id']==child)['status']=='PASS' for child in row.get('children',[])), 'Parent has unfinished children'
row.update(status=status,owner=owner)
changed_ids={id}
if note: row['actual']=note
for r in state['tasks']:
    dependencies_pass=all(next(x for x in state['tasks'] if x['id']==dep)['status']=='PASS' for dep in r['depends_on']+r.get('children',[]))
    if r['status']=='READY' and not dependencies_pass:
        r['status']='TODO'
        changed_ids.add(r['id'])
    elif r['status']=='TODO' and dependencies_pass:
        r['status']='READY'
        changed_ids.add(r['id'])
state['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
p.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for r in state['tasks']:
    if r['id'] not in changed_ids: continue
    card=doc/'tasks'/f'{r["id"]}.md'; text=card.read_text(encoding='utf-8')
    text=re.sub(r'^- Status: .+$','- Status: '+r['status'],text,flags=re.M)
    if r['id']==id: text=re.sub(r'^- Owner: .+$','- Owner: '+r['owner'],text,flags=re.M)
    if r['id']==id and note:
        def fill_actual(match):
            body=match.group(2)
            return match.group(1)+note+'\n' if ('Not executed' in body or 'Не выполнялось' in body or 'Not implemented' in body) else match.group(0)
        text=re.sub(r'(## (?:Actual / evidence|Фактически получено / evidence)\n\n)([\s\S]*?)(?=\n##|$)',fill_actual,text,count=1)
        if status=='PASS':
            text=text.replace('Не исследовано.','Существенных открытых дефектов по этому результату нет; исправления и повторные проверки указаны в evidence/checkpoint.').replace('Not investigated.','No material unresolved defect for this result; fixes and retest evidence are recorded in checkpoints.')
    if r['id']==id and note: text+='\n## Checkpoint '+state['updated_at']+'\n\n'+note+'\n'
    card.write_text(text,encoding='utf-8')
board='''# QoimaTwin v3 — task board

Source: `brief/01_START_CODEX.md` + `brief/03_MICROTASKS.md`. Cards: `tasks/ID.md`.
One ACTIVE card per executor. Reviewed artifacts gate dependent work; broad parents gain children before execution.
V2 preserved; visual fixtures and backend runs have separate labels. Root alone updates central state.

| ID | Status | Owner | Dependencies | Result |
|---|---|---|---|---|
'''+''.join(f'| [{r["id"]}](tasks/{r["id"]}.md) | {r["status"]} | {r["owner"]} | {",".join(r["depends_on"]) or "—"} | {r["title"]} |\n' for r in state['tasks'])
(doc/'TASK_BOARD.md').write_text(board,encoding='utf-8')
resume=doc/'RESUME.md'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
branch=subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()
ready=[r['id'] for r in state['tasks'] if r['status']=='READY']
active=[r for r in state['tasks'] if r['status'] in ['ACTIVE','VERIFY','FIX']]
passed=[r['id'] for r in state['tasks'] if r['status']=='PASS']
txt=f'''# QoimaTwin v3 — resume

Updated UTC: {state['updated_at']}
Workspace: `{root.as_posix()}`
Branch: `{branch}`; HEAD observed at this state update: `{head}`.
Existing goal: complete visual v3 per `brief/01_START_CODEX.md`. Read live goal status; do not create a duplicate goal.

## Current checkpoint

{id} {status} ({owner}): {note}

PASS ({len(passed)}/{len(state['tasks'])} cards, including expanded children): {', '.join(passed)}.
ACTIVE/VERIFY/FIX: {', '.join(r['id']+' '+r['status']+' '+r['owner'] for r in active) or 'none'}.
Next READY: {', '.join(ready) or 'none; inspect dependency state'}.
Read the current card, its exact inputs and evidence before resuming. Use `python tools/visual/v3/update_task_state.py ID STATUS OWNER "review note"` for root state transitions; agents edit only their card/artifacts and request root review.

## Decisions and preservation

V3 is144×72×8m with24people, six ports, eight cargo archetypes and five storage types. New square cartoon references precede model geometry. Details: `brief/02_DESIGN_V3.md`, source queue `brief/03_MICROTASKS.md`, card expansion `brief/04_TASK_CARD_EXAMPLES.md`.
Ownership and boundary: `OWNERSHIP.md`; current frontend facts: `FRONTEND_MAP.md`.
User requires separate V2/V3 Git branches and runnable packages with friend test/choice guide: `DUAL_VERSION_DELIVERY.md`. Preserved V2 ref and current V3 fork are in `work/v3/git-preservation.json`; final publishing and dual-package checks remain H08.
V2 original240dirtypaths: `work/v3/start-state.json`; verified240copies/96688631bytes: `work/v3/backup-manifest.json`. Original files retained. Shared21contracts: `work/v3/protected-contracts.json`.
Read-only remote fetch reached backend-core dd6e7ba, no merge. Visual/analytical/actual engine labels stay distinct; separate visual_complete/backend_integration_complete.
Evidence index: `ASSET_INVENTORY.md`, `V2_LIMITATIONS.md`, `evidence/viewer-capture.json`. Existing V2 snapshots are not V3 acceptance.

## Tools and next execution

Background Blender: `C:/Program Files/Blender Foundation/Blender 5.0/blender.exe`; separate v3 output files. System Python has Pillow; repo .venv for current project validators. Root owns live Blender and localhost browser/performance work; no concurrent heavy benchmark/render.
Existing baseline viewer: `node work/night-static/server.mjs`, http://127.0.0.1:4180; final V2 production script index-DOPf_3RA.js. Fresh capture command: `node work/v3/capture-v2.mjs`.
Reference authority: `assets/references/v3/manifest.json` and current asset bindings/review. Additional dedicated references precede their geometry where coverage is insufficient. Reference PASS is not model/action acceptance. Built-in imagegen only; save/open actual PNG and record exact prompt/provenance. No silent paid API fallback.
Graph project qoima-twin at this repository root. Confirm current index status/generation after compaction before structural exploration; use coverage and exact-source fallback for changed/missing ranges. No extra Obsidian snapshot/sync; daily heartbeat owns that.
'''
resume.write_text(txt,encoding='utf-8')
print(json.dumps({'updated':id,'status':status,'ready':[r['id'] for r in state['tasks'] if r['status']=='READY']},ensure_ascii=False))
