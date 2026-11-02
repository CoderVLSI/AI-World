const $=id=>document.getElementById(id);

let world,selected='',replay=false,following=false,cursor=0,events=[];

let THREE,scene,camera,renderer,controls,group,sun,terrainGroup,firstView=true;

const meshes=new Map();const previousPositions=new Map();

try {

 THREE=await import('three'); const {OrbitControls}=await import('three/addons/controls/OrbitControls.js');

 scene=new THREE.Scene();scene.background=new THREE.Color('#172b2a');scene.fog=new THREE.Fog('#172b2a',120,550);

 camera=new THREE.PerspectiveCamera(48,innerWidth/innerHeight,.1,1000);camera.position.set(55,55,70);

 renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight);document.body.prepend(renderer.domElement);

 controls=new OrbitControls(camera,renderer.domElement);controls.target.set(30,0,30);controls.enableDamping=true;controls.maxPolarAngle=Math.PI*.48;

 scene.add(new THREE.HemisphereLight(0xe8f4d7,0x243a30,2.5));sun=new THREE.DirectionalLight(0xffe4ac,2);sun.position.set(25,50,20);scene.add(sun);

 group=new THREE.Group();scene.add(group);terrainGroup=new THREE.Group();scene.add(terrainGroup);

 const ray=new THREE.Raycaster(), pointer=new THREE.Vector2();

 renderer.domElement.addEventListener('click',e=>{pointer.set(e.clientX/innerWidth*2-1,-e.clientY/innerHeight*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects([...meshes.values()],true)[0];if(hit){let obj=hit.object;while(obj&&!obj.userData.id)obj=obj.parent;selected=obj?.userData.id||'';$('agents').value=selected;inspect();}});

 addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)});

 let last=0;function animate(t){requestAnimationFrame(animate);if(t-last<33)return;last=t;for(const avatar of meshes.values()){const moving=avatar.position.distanceTo(avatar.userData.target)>.025;avatar.position.lerp(avatar.userData.target,.15);for(const child of avatar.children){if(['upper arm','forearm','thigh','lower leg'].includes(child.name))child.rotation.x=moving?Math.sin(t*.008)*(child.position.x>0?1:-1)*.28:0;}}if(following&&meshes.has(selected))controls.target.lerp(meshes.get(selected).position,.15);controls.update();renderer.render(scene,camera)}requestAnimationFrame(animate);

}catch(error){$('fallback').style.display='block';$('badge').textContent='2D fallback   '+error.message;}

function mesh(geometry,color,x,y,z){const m=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:1}));m.position.set(x,y,z);group.add(m);return m;}

const colors={forest:'#526e46',grassland:'#7f8b50',highland:'#858778',wetland:'#597665',dryland:'#b3a277',water:'#4e8d99'};

let terrainIndex=new Map();

function heightAt(x,z){const size=world?.terrain?.[0]?.size||8;return terrainIndex.get(`${Math.floor(x/size)*size},${Math.floor(z/size)*size}`)?.elevation||0;}

function person(a){

 const root=new THREE.Group();root.position.set(a.x,heightAt(a.x,a.z),a.z);root.scale.setScalar((a.height_cm||170)/170);root.userData.id=a.id;root.userData.target=root.position.clone();if(previousPositions.has(a.id))root.position.copy(previousPositions.get(a.id));

 function part(name,geometry,color,x,y,z,parent=root){const m=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.9}));m.position.set(x,y,z);m.name=name;parent.add(m);return m;}

 const skin=a.skin_tone||'#bd8c68',cloth=a.id===selected?'#e5bf64':a.clothing_color||'#678b91';

 part('torso',new THREE.BoxGeometry(.46,.57,.25),cloth,0,1.15,0);

 part('pelvis',new THREE.BoxGeometry(.43,.2,.24),'#3f4b48',0,.79,0);

 part('neck',new THREE.CylinderGeometry(.07,.08,.13,6),skin,0,1.49,0);

 part('head',new THREE.SphereGeometry(.17,10,8),skin,0,1.69,0);

 part('hair',new THREE.SphereGeometry(.172,10,6,0,Math.PI*2,0,Math.PI*.48),'#3d3028',0,1.72,0);

 for(const side of [-1,1]){

  part('eye',new THREE.SphereGeometry(.023,5,4),'#272a28',side*.065,1.72,.153);

  part('ear',new THREE.SphereGeometry(.038,5,4),skin,side*.174,1.68,0);

  part('upper arm',new THREE.CapsuleGeometry(.065,.23,3,5),cloth,side*.31,1.25,0);

  part('forearm',new THREE.CapsuleGeometry(.055,.22,3,5),skin,side*.33,.94,0);

  part('hand',new THREE.BoxGeometry(.09,.12,.05),skin,side*.33,.73,0);

  for(let j=0;j<4;j++)part('finger',new THREE.BoxGeometry(.015,.06,.022),skin,side*.33+(j-1.5)*.021,.64,0);

  part('thumb',new THREE.BoxGeometry(.025,.055,.025),skin,side*.39,.73,.02);

  part('thigh',new THREE.CapsuleGeometry(.095,.23,3,5),'#435352',side*.125,.59,0);

  part('lower leg',new THREE.CapsuleGeometry(.075,.22,3,5),'#435352',side*.125,.26,0);

  part('foot',new THREE.BoxGeometry(.16,.12,.30),'#403a31',side*.125,.065,.07);

 }

 part('nose',new THREE.ConeGeometry(.034,.08,5),skin,0,1.68,.18).rotation.x=Math.PI/2;

 part('mouth',new THREE.BoxGeometry(.065,.012,.015),'#805248',0,1.61,.154);

 group.add(root);return root;

}

function drawTerrain(s){

 terrainGroup.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});terrainGroup.clear();

 terrainIndex=new Map((s.terrain||[]).map(t=>[`${t.x},${t.z}`,t]));

 const tiles=s.terrain||[{x:0,z:0,size:s.width,elevation:0,biome:'grassland'}];

 const tileMesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({roughness:1}),tiles.length);

 const dummy=new THREE.Object3D();tiles.forEach((t,i)=>{dummy.position.set(t.x+t.size/2,t.elevation-.65,t.z+t.size/2);dummy.scale.set(t.size,1.3,t.size);dummy.updateMatrix();tileMesh.setMatrixAt(i,dummy.matrix);tileMesh.setColorAt(i,new THREE.Color(colors[t.biome]));});terrainGroup.add(tileMesh);

}

function render(s){

 world=s;

 if(renderer){

  group.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});for(const [id,m] of meshes)previousPositions.set(id,m.position.clone());group.clear();meshes.clear();

  if(firstView){drawTerrain(s);const first=Object.values(s.agents)[0];controls.target.set(first.x,0,first.z);camera.position.set(first.x+18,22,first.z+24);firstView=false;}

  const nodes=Object.values(s.resources).filter(n=>n.amount>0);

  const inst=new THREE.InstancedMesh(new THREE.ConeGeometry(.45,1.2,6),new THREE.MeshStandardMaterial({roughness:1}),nodes.length);group.add(inst);const dummy=new THREE.Object3D();

  const resourceColors={food:'#cbba69',fruit:'#c46f58',grain:'#dbc986',water:'#74bfd1',wood:'#325a3b',stone:'#959a91',clay:'#b77c60',sand:'#c9bb84',iron_ore:'#8b6554',copper_ore:'#719a86',coal:'#434340',salt:'#e7ddd0',herbs:'#76ad70',plant_fiber:'#a4b86d',fish:'#89acbd'};

  nodes.forEach((n,i)=>{const tree=n.kind==='wood';dummy.position.set(n.x,heightAt(n.x,n.z)+(tree?1.6:.45),n.z);dummy.scale.set(tree?2:.65,tree?3:.65,tree?2:.65);dummy.updateMatrix();inst.setMatrixAt(i,dummy.matrix);inst.setColorAt(i,new THREE.Color(resourceColors[n.kind]||'#aaa'));});

  for(const a of Object.values(s.agents)){if(a.alive)meshes.set(a.id,person(a));}

  const hour=s.climate?.hour||12;sun.intensity=Math.max(.35,Math.sin((hour-6)/12*Math.PI)*2);sun.position.set(s.width/2,60,s.depth/2);

  for(const p of Object.values(s.parts))mesh(new THREE.BoxGeometry(.8,p.shape==='rod'?2:.6,.8),p.material==='wood'?'#9d7549':'#a2a89c',p.x,heightAt(p.x,p.z)+.5,p.z);

  for(const w of Object.values(s.works))mesh(new THREE.BoxGeometry(.5,.15,.7),'#f2dfac',w.x,heightAt(w.x,w.z)+.2,w.z);

 }else{const c=$('fallback');c.width=innerWidth;c.height=innerHeight;const ctx=c.getContext('2d'),scale=Math.min(innerWidth/s.width,innerHeight/s.depth);ctx.fillStyle='#142922';ctx.fillRect(0,0,c.width,c.height);for(const n of Object.values(s.resources)){ctx.fillStyle=n.kind==='food'?'#b7bd64':'#4c7850';if(n.amount)ctx.fillRect(n.x*scale,n.z*scale,3,3)}for(const a of Object.values(s.agents)){ctx.fillStyle='#f2d29c';ctx.fillRect(a.x*scale,a.z*scale,5,5)}}

 $('generations').textContent=`Day ${Math.floor(s.tick*(s.biology?.days_per_tick||1/144))} | ${s.metrics?.births??Object.values(s.agents).filter(a=>a.generation>0).length} births | ${s.pregnancies?.length||0} pregnancies | generation ${Math.max(...Object.values(s.agents).map(a=>a.generation||0))}${(s.biology?.days_per_tick||0)>1/144?' | ACCELERATED CALENDAR':''}`;
 $('backend').textContent=s.manifest.inference_backend==='MockInferenceBackend'?'DETERMINISTIC MOCK   no language model running':`SHARED MODEL   ${s.manifest.model_id}`;

 $('ecology').textContent=`${s.width}   ${s.depth} terrain   ${s.climate?.season||''}   ${s.climate?.weather||''}   ${s.climate?.temperature_c??''} C   ${Object.keys(s.resource_catalog||{}).length||15} resource types`;

 $('badge').textContent=`${replay?'REPLAY':'LIVE'}   tick ${s.tick}   ${Object.values(s.agents).filter(a=>a.alive).length} inhabitants   ${s.status}`;

 if(!replay)$('tick').max=s.tick;

 const current=$('agents').value;$('agents').replaceChildren(new Option('Choose an inhabitant',''),...Object.values(s.agents).map(a=>new Option(`${a.id} / ${a.life_stage||'adult'} / G${a.generation||0}`,a.id)));$('agents').value=current;

 inspect();

}

function inspect(){const a=world?.agents[selected];$('anatomy').textContent=a?Object.entries(a.body?.parts||{}).map(([name,value])=>`${name.replaceAll('_',' ')}: ${value.health}`).join('\n'):'Select an inhabitant.';$('detail').textContent=a?`${a.id}\n${a.gender||"unspecified"}   sex: ${a.biological_sex||"unspecified"}\nAge ${(a.age_years??a.age_years_at_start??25).toFixed(2)}   Height ${a.height_cm||170} cm\nStage ${a.life_stage||"adult"} / Generation ${a.generation||0}\nParents ${(a.parent_ids||[]).join(", ")||"founder"}\nPosition ${a.x}, ${a.z}\nThirst ${a.thirst||0}\nBody: ${Object.keys(a.body?.parts||{}).length} parts tracked\nEnergy ${a.energy} / Hunger ${a.hunger}\nHealth ${a.health}\nInventory ${JSON.stringify(a.inventory)}\nSkills ${JSON.stringify(a.skills||{})}\nLearned records ${a.knowledge?.length||0}\nAlive ${a.alive}`:'Select an inhabitant.';}

$('agents').onchange=e=>{selected=e.target.value;inspect()};$('follow').onclick=()=>{following=!following;if(following&&meshes.has(selected)){const p=meshes.get(selected).position;controls.target.copy(p);camera.position.copy(p).add(new THREE.Vector3(5,3,6));}$('follow').textContent=following?'Stop following':'Follow selected'};

$('replay').onclick=async()=>{try{const n=Number($('tick').value);const r=await fetch(`/api/v1/history?from_tick=${n}&to_tick=${n}`);if(!r.ok)throw Error('Tick unavailable');replay=true;render(await r.json());$('events').textContent='Historical snapshot selected. Return to live for the live event feed.';$('mode').textContent='HISTORICAL   live simulation continues';}catch(e){$('mode').textContent=e.message}};

$('live').onclick=()=>{replay=false;$('mode').textContent='LIVE';poll()};

async function poll(){try{if(!replay){const r=await fetch('/api/v1/world/snapshot');if(!r.ok)throw Error('Snapshot unavailable');render(await r.json());let er=await fetch(`/api/v1/world/events?after=${Number.isInteger(cursor)?cursor:0}`);if(er.status===400){cursor=0;events=[];er=await fetch('/api/v1/world/events?after=0')}if(!er.ok)throw Error('Event feed unavailable');const e=await er.json();cursor=e.cursor;events.push(...e.events.filter(e=>e.type!=='tick_committed'));events=events.slice(-12);$('events').textContent=events.map(e=>`t${e.world_tick}   ${e.actor_id||'world'}   ${e.type}`).join('\n')}}catch(e){$('badge').textContent='DISCONNECTED   '+e.message}}

await poll();setInterval(poll,1500);

