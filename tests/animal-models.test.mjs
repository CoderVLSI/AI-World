import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../web/vendor/three.module.js';
import {createAnimalModel,animateAnimalModel} from '../web/animal-models.mjs';
const groups={deer:'mammal',rabbit:'mammal',boar:'mammal',wolf:'mammal',fox:'mammal',sparrow:'bird',crow:'bird',duck:'bird',owl:'bird',carp:'fish',butterfly:'insect',bee:'insect'};
test('all twelve species have finite real 3D mesh geometry without changing animal data',()=>{
 for(const[species,group]of Object.entries(groups)){
  const a={id:'animal-000012',species,x:3,z:4};const before=JSON.stringify(a);
  const model=createAnimalModel(THREE,a,{group,color:'#aaa'});let meshes=0,sprites=0;
  model.traverse(part=>{if(part.isSprite)sprites++;if(part.isMesh){meshes++;for(const value of part.geometry.attributes.position.array)assert.ok(Number.isFinite(value));}});
  assert.equal(sprites,0);assert.ok(meshes>=8,species);assert.equal(JSON.stringify(a),before);
  for(const leg of model.userData.legs)assert.ok(leg.children.some(child=>child.name.endsWith(' bone')),'Leg geometry must follow its joint');
  for(const tail of model.userData.tails)assert.ok(tail.getObjectByName('tail'),'Tail geometry must follow its joint');
  const bounds=new THREE.Box3().setFromObject(model);assert.ok(bounds.max.y>bounds.min.y);
  animateAnimalModel(model,1000,true);
  model.traverse(part=>assert.ok([part.rotation.x,part.rotation.y,part.rotation.z].every(Number.isFinite)));
 }
});
test('species anatomy and animation distinguish limbs, wings and fins',()=>{
 const deer=createAnimalModel(THREE,{id:'animal-1',species:'deer'},{group:'mammal'});
 assert.ok(deer.getObjectByName('antler'));assert.equal(deer.userData.legs.length,4);
 const duck=createAnimalModel(THREE,{id:'animal-2',species:'duck'},{group:'bird'});
 assert.ok(duck.getObjectByName('flat bill'));assert.equal(duck.userData.wings.length,2);
 const fish=createAnimalModel(THREE,{id:'animal-3',species:'carp'},{group:'fish'});
 assert.ok(fish.getObjectByName('dorsal fin'));assert.ok(fish.getObjectByName('pectoral fin'));
 animateAnimalModel(deer,1000,true);assert.ok(deer.userData.legs.some(leg=>leg.rotation.x!==0));
 animateAnimalModel(deer,1000,false);assert.ok(deer.userData.legs.every(leg=>leg.rotation.x===0));
});
