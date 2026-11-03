export function groupFor(type){
  if(['birth','death','adulthood_reached','pregnancy_lost','arrival','reproduce'].includes(type))return 'life';
  if(['speak','write','read','revise','teach'].includes(type))return 'culture';
  if(['place'].includes(type))return 'building';
  if(['move','gather','eat','drink','rest','care','give','wait'].includes(type))return 'survival';
  return 'other';
}
export function publicText(event){
  if(event.type==='reflect')return 'Private reflection recorded. Contents are not displayed.';
  const p=event.payload?.parameters||{};
  return ['speak','write','revise','teach'].includes(event.type)&&typeof p.text==='string'?p.text:'';
}
export function filterEvents(events,{group='all',actor='',query=''}={}){
  const q=query.trim().toLowerCase();
  return events.filter(e=>e.type!=='tick_committed'&&(group==='all'||groupFor(e.type)===group)&&(!actor||e.actor_id===actor)&&(!q||[e.event_id,e.type,e.actor_id,publicText(e)].join(' ').toLowerCase().includes(q))).sort((a,b)=>b.world_tick-a.world_tick||b.event_id.localeCompare(a.event_id));
}
export function relatives(agents,id){
  const person=agents[id];if(!person)return {parents:[],children:[],guardians:[]};
  return {parents:[...(person.parent_ids||[])],guardians:[...(person.guardian_ids||[])],children:Object.values(agents).filter(a=>(a.parent_ids||[]).includes(id)).map(a=>a.id)};
}
export function mergeEvents(previous,incoming){
  const map=new Map(previous.map(e=>[e.event_id,e]));for(const e of incoming)if(e.type!=='tick_committed')map.set(e.event_id,e);return [...map.values()];
}
export function generationGroups(agents,query=''){
  const groups=new Map();for(const a of Object.values(agents).sort((a,b)=>a.id.localeCompare(b.id))){if(!a.id.toLowerCase().includes(query.toLowerCase()))continue;const g=Number.isInteger(a.generation)?a.generation:0;if(!groups.has(g))groups.set(g,[]);groups.get(g).push(a);}return [...groups.entries()].sort((a,b)=>a[0]-b[0]);
}
