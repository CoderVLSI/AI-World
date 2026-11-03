// Procedural, low-poly anatomy for the witness. Pure visuals: no world mutations.
export function createAnimalModel(T,a,definition){
 const root=new T.Group();root.name=a.species;root.userData.id=a.id;root.userData.animal=true;
 root.userData.legs=[];root.userData.wings=[];root.userData.tails=[];
 const colors={deer:'#b78a57',rabbit:'#c1b3a0',boar:'#705b50',wolf:'#89918c',fox:'#c77739',sparrow:'#9b7750',crow:'#28313a',duck:'#708b72',owl:'#9d8766',carp:'#b59867',butterfly:'#9c78cb',bee:'#d6b34a'};
 const fur=colors[a.species]||definition.color,black='#202622',cream='#e2d4b6';
 function part(name,geometry,color,x,y,z,sx=1,sy=1,sz=1,parent=root){const m=new T.Mesh(geometry,new T.MeshStandardMaterial({color,roughness:.9,side:T.DoubleSide}));m.name=name;m.position.set(x,y,z);m.scale.set(sx,sy,sz);parent.add(m);return m;}
 const ball=(name,color,x,y,z,sx,sy,sz,parent=root)=>part(name,new T.SphereGeometry(1,10,7),color,x,y,z,sx,sy,sz,parent);
 const cone=(name,color,x,y,z,r,h,parent=root)=>part(name,new T.ConeGeometry(r,h,6),color,x,y,z,1,1,1,parent);
 function eyes(y,z,spread=.13){for(const s of [-1,1])ball('eye',black,s*spread,y,z,.035,.04,.035);}
 function limb(name,color,x,y,z,length,radius=.055){const pivot=new T.Group();pivot.name=name;pivot.position.set(x,y,z);root.add(pivot);part(name+' bone',new T.CapsuleGeometry(radius,Math.max(.02,length-2*radius),3,6),color,0,-length/2,0,1,1,1,pivot);root.userData.legs.push(pivot);return pivot;}
 function tail(color,x,y,z,length,radius){const p=new T.Group();p.position.set(x,y,z);root.add(p);part('tail',new T.CapsuleGeometry(radius,length,3,6),color,0,0,length/2,1,1,1,p).rotation.x=Math.PI/2;root.userData.tails.push(p);return p;}
 function wing(side,color,y,z,length,width){const pivot=new T.Group();pivot.position.set(side*.16,y,z);root.add(pivot);ball('wing',color,side*length/2,0,0,length/2,.045,width/2,pivot);root.userData.wings.push({pivot,side});return pivot;}
 if(definition.group==='mammal'){
  const deer=a.species==='deer',rabbit=a.species==='rabbit',boar=a.species==='boar',fox=a.species==='fox';
  const h=deer?1.02:rabbit?.37:boar?.57:.65,length=deer?.68:rabbit?.32:boar?.55:.56;
  ball('torso',fur,0,h,.08,rabbit?.22:.28,rabbit?.24:.32,length);
  ball('chest',fur,0,h,-length*.55,.27,.34,.3);
  for(const s of [-1,1])for(const front of [true,false]){const leg=limb((front?'front':'hind')+' leg',fur,s*(rabbit?.15:.2),h-.12,front?-length*.55:length*.65,h-.15,rabbit?.045:.055);leg.userData.phase=(front?0:Math.PI)+(s>0?Math.PI:0);ball('paw',boar?'#3b302a':black,0,-(h-.15),-.035,rabbit?.065:.075,.045,rabbit?.11:.10,leg);}
  const headY=h+(deer?.55:rabbit?.25:.13),headZ=-length-(deer?.08:.08);
  if(deer)part('long neck',new T.CapsuleGeometry(.14,.45,3,7),fur,0,h+.28,-.5).rotation.x=-.35;
  ball('head',fur,0,headY,headZ,rabbit?.17:.2,rabbit?.18:.24,.27);
  ball('muzzle',boar?'#b99386':fox?cream:fur,0,headY-.07,headZ-.24,.14,.11,.2);
  ball('nose',black,0,headY-.05,headZ-.43,.075,.05,.045);
  for(const s of [-1,1]){
   const ear=(a.species==='wolf'||fox)?cone('pointed ear',fur,s*.15,headY+.27,headZ+.03,.09,.25):ball('ear',fur,s*.15,headY+(rabbit?.31:.24),headZ+.03,rabbit?.075:.085,rabbit?.27:.15,.055);ear.rotation.z=s*(rabbit?.2:.35);
   ball('eye',black,s*.16,headY+.055,headZ-.17,.035,.04,.035);
   if(deer){const antler=part('antler',new T.CylinderGeometry(.022,.035,.48,5),cream,s*.12,headY+.43,headZ,.8,1,1);antler.rotation.z=s*-.2;for(const branch of [0,1])part('antler tine',new T.CylinderGeometry(.012,.018,.20,4),cream,s*(.19+branch*.045),headY+.42+branch*.13,headZ-.035,1,1,1).rotation.z=s*-.65;}
   if(boar)cone('tusk',cream,s*.14,headY-.07,headZ-.30,.038,.18).rotation.z=-s*.4;
  }
  if(rabbit)ball('cotton tail',cream,0,h+.1,length+.08,.12,.12,.12);
  else{const p=tail(fur,0,h+.08,length*.9,fox?.65:deer?.22:.45,fox?.12:.065);if(fox)ball('tail tip',cream,0,0,.75,.11,.1,.17,p);}
 }else if(definition.group==='bird'){
  const duck=a.species==='duck',owl=a.species==='owl',crow=a.species==='crow';
  ball('body',fur,0,.38,.05,owl?.25:.19,owl?.32:.23,duck?.39:.25);
  ball('head',duck?'#386d56':fur,0,owl?.73:.64,-.2,owl?.24:.17,owl?.24:.18,.17);
  if(owl)for(const s of [-1,1]){ball('facial disk',cream,s*.105,.75,-.345,.105,.13,.025);ball('eye','#efbd4b',s*.10,.77,-.37,.06,.065,.02);ball('pupil',black,s*.10,.77,-.393,.025,.035,.01);cone('ear tuft',fur,s*.15,.99,-.19,.075,.18);}
  else eyes(.68,-.335,.105);
  if(duck)part('flat bill',new T.BoxGeometry(.16,.05,.21),'#d4ad4c',0,.59,-.39);
  else cone('beak',crow?'#34373c':'#ccac63',0,owl?.68:.61,-.39,.055,.18).rotation.x=-Math.PI/2;
  for(const s of [-1,1]){const leg=limb('bird leg','#ad9258',s*.10,.22,.02,.19,.023);ball('foot','#d3a75e',0,-.19,-.04,duck?.105:.065,.025,.09,leg);wing(s,crow?'#1d272e':fur,.42,.03,owl?.55:.47,.38);}
  const t=tail(fur,0,.3,.22,.20,.06);t.rotation.x=.25;
 }else if(definition.group==='fish'){
  ball('body',fur,0,.35,0,.20,.29,.56);ball('head','#b0a077',0,.35,-.36,.18,.24,.24);eyes(.43,-.5,.145);
  const t=tail('#b87e51',0,.35,.55,.12,.04);ball('upper tail fin','#c69a62',0,.16,.16,.035,.24,.18,t).rotation.x=.4;ball('lower tail fin','#c69a62',0,-.16,.16,.035,.24,.18,t).rotation.x=-.4;
  cone('dorsal fin','#b67e49',0,.67,.08,.12,.23).scale.z=2;
  for(const s of [-1,1])ball('pectoral fin','#c3aa79',s*.21,.25,-.1,.16,.025,.18).rotation.z=s*.3;
 }else{
  const bee=a.species==='bee';
  ball('abdomen',bee?'#d1a938':'#4c394f',0,.3,.11,.10,.11,.22);ball('thorax',bee?'#74572e':'#574057',0,.3,-.08,.09,.10,.11);ball('head',black,0,.3,-.23,.09,.09,.09);
  if(bee)for(const offset of [0,.11])part('stripe',new T.TorusGeometry(.105,.022,4,10),black,0,.3,.09+offset).scale.y=.95;
  for(const s of [-1,1]){part('antenna',new T.CylinderGeometry(.008,.008,.17,4),black,s*.055,.42,-.26).rotation.z=-s*.4;for(let j=0;j<3;j++)limb('insect leg',black,s*.08,.28,-.1+j*.1,.16,.012);
   const w=wing(s,bee?'#d6e8dc':'#b184d7',.36,0,bee?.3:.46,bee?.22:.42);if(!bee){ball('hind wing','#775fbd',s*.19,0,.24,.23,.025,.23,w);ball('wing eye','#e1be71',s*.23,.035,-.04,.07,.015,.09,w);}}
 }
 const scale=definition.group==='insect'?.8:a.species==='rabbit'?.9:1;root.scale.setScalar(scale);
 root.userData.group=definition.group;root.userData.phase=Number(a.id.replace(/\D/g,''))*.7;
 return root;
}

export function animateAnimalModel(root,time,moving){
 const phase=time*.009+root.userData.phase;
 for(const leg of root.userData.legs)leg.rotation.x=moving?Math.sin(phase+(leg.userData.phase||0))*.38:0;
 for(const {pivot,side}of root.userData.wings)pivot.rotation.z=Math.sin(phase*(root.userData.group==='insect'?2.2:.8))*side*(root.userData.group==='insect'?1.0:moving?.65:.10);
 for(const tail of root.userData.tails)tail.rotation.y=Math.sin(phase*.65)*(moving?.22:.06);
}
