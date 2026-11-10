/* Run the unmodified Python simulation in a dedicated browser worker. */
const PYODIDE_URL='https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
let runtime,paused=false,timer;
const python=`
import json
from caitanya.engine import World
world = World(seed=browser_seed, population=5, width=64, depth=64, wildlife_per_species=2)
def browser_frame(advance=False):
    if advance and world.tick < 720:
        world.step()
    snapshot = world.public()
    snapshot['execution'] = {'running': not browser_paused and world.tick < 720,
                             'reason': 'browser_paused' if browser_paused else 'session_limit' if world.tick >= 720 else 'running'}
    # Only public event labels cross the worker boundary. Never transmit private deltas.
    labels = [{'index': index, 'world_tick': e['world_tick'], 'actor_id': e['actor_id'], 'type': e['type']}
              for index, e in enumerate(world.events[-80:], max(0, len(world.events)-80))
              if e['type'] != 'tick_committed'][-12:]
    return json.dumps({'snapshot': snapshot, 'events': labels, 'cursor': len(world.events)})
`;
function frame(advance){
  runtime.globals.set('browser_paused',paused);
  const value=runtime.runPython(`browser_frame(${advance?'True':'False'})`);
  const data=JSON.parse(value);
  self.postMessage({type:'frame',...data});
  if(data.snapshot.tick>=720)clearInterval(timer);
}
self.onmessage=async({data})=>{
  try{
    if(data.type==='start'){
      if(runtime)return;
      self.postMessage({type:'loading',message:'Loading Python engine… first visit may take a moment'});
      importScripts(PYODIDE_URL+'pyodide.js');
      runtime=await loadPyodide({indexURL:PYODIDE_URL});
      const response=await fetch('./engine.zip');
      if(!response.ok)throw Error('Could not load the world engine');
      runtime.unpackArchive(await response.arrayBuffer(),'zip');
      runtime.globals.set('browser_seed',data.seed);
      runtime.globals.set('browser_paused',false);
      await runtime.runPythonAsync(python);
      frame(false);
      timer=setInterval(()=>{try{if(!paused)frame(true);}catch(error){clearInterval(timer);self.postMessage({type:'error',message:error.message});}},1000);
    }else if(data.type==='pause'&&runtime){paused=Boolean(data.paused);frame(false);}
  }catch(error){clearInterval(timer);self.postMessage({type:'error',message:error.message});}
};
