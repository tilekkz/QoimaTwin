import {WAREHOUSE_BASE_FILES,type WarehouseTexts} from './warehouseAdapter';
import type {HeavyInboundFixture} from './warehouseHeavyInboundPlan';

// Exact reviewed UTF-8 fixture bytes; update only with a new affected-scope receipt.
export const HEAVY_INBOUND_FIXTURE_SHA256='7e5b49f04b5b3a59f2ac23f62f2d57e9381a5cbacb98ae9ba00254a00ffc70da';
const sha256=async(value:string)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))].map(n=>n.toString(16).padStart(2,'0')).join('');

/** Bind the episode to the exact same source texts used by the warehouse adapter. */
export async function verifyWarehouseHeavyInboundSources(texts:WarehouseTexts,fixtureText:string):Promise<HeavyInboundFixture>{
 if(await sha256(fixtureText)!==HEAVY_INBOUND_FIXTURE_SHA256)throw Error('INBOUND_FIXTURE_HASH_MISMATCH');
 const fixture=JSON.parse(fixtureText) as HeavyInboundFixture;
 await Promise.all((Object.keys(WAREHOUSE_BASE_FILES) as (keyof WarehouseTexts)[]).map(async key=>{
  const path='frontend/public'+WAREHOUSE_BASE_FILES[key];
  if(await sha256(texts[key])!==fixture.source_hashes[path])throw Error('INBOUND_SOURCE_HASH_MISMATCH:'+path);
 }));
 return fixture;
}
