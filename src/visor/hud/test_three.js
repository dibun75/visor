const THREE = require('three');
try {
  let g = new THREE.BufferGeometry().setFromPoints([]);
  console.log("Success with empty Array!");
} catch(e) {
  console.log("Empty Array Exception:", e);
}
