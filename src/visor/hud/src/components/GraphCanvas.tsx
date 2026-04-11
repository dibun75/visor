import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stars, Text, Float } from '@react-three/drei';
import * as THREE from 'three';

// Mock data anticipating SQLite DB nodes
const MOCK_NODES = Array.from({ length: 40 }).map((_, i) => ({
  id: i,
  position: new THREE.Vector3(
    (Math.random() - 0.5) * 20,
    (Math.random() - 0.5) * 20,
    (Math.random() - 0.5) * 20
  ),
  type: Math.random() > 0.7 ? 'class' : 'function',
  name: `Node_${i}`,
}));

const ConnectionLines = () => {
  const points = useMemo(() => {
    const pts = [];
    for (let i = 0; i < 25; i++) {
      const source = MOCK_NODES[Math.floor(Math.random() * MOCK_NODES.length)];
      const target = MOCK_NODES[Math.floor(Math.random() * MOCK_NODES.length)];
      pts.push(source.position, target.position);
    }
    return pts;
  }, []);

  const lineGeometry = useMemo(() => {
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    return geo;
  }, [points]);

  return (
    <lineSegments geometry={lineGeometry}>
      <lineBasicMaterial color="#ffffff" opacity={0.15} transparent depthWrite={false} />
    </lineSegments>
  );
};

const NodeCloud = () => {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.05;
      groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.1;
    }
  });

  return (
    <group ref={groupRef}>
      <ConnectionLines />
      {MOCK_NODES.map((node) => (
        <Float key={node.id} speed={2} rotationIntensity={0.5} floatIntensity={1}>
          <group position={node.position}>
            <mesh>
              <sphereGeometry args={[0.3, 16, 16]} />
              <meshStandardMaterial
                color={node.type === 'class' ? '#ff0a54' : '#00f2fe'}
                emissive={node.type === 'class' ? '#ff0a54' : '#00f2fe'}
                emissiveIntensity={0.5}
                roughness={0.2}
                metalness={0.8}
              />
            </mesh>
            <Text
              position={[0, -0.6, 0]}
              fontSize={0.3}
              color="white"
              anchorX="center"
              anchorY="middle"
              outlineWidth={0.02}
              outlineColor="#000000"
            >
              {node.name}
            </Text>
          </group>
        </Float>
      ))}
    </group>
  );
};

export const GraphCanvas: React.FC = () => {
  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0 }}>
      <Canvas camera={{ position: [0, 0, 25], fov: 60 }}>
        <color attach="background" args={['#090a0f']} />
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={1.5} color="#00f2fe" />
        <pointLight position={[-10, -10, -10]} intensity={1} color="#ff0a54" />
        
        <Stars radius={50} depth={50} count={3000} factor={4} saturation={1} fade speed={1} />
        <NodeCloud />
        <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} autoRotate autoRotateSpeed={0.5} />
      </Canvas>
    </div>
  );
};
