const THREE = require('three');
try {
  const geom = new THREE.BufferGeometry().setFromPoints([]);
  console.log('Geom positions:', geom.attributes.position);
} catch (e) {
  console.log('Error:', e);
}
