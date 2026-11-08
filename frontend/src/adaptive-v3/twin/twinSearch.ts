/**
 * Search over the warehouse snapshot: workers, cargo (HU and SKU), zones, ports and storage slots.
 * Pure: the page builds the entries from the loaded bundle and decides where to fly. Matching ignores case,
 * spaces, ':' '_' '-' and the 'v3:' prefixes, so «pk 03», «demo001» or «small_e 019» all find what you expect.
 */
export type SearchKind='actor'|'HU'|'zone'|'port'|'slot';
export type SearchEntry={kind:SearchKind;id:string;title:string;sub:string;keys:string[]};
export type SearchHit=SearchEntry&{score:number};

export const KIND_RU:Record<SearchKind,string>={actor:'Работники',HU:'Грузы',zone:'Участки',port:'Ворота',slot:'Ячейки'};
const KIND_ORDER:SearchKind[]=['actor','HU','port','zone','slot'];

export const norm=(s:string)=>s.toLowerCase().replace(/ё/g,'е').replace(/\bv3:(hu|slot|module|service):/g,'').replace(/[\s:_\-.·]+/g,'');
/** Short, human form of internal IDs for display. */
export const shortId=(id:string)=>id.replace(/^v3:(HU:initial|slot|module|service):/,'');

export function buildIndex(entries:SearchEntry[]){return entries.map(e=>({e,keys:e.keys.map(norm).filter(Boolean)}));}
export type SearchIndex=ReturnType<typeof buildIndex>;

/** Every query word must match some key; a whole-key match beats a prefix, a prefix beats a substring. */
export function search(index:SearchIndex,query:string,perKind=5):SearchHit[]{
 const words=query.split(/\s+/).map(norm).filter(Boolean);if(!words.length)return [];
 const hits:SearchHit[]=[];
 for(const {e,keys} of index){
  let score=0;
  for(const w of words){
   let best=0;for(const k of keys)best=Math.max(best,k===w?100:k.startsWith(w)?60:k.includes(w)?25:0);
   if(!best){score=0;break;}score+=best;
  }
  if(score)hits.push({...e,score});
 }
 const grouped=new Map<SearchKind,SearchHit[]>();
 for(const h of hits.sort((a,b)=>b.score-a.score||a.title.localeCompare(b.title,'ru',{numeric:true})))grouped.set(h.kind,[...(grouped.get(h.kind)??[]),h]);
 // Kinds with the strongest hit come first; inside a kind the best few.
 return [...grouped.entries()].sort((a,b)=>b[1][0].score-a[1][0].score||KIND_ORDER.indexOf(a[0])-KIND_ORDER.indexOf(b[0])).flatMap(([,list])=>list.slice(0,perKind));
}
