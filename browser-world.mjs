/* Adapt the viewer's read-only requests to public frames from a local worker. */
const worker=new Worker(new URL('./browser-world-worker.js',import.meta.url));
let current,resolveReady,rejectReady;
const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
const status=document.getElementById('badge');
const realFetch=globalThis.fetch.bind(globalThis);
worker.onmessage=({data})=>{
  if(data.type==='loading')status.textContent=data.message;
  if(data.type==='error'){status.textContent='World stopped: '+data.message;rejectReady(Error(data.message));}
  if(data.type==='frame'){current=data;resolveReady();}
};
worker.onerror=()=>{status.textContent='World engine could not start. Try reloading.';rejectReady(Error('Worker failed'));};
const seedParam=Number(new URLSearchParams(location.search).get('seed')||314159);
worker.postMessage({type:'start',seed:Number.isSafeInteger(seedParam)?seedParam:314159});
globalThis.fetch=async(input,options)=>{
  const url=new URL(typeof input==='string'?input:input.url,location.href);
  if(url.origin===location.origin&&url.pathname.startsWith('/api/v1/')){
    await ready;
    if(url.pathname==='/api/v1/world/snapshot')return Response.json(current.snapshot);
    if(url.pathname==='/api/v1/world/events')return Response.json({cursor:current.cursor,events:current.events.filter(event=>event.index>=Number(url.searchParams.get('after')||0))});
    return Response.json({detail:'Historical replay is unavailable in the browser world'},{status:400});
  }
  return realFetch(input,options);
};
document.getElementById('pause-world').onclick=event=>{
  const paused=event.currentTarget.dataset.paused!=='true';
  event.currentTarget.dataset.paused=String(paused);
  event.currentTarget.textContent=paused?'Resume world':'Pause world';
  worker.postMessage({type:'pause',paused});
};
document.getElementById('new-world').onclick=()=>{
  const url=new URL(location.href);url.searchParams.set('seed',String(crypto.getRandomValues(new Uint32Array(1))[0]));location.href=url.href;
};
await ready;
await import('./viewer.js');
