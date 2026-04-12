import { useRef, useMemo, useState, useEffect, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stars, Float, Html } from '@react-three/drei';
import * as THREE from 'three';

// ────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────

interface GraphNode {
  id: number;
  file_path: string;
  name: string;
  node_count: number;
  classes: number;
  functions: number;
  top_entities: { name: string; type: string }[];
  cluster: string;
  recently_modified: boolean;
}

interface GraphEdge {
  source: number;
  target: number;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ────────────────────────────────────────────────────
// Color palette for directory clusters
// ────────────────────────────────────────────────────

const CLUSTER_COLORS = [
  '#00f2fe', // cyan
  '#ff0a54', // rose
  '#4facfe', // sky blue
  '#f77f00', // orange
  '#7209b7', // purple
  '#06d6a0', // emerald
  '#e63946', // red
  '#fca311', // gold
  '#3a86ff', // blue
  '#8338ec', // violet
  '#ff006e', // magenta
  '#fb5607', // flame
];

function getClusterColor(cluster: string, clusterIndex: Map<string, number>): string {
  if (!clusterIndex.has(cluster)) {
    clusterIndex.set(cluster, clusterIndex.size);
  }
  return CLUSTER_COLORS[clusterIndex.get(cluster)! % CLUSTER_COLORS.length];
}

// ────────────────────────────────────────────────────
// Position nodes in a 3D layout using cluster grouping
// ────────────────────────────────────────────────────

function computePositions(nodes: GraphNode[], clusterIndex: Map<string, number>): Map<number, THREE.Vector3> {
  const positions = new Map<number, THREE.Vector3>();
  const clusterCenters = new Map<string, THREE.Vector3>();

  // Create cluster centers on a sphere
  const clusters = Array.from(new Set(nodes.map(n => n.cluster)));
  clusters.forEach((c, i) => {
    const phi = Math.acos(-1 + (2 * i) / Math.max(clusters.length, 1));
    const theta = Math.sqrt(clusters.length * Math.PI) * phi;
    const r = 12;
    clusterCenters.set(c, new THREE.Vector3(
      r * Math.cos(theta) * Math.sin(phi),
      r * Math.sin(theta) * Math.sin(phi),
      r * Math.cos(phi)
    ));
    if (!clusterIndex.has(c)) clusterIndex.set(c, clusterIndex.size);
  });

  // Place nodes around their cluster center
  const clusterCounters = new Map<string, number>();
  nodes.forEach((node) => {
    const center = clusterCenters.get(node.cluster) || new THREE.Vector3();
    const idx = clusterCounters.get(node.cluster) || 0;
    clusterCounters.set(node.cluster, idx + 1);

    const angle = idx * 2.4; // golden angle for even distribution
    const radius = 1.5 + idx * 0.3;
    const offset = new THREE.Vector3(
      Math.cos(angle) * radius,
      Math.sin(angle) * radius,
      (Math.random() - 0.5) * 2
    );

    positions.set(node.id, center.clone().add(offset));
  });

  return positions;
}

// ────────────────────────────────────────────────────
// Connection lines between nodes
// ────────────────────────────────────────────────────

const ConnectionLines: React.FC<{
  edges: GraphEdge[];
  positions: Map<number, THREE.Vector3>;
}> = ({ edges, positions }) => {
  const lineGeometry = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    edges.forEach(e => {
      const s = positions.get(e.source);
      const t = positions.get(e.target);
      if (s && t) {
        pts.push(s, t);
      }
    });
    if (pts.length === 0) return null;
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [edges, positions]);

  if (!lineGeometry) return null;

  return (
    <lineSegments geometry={lineGeometry}>
      <lineBasicMaterial color="#ffffff" opacity={0.4} transparent depthWrite={false} />
    </lineSegments>
  );
};

// ────────────────────────────────────────────────────
// Drift pulse ring (animated glow on recently modified files)
// ────────────────────────────────────────────────────

const DriftPulse: React.FC = () => {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (ref.current) {
      const s = 1 + Math.sin(clock.elapsedTime * 3) * 0.3;
      ref.current.scale.set(s, s, s);
      (ref.current.material as THREE.MeshBasicMaterial).opacity = 0.3 + Math.sin(clock.elapsedTime * 3) * 0.2;
    }
  });
  return (
    <mesh ref={ref}>
      <ringGeometry args={[0.6, 0.8, 32]} />
      <meshBasicMaterial color="#ff0a54" transparent opacity={0.5} side={THREE.DoubleSide} />
    </mesh>
  );
};

// ────────────────────────────────────────────────────
// Single graph node sphere
// ────────────────────────────────────────────────────

const GraphNodeMesh: React.FC<{
  node: GraphNode;
  position: THREE.Vector3;
  color: string;
  onHover: (node: GraphNode | null) => void;
}> = ({ node, position, color, onHover }) => {
  const meshRef = useRef<THREE.Mesh>(null);

  // God-node sizing: radius proportional to node count, clamped
  const radius = Math.max(0.15, Math.min(0.8, 0.1 + node.node_count * 0.015));

  return (
    <Float speed={1.5} rotationIntensity={0.2} floatIntensity={0.5}>
      <group position={position}>
        <mesh
          ref={meshRef}
          onPointerEnter={(e) => { e.stopPropagation(); onHover(node); }}
          onPointerLeave={() => onHover(null)}
        >
          <sphereGeometry args={[radius, 16, 16]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={node.recently_modified ? 0.8 : 0.4}
            roughness={0.2}
            metalness={0.8}
          />
        </mesh>
        {node.recently_modified && <DriftPulse />}
      </group>
    </Float>
  );
};

// ────────────────────────────────────────────────────
// Tooltip overlay (glassmorphism HTML panel)
// ────────────────────────────────────────────────────

const Tooltip: React.FC<{ node: GraphNode; position: THREE.Vector3 }> = ({ node, position }) => {
  return (
    <Html
      position={[position.x, position.y + 1.2, position.z]}
      center
      style={{ pointerEvents: 'none' }}
    >
      <div style={{
        background: 'rgba(10, 12, 20, 0.85)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(0, 242, 254, 0.2)',
        borderRadius: '10px',
        padding: '12px 16px',
        minWidth: '220px',
        maxWidth: '280px',
        color: '#e0e6ed',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        fontSize: '11px',
        lineHeight: '1.5',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 16px rgba(0, 242, 254, 0.1)',
      }}>
        {/* File name */}
        <div style={{
          fontSize: '13px',
          fontWeight: 700,
          color: '#fff',
          marginBottom: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          <span>📁</span>
          <span style={{ wordBreak: 'break-all' }}>{node.file_path.replace('./', '')}</span>
        </div>

        {/* Counts */}
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.1)',
          paddingTop: '6px',
          marginBottom: '6px',
          display: 'flex',
          gap: '12px',
        }}>
          <span><span style={{ color: '#ff0a54' }}>●</span> {node.classes} classes</span>
          <span><span style={{ color: '#00f2fe' }}>●</span> {node.functions} functions</span>
        </div>

        {/* Top entities */}
        {node.top_entities.length > 0 && (
          <div style={{
            borderTop: '1px solid rgba(255,255,255,0.1)',
            paddingTop: '6px',
          }}>
            <div style={{ color: '#8892a4', fontSize: '10px', letterSpacing: '1px', marginBottom: '4px' }}>
              TOP ENTITIES
            </div>
            {node.top_entities.map((e, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <span style={{
                  fontSize: '9px',
                  padding: '1px 5px',
                  borderRadius: '3px',
                  background: e.type === 'class' ? 'rgba(255, 10, 84, 0.2)' : 'rgba(0, 242, 254, 0.2)',
                  color: e.type === 'class' ? '#ff0a54' : '#00f2fe',
                  fontWeight: 600,
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}>{e.type}</span>
                <span>{e.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Drift indicator */}
        {node.recently_modified && (
          <div style={{
            borderTop: '1px solid rgba(255,255,255,0.1)',
            paddingTop: '6px',
            marginTop: '4px',
            color: '#ff0a54',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}>
            <span style={{ fontSize: '14px' }}>🔴</span> RECENTLY MODIFIED
          </div>
        )}
      </div>
    </Html>
  );
};

// ────────────────────────────────────────────────────
// Node cloud (all nodes + edges + tooltip)
// ────────────────────────────────────────────────────

const NodeCloud: React.FC<{ graphData: GraphData }> = ({ graphData }) => {
  const groupRef = useRef<THREE.Group>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  const clusterIndex = useMemo(() => new Map<string, number>(), []);
  const positions = useMemo(
    () => computePositions(graphData.nodes, clusterIndex),
    [graphData.nodes]
  );

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.03;
    }
  });

  const handleHover = useCallback((node: GraphNode | null) => {
    setHoveredNode(node);
  }, []);

  return (
    <group ref={groupRef}>
      <ConnectionLines edges={graphData.edges} positions={positions} />
      {graphData.nodes.map((node) => {
        const pos = positions.get(node.id);
        if (!pos) return null;
        const color = getClusterColor(node.cluster, clusterIndex);
        return (
          <GraphNodeMesh
            key={node.id}
            node={node}
            position={pos}
            color={color}
            onHover={handleHover}
          />
        );
      })}
      {hoveredNode && positions.get(hoveredNode.id) && (
        <Tooltip node={hoveredNode} position={positions.get(hoveredNode.id)!} />
      )}
    </group>
  );
};

// ────────────────────────────────────────────────────
// Fallback static cloud (shown while data is loading)
// ────────────────────────────────────────────────────

const LoadingCloud: React.FC = () => {
  const groupRef = useRef<THREE.Group>(null);
  const dots = useMemo(() =>
    Array.from({ length: 20 }).map((_, i) => ({
      id: i,
      position: new THREE.Vector3(
        (Math.random() - 0.5) * 16,
        (Math.random() - 0.5) * 16,
        (Math.random() - 0.5) * 16
      ),
    })),
  []);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.05;
    }
  });

  return (
    <group ref={groupRef}>
      {dots.map(d => (
        <Float key={d.id} speed={2} floatIntensity={1}>
          <mesh position={d.position}>
            <sphereGeometry args={[0.15, 8, 8]} />
            <meshStandardMaterial color="#1a2030" emissive="#1a2030" emissiveIntensity={0.3} />
          </mesh>
        </Float>
      ))}
    </group>
  );
};

// ────────────────────────────────────────────────────
// Main GraphCanvas component
// ────────────────────────────────────────────────────

const getVsCode = () => {
  if (!(window as any).vscodeApiInstance && (window as any).acquireVsCodeApi) {
    (window as any).vscodeApiInstance = (window as any).acquireVsCodeApi();
  }
  return (window as any).vscodeApiInstance || null;
};

export const GraphCanvas: React.FC = () => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const vscode = getVsCode();

  useEffect(() => {
    const messageHandler = (event: MessageEvent) => {
      if (event.data.command === 'graphData') {
        try {
          setGraphData(event.data.data);
        } catch (err: any) {
          console.error('[Err] graphData failed:', err.message);
        }
      }
    };

    window.addEventListener('message', messageHandler);

    // Fetch graph data immediately and then every 10 seconds
    const fetchGraph = () => {
      if (vscode) {
        vscode.postMessage({ command: 'fetchGraphData' });
      }
    };

    fetchGraph();
    const interval = setInterval(fetchGraph, 10000);

    return () => {
      clearInterval(interval);
      window.removeEventListener('message', messageHandler);
    };
  }, []);

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 0 }}>
      <Canvas camera={{ position: [0, 0, 28], fov: 60 }}>
        <color attach="background" args={['#090a0f']} />
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={1.5} color="#00f2fe" />
        <pointLight position={[-10, -10, -10]} intensity={1} color="#ff0a54" />
        <Stars radius={50} depth={50} count={3000} factor={4} saturation={1} fade speed={1} />
        {graphData && graphData.nodes && graphData.nodes.length > 0 ? (
          <NodeCloud graphData={graphData} />
        ) : (
          <LoadingCloud />
        )}
        <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} autoRotate autoRotateSpeed={0.3} />
      </Canvas>
    </div>
  );
};

