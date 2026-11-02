import test from 'node:test';
import assert from 'node:assert/strict';
import {relatives,filterEvents,mergeEvents,publicText,generationGroups} from '../web/chronicle-core.mjs';
test('lineage preserves biological connections and distinct caregivers',()=>{
 const agents={a:{id:'a'},b:{id:'b'},c:{id:'c',parent_ids:['a','missing'],guardian_ids:['b'],generation:1}};
 assert.deepEqual(relatives(agents,'c'),{parents:['a','missing'],children:[],guardians:['b']});
 assert.deepEqual(relatives(agents,'a').children,['c']);
 assert.deepEqual(generationGroups(agents).map(([g,a])=>[g,a.length]),[[0,2],[1,1]]);
 assert.deepEqual(generationGroups(agents,'C').map(([g,a])=>a[0].id),['c']);
});
test('timeline filters actual public events; never searches private reflection or summaries',()=>{
 const events=[{event_id:'evt-1',world_tick:1,type:'birth',actor_id:'c'},
 {event_id:'evt-2',world_tick:2,type:'speak',actor_id:'a',payload:{parameters:{text:'hello'}}},
 {event_id:'evt-3',world_tick:3,type:'reflect',actor_id:'a',payload:{parameters:{text:'private secret'},reason_summary:'hidden'}},
 {event_id:'evt-4',world_tick:4,type:'tick_committed'}];
 assert.equal(filterEvents(events).length,3);
 assert.equal(filterEvents(events,{group:'life'})[0].type,'birth');
 assert.equal(filterEvents(events,{query:'HELLO',actor:'a'}).length,1);
 assert.equal(filterEvents(events,{query:'private secret'}).length,0);
 assert.equal(publicText(events[2]),'Private reflection recorded. Contents are not displayed.');
 assert.equal(publicText({type:'speak',payload:{parameters:{text:'<img src=x onerror=alert(1)>'}}}),'<img src=x onerror=alert(1)>');
});
test('pagination merges duplicate event IDs and omits private committed patches',()=>{
 const e={event_id:'evt-1',type:'birth'};
 assert.equal(mergeEvents([e],[e,{event_id:'evt-2',type:'tick_committed',payload:{root:'private'}}]).length,1);
});
