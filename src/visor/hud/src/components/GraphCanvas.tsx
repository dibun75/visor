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

interface ContextNode {
  id: number;
  file_path: string;
  name: string;
  node_type: string;
  start_line: number;
  end_line: number;
  code_snippet?: string;
  relevance_score: number;
}

interface ContextResult {
  context: ContextNode[];
  debug: {
    intent: string;
    skill: string | null;
    scores: Record<string, Record<string, number>>;
    reasoning: Record<string, string[]>;
  };
  metrics: {
    estimated_tokens_without: number;
    estimated_tokens_with: number;
    reduction_percent: number;
  };
  query: string;
  total_tokens: number;
  truncated: boolean;
  recommended_next?: string[];
}

type GraphViewMode = 'full' | 'context' | 'dependency';

// ────────────────────────────────────────────────────
// Color palette for directory clusters
// ────────────────────────────────────────────────────

const CLUSTER_COLORS = [
  '#00f2fe', '#ff0a54', '#4facfe', '#f77f00', '#7209b7',
  '#06d6a0', '#e63946', '#fca311', '#3a86ff', '#8338ec',
  '#ff006e', '#fb5607',
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

  const clusterCounters = new Map<string, number>();
  nodes.forEach((node) => {
    const center = clusterCenters.get(node.cluster) || new THREE.Vector3();
    const idx = clusterCounters.get(node.cluster) || 0;
    clusterCounters.set(node.cluster, idx + 1);

    const angle = idx * 2.4;
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
// Edge rendering with intelligence highlighting
// ────────────────────────────────────────────────────

const EDGE_STYLE: Record<string, { color: string; opacity: number }> = {
  IMPORTS: { color: '#00f2fe', opacity: 0.5 },
  CALLS:   { color: '#f77f00', opacity: 0.35 },
  DEFAULT: { color: '#ffffff', opacity: 0.2 },
};

const EdgeLines: React.FC<{
  edges: GraphEdge[];
  positions: Map<number, THREE.Vector3>;
  selectedNodeIds: Set<number>;
  hasContext: boolean;
}> = ({ edges, positions, selectedNodeIds, hasContext }) => {
  const byType = useMemo(() => {
    const groups: Record<string, { pts: THREE.Vector3[]; selected: boolean }[]> = {};
    edges.forEach(e => {
      const s = positions.get(e.source);
      const t = positions.get(e.target);
      if (!s || !t) return;
      const key = e.type in EDGE_STYLE ? e.type : 'DEFAULT';
      if (!groups[key]) groups[key] = [];
      const isSelected = hasContext && selectedNodeIds.has(e.source) && selectedNodeIds.has(e.target);
      groups[key].push({ pts: [s, t], selected: isSelected });
    });

    // Separate selected and unselected edges per type
    return Object.entries(groups).flatMap(([type, items]) => {
      const style = EDGE_STYLE[type] ?? EDGE_STYLE.DEFAULT;
      const selectedPts = items.filter(i => i.selected).flatMap(i => i.pts);
      const normalPts = items.filter(i => !i.selected).flatMap(i => i.pts);
      const result = [];
      if (normalPts.length > 0) {
        result.push({
          key: `${type}-normal`,
          geometry: new THREE.BufferGeometry().setFromPoints(normalPts),
          color: style.color,
          opacity: hasContext ? 0.04 : style.opacity,
        });
      }
      if (selectedPts.length > 0) {
        result.push({
          key: `${type}-selected`,
          geometry: new THREE.BufferGeometry().setFromPoints(selectedPts),
          color: '#00f2fe',
          opacity: 0.9,
        });
      }
      return result;
    });
  }, [edges, positions, selectedNodeIds, hasContext]);

  return (
    <>
      {byType.map(({ key, geometry, color, opacity }) => (
        <lineSegments key={key} geometry={geometry}>
          <lineBasicMaterial color={color} opacity={opacity} transparent depthWrite={false} />
        </lineSegments>
      ))}
    </>
  );
};

// ────────────────────────────────────────────────────
// Pulse animation along selected edges
// ────────────────────────────────────────────────────

const PulseParticles: React.FC<{
  edges: GraphEdge[];
  positions: Map<number, THREE.Vector3>;
  selectedNodeIds: Set<number>;
}> = ({ edges, positions, selectedNodeIds }) => {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const selectedEdges = useMemo(() =>
    edges.filter(e => selectedNodeIds.has(e.source) && selectedNodeIds.has(e.target))
      .filter(e => positions.has(e.source) && positions.has(e.target))
      .slice(0, 20), // Cap at 20 pulses for performance
    [edges, positions, selectedNodeIds]
  );

  useFrame(({ clock }) => {
    if (!meshRef.current || selectedEdges.length === 0) return;
    const t = clock.elapsedTime;

    selectedEdges.forEach((edge, i) => {
      const s = positions.get(edge.source)!;
      const target = positions.get(edge.target)!;
      const progress = ((t * 0.5 + i * 0.15) % 1);
      dummy.position.lerpVectors(s, target, progress);
      dummy.scale.setScalar(0.08);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);
    });
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  if (selectedEdges.length === 0) return null;

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, selectedEdges.length]}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial color="#00f2fe" transparent opacity={0.8} />
    </instancedMesh>
  );
};

// ────────────────────────────────────────────────────
// Drift pulse ring
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
// Single graph node sphere with intelligence highlighting
// ────────────────────────────────────────────────────

const GraphNodeMesh: React.FC<{
  node: GraphNode;
  position: THREE.Vector3;
  color: string;
  isSelected: boolean;
  hasContext: boolean;
  onHover: (node: GraphNode | null) => void;
}> = ({ node, position, color, isSelected, hasContext, onHover }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const radius = Math.max(0.15, Math.min(0.8, 0.1 + node.node_count * 0.015));

  // Intelligence-driven appearance
  const nodeColor = isSelected ? '#00f2fe' : color;
  const emissiveIntensity = isSelected ? 1.2 : (hasContext ? 0.05 : (node.recently_modified ? 0.8 : 0.4));
  const nodeOpacity = hasContext && !isSelected ? 0.12 : 1.0;

  return (
    <Float speed={1.5} rotationIntensity={0.2} floatIntensity={0.5}>
      <group position={position}>
        <mesh
          ref={meshRef}
          onPointerEnter={(e) => { e.stopPropagation(); onHover(node); }}
          onPointerLeave={() => onHover(null)}
        >
          <sphereGeometry args={[isSelected ? radius * 1.3 : radius, 16, 16]} />
          <meshStandardMaterial
            color={nodeColor}
            emissive={nodeColor}
            emissiveIntensity={emissiveIntensity}
            roughness={0.2}
            metalness={0.8}
            transparent={hasContext && !isSelected}
            opacity={nodeOpacity}
          />
        </mesh>
        {/* Glow ring for selected nodes */}
        {isSelected && (
          <mesh>
            <ringGeometry args={[radius * 1.5, radius * 1.8, 32]} />
            <meshBasicMaterial color="#00f2fe" transparent opacity={0.3} side={THREE.DoubleSide} />
          </mesh>
        )}
        {node.recently_modified && !isSelected && <DriftPulse />}
      </group>
    </Float>
  );
};

// ────────────────────────────────────────────────────
// Intelligence Tooltip (with reasoning + scores)
// ────────────────────────────────────────────────────

const ScoreBar: React.FC<{ label: string; value: number; max: number; color: string }> = ({ label, value, max, color }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
    <span style={{ fontSize: '10px', color: '#8892a4', width: '70px', textAlign: 'right' }}>{label}</span>
    <div style={{ flex: 1, height: '4px', background: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
      <div style={{ width: `${Math.min(100, (value / max) * 100)}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.3s ease' }} />
    </div>
    <span style={{ fontSize: '10px', color: '#8892a4', width: '30px' }}>+{value.toFixed(2)}</span>
  </div>
);

const Tooltip: React.FC<{
  node: GraphNode;
  position: THREE.Vector3;
  contextResult: ContextResult | null;
}> = ({ node, position, contextResult }) => {
  // Find if this node is in context results
  const contextNode = contextResult?.context.find(c => c.file_path === node.file_path);
  const nodeScores = contextNode ? contextResult?.debug.scores[String(contextNode.id)] : null;
  const nodeReasons = contextNode ? contextResult?.debug.reasoning[String(contextNode.id)] : null;

  return (
    <Html position={[position.x, position.y + 1.2, position.z]} center style={{ pointerEvents: 'none' }}>
      <div style={{
        background: 'rgba(10, 12, 20, 0.92)',
        backdropFilter: 'blur(16px)',
        border: `1px solid ${contextNode ? 'rgba(0, 242, 254, 0.4)' : 'rgba(0, 242, 254, 0.2)'}`,
        borderRadius: '10px',
        padding: '12px 16px',
        minWidth: '240px',
        maxWidth: '320px',
        color: '#e0e6ed',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        fontSize: '11px',
        lineHeight: '1.5',
        boxShadow: contextNode
          ? '0 8px 32px rgba(0, 0, 0, 0.5), 0 0 24px rgba(0, 242, 254, 0.15)'
          : '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 16px rgba(0, 242, 254, 0.1)',
      }}>
        {/* File name */}
        <div style={{ fontSize: '13px', fontWeight: 700, color: '#fff', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>📁</span>
          <span style={{ wordBreak: 'break-all' }}>{node.file_path.replace('./', '')}</span>
        </div>

        {/* Intelligence Panel (shown for context nodes) */}
        {contextNode && nodeScores && (
          <div style={{ borderTop: '1px solid rgba(0, 242, 254, 0.2)', paddingTop: '8px', marginBottom: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '10px', color: '#00f2fe', letterSpacing: '1px', fontWeight: 600 }}>INTELLIGENCE</span>
              <span style={{ fontSize: '14px', fontWeight: 700, color: '#00f2fe' }}>{contextNode.relevance_score.toFixed(2)}</span>
            </div>
            <ScoreBar label="exact" value={nodeScores.exact_match || 0} max={2} color="#00f2fe" />
            <ScoreBar label="proximity" value={nodeScores.proximity || 0} max={2} color="#4facfe" />
            <ScoreBar label="embedding" value={nodeScores.embedding || 0} max={2} color="#06d6a0" />
            <ScoreBar label="dependency" value={nodeScores.dependency || 0} max={2} color="#f77f00" />
            <ScoreBar label="recency" value={nodeScores.recency || 0} max={2} color="#ff0a54" />
          </div>
        )}

        {/* Reasoning strings */}
        {nodeReasons && nodeReasons.length > 0 && (
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px', marginBottom: '6px' }}>
            <div style={{ fontSize: '10px', color: '#8892a4', letterSpacing: '1px', marginBottom: '4px' }}>REASONING</div>
            {nodeReasons.map((r, i) => (
              <div key={i} style={{ fontSize: '10px', color: '#06d6a0', marginBottom: '2px' }}>→ {r}</div>
            ))}
          </div>
        )}

        {/* Counts */}
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px', marginBottom: '6px', display: 'flex', gap: '12px' }}>
          <span><span style={{ color: '#ff0a54' }}>●</span> {node.classes} classes</span>
          <span><span style={{ color: '#00f2fe' }}>●</span> {node.functions} functions</span>
        </div>

        {/* Top entities */}
        {node.top_entities.length > 0 && (
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px' }}>
            <div style={{ color: '#8892a4', fontSize: '10px', letterSpacing: '1px', marginBottom: '4px' }}>TOP ENTITIES</div>
            {node.top_entities.map((e, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <span style={{
                  fontSize: '9px', padding: '1px 5px', borderRadius: '3px',
                  background: e.type === 'class' ? 'rgba(255, 10, 84, 0.2)' : 'rgba(0, 242, 254, 0.2)',
                  color: e.type === 'class' ? '#ff0a54' : '#00f2fe',
                  fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase',
                }}>{e.type}</span>
                <span>{e.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Drift indicator */}
        {node.recently_modified && (
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px', marginTop: '4px', color: '#ff0a54', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '14px' }}>🔴</span> RECENTLY MODIFIED
          </div>
        )}

        {/* Skill badge in tooltip */}
        {contextNode && contextResult?.debug.skill && (
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px', marginTop: '4px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(0, 242, 254, 0.15)', color: '#00f2fe', fontWeight: 600, letterSpacing: '0.5px' }}>
              {contextResult.debug.intent}
            </span>
            <span style={{ fontSize: '10px', color: '#8892a4' }}>via {contextResult.debug.skill}</span>
          </div>
        )}
      </div>
    </Html>
  );
};

// ────────────────────────────────────────────────────
// View Mode Toggle Overlay
// ────────────────────────────────────────────────────

const ViewModeToggle: React.FC<{
  mode: GraphViewMode;
  onChange: (mode: GraphViewMode) => void;
  hasContext: boolean;
}> = ({ mode, onChange, hasContext }) => {
  const modes: { key: GraphViewMode; label: string }[] = [
    { key: 'full', label: 'FULL' },
    { key: 'context', label: 'CONTEXT' },
    { key: 'dependency', label: 'DEPS' },
  ];

  return (
    <div style={{
      position: 'absolute', bottom: 24, right: 24, zIndex: 10,
      display: 'flex', gap: '2px',
      background: 'rgba(10, 12, 20, 0.65)', backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px',
      padding: '3px', fontFamily: "'Inter', sans-serif", fontSize: '10px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)', pointerEvents: 'auto',
    }}>
      {modes.map(m => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          disabled={!hasContext && m.key !== 'full'}
          style={{
            background: mode === m.key ? 'rgba(0, 242, 254, 0.2)' : 'transparent',
            border: 'none', borderRadius: '5px',
            color: mode === m.key ? '#00f2fe' : ((!hasContext && m.key !== 'full') ? '#333' : '#8892a4'),
            padding: '6px 12px', cursor: (!hasContext && m.key !== 'full') ? 'default' : 'pointer',
            fontWeight: mode === m.key ? 700 : 400, letterSpacing: '1px',
            transition: 'all 0.2s ease', fontFamily: "'Inter', sans-serif", fontSize: '10px',
          }}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
};

// ────────────────────────────────────────────────────
// Node cloud with intelligence state
// ────────────────────────────────────────────────────

const NodeCloud: React.FC<{
  graphData: GraphData;
  contextResult: ContextResult | null;
  viewMode: GraphViewMode;
}> = ({ graphData, contextResult, viewMode }) => {
  const groupRef = useRef<THREE.Group>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  const clusterIndex = useMemo(() => new Map<string, number>(), []);
  const positions = useMemo(
    () => computePositions(graphData.nodes, clusterIndex),
    [graphData.nodes]
  );

  // Build set of selected node IDs (graph node IDs whose file_path matches context)
  const selectedFilePaths = useMemo(() => {
    if (!contextResult) return new Set<string>();
    return new Set(contextResult.context.map(c => c.file_path));
  }, [contextResult]);

  const selectedNodeIds = useMemo(() => {
    const ids = new Set<number>();
    graphData.nodes.forEach(n => {
      if (selectedFilePaths.has(n.file_path)) ids.add(n.id);
    });
    return ids;
  }, [graphData.nodes, selectedFilePaths]);

  // Filter nodes based on view mode
  const visibleNodes = useMemo(() => {
    if (viewMode === 'full' || !contextResult) return graphData.nodes;
    if (viewMode === 'context') {
      // Show selected + direct neighbors
      const neighborIds = new Set<number>(selectedNodeIds);
      graphData.edges.forEach(e => {
        if (selectedNodeIds.has(e.source)) neighborIds.add(e.target);
        if (selectedNodeIds.has(e.target)) neighborIds.add(e.source);
      });
      return graphData.nodes.filter(n => neighborIds.has(n.id));
    }
    // dependency mode — only nodes on paths between selected
    return graphData.nodes.filter(n => selectedNodeIds.has(n.id));
  }, [graphData, contextResult, viewMode, selectedNodeIds]);

  const hasContext = contextResult !== null && contextResult.context.length > 0;

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
      <EdgeLines
        edges={graphData.edges}
        positions={positions}
        selectedNodeIds={selectedNodeIds}
        hasContext={hasContext}
      />
      {hasContext && (
        <PulseParticles
          edges={graphData.edges}
          positions={positions}
          selectedNodeIds={selectedNodeIds}
        />
      )}
      {visibleNodes.map((node) => {
        const pos = positions.get(node.id);
        if (!pos) return null;
        const color = getClusterColor(node.cluster, clusterIndex);
        const isSelected = selectedNodeIds.has(node.id);
        return (
          <GraphNodeMesh
            key={node.id}
            node={node}
            position={pos}
            color={color}
            isSelected={isSelected}
            hasContext={hasContext}
            onHover={handleHover}
          />
        );
      })}
      {hoveredNode && positions.get(hoveredNode.id) && (
        <Tooltip
          node={hoveredNode}
          position={positions.get(hoveredNode.id)!}
          contextResult={contextResult}
        />
      )}
    </group>
  );
};

// ────────────────────────────────────────────────────
// Fallback loading cloud
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
// Status Indicator + Query Panel overlays
// ────────────────────────────────────────────────────

const StatusIndicator: React.FC<{ status: 'SYNCING' | 'LIVE' | 'ERROR' }> = ({ status }) => {
  const color = status === 'LIVE' ? '#06d6a0' : status === 'SYNCING' ? '#00f2fe' : '#ff0a54';
  const text = status === 'LIVE' ? 'SYSTEM LIVE' : status === 'SYNCING' ? 'SYNCING...' : 'DISCONNECTED';

  return (
    <div style={{
      position: 'absolute', top: 24, right: 24, zIndex: 10,
      background: 'rgba(10, 12, 20, 0.65)', backdropFilter: 'blur(12px)',
      border: `1px solid ${color}33`, borderRadius: '20px',
      padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '8px',
      fontFamily: "'Inter', sans-serif", fontSize: '11px', fontWeight: 600, color: color,
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)', transition: 'all 0.3s ease',
      pointerEvents: 'none', userSelect: 'none'
    }}>
      <div style={{
        width: '6px', height: '6px', borderRadius: '50%',
        background: color, boxShadow: `0 0 8px ${color}`,
        animation: status === 'SYNCING' ? 'visor-pulse 0.8s infinite alternate' : 'none'
      }} />
      <span style={{ letterSpacing: '0.5px' }}>{text}</span>
      <style>{`
        @keyframes visor-pulse {
          0% { opacity: 0.3; transform: scale(0.9); }
          100% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </div>
  );
};

const QueryPanel: React.FC<{ contextResult: ContextResult | null }> = ({ contextResult }) => {
  if (!contextResult || contextResult.context.length === 0) return null;

  return (
    <div style={{
      position: 'absolute', top: 24, left: 24, zIndex: 10,
      background: 'rgba(10, 12, 20, 0.75)', backdropFilter: 'blur(12px)',
      border: '1px solid rgba(0, 242, 254, 0.2)', borderRadius: '10px',
      padding: '12px 16px', minWidth: '220px',
      fontFamily: "'Inter', sans-serif", fontSize: '11px', color: '#e0e6ed',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)', pointerEvents: 'none', userSelect: 'none',
    }}>
      <div style={{ fontSize: '10px', color: '#8892a4', letterSpacing: '1px', marginBottom: '6px' }}>ACTIVE QUERY</div>
      <div style={{ fontSize: '13px', fontWeight: 700, color: '#fff', marginBottom: '8px' }}>"{contextResult.query}"</div>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '6px' }}>
        <div>
          <div style={{ fontSize: '9px', color: '#8892a4', letterSpacing: '1px' }}>INTENT</div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#00f2fe' }}>{contextResult.debug.intent}</div>
        </div>
        <div>
          <div style={{ fontSize: '9px', color: '#8892a4', letterSpacing: '1px' }}>NODES</div>
          <div style={{ fontSize: '12px', fontWeight: 600 }}>{contextResult.context.length}</div>
        </div>
        <div>
          <div style={{ fontSize: '9px', color: '#8892a4', letterSpacing: '1px' }}>REDUCTION</div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#06d6a0' }}>{contextResult.metrics.reduction_percent}%</div>
        </div>
      </div>
      {contextResult.debug.skill && (
        <div style={{
          display: 'inline-block', fontSize: '9px', padding: '3px 8px', borderRadius: '4px',
          background: 'rgba(0, 242, 254, 0.12)', color: '#00f2fe', fontWeight: 600, letterSpacing: '0.5px',
        }}>
          🧠 {contextResult.debug.skill}
        </div>
      )}
    </div>
  );
};

const EdgeLegend: React.FC = () => {
  return (
    <div style={{
      position: 'absolute', bottom: 24, left: 24, zIndex: 10,
      background: 'rgba(10, 12, 20, 0.65)', backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px',
      padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: '6px',
      fontFamily: "'Inter', sans-serif", fontSize: '11px', color: '#e0e6ed',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)', pointerEvents: 'none', userSelect: 'none'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ width: '12px', height: '2px', background: EDGE_STYLE.IMPORTS.color, opacity: EDGE_STYLE.IMPORTS.opacity + 0.3 }} />
        <span>Structural Import</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ width: '12px', height: '2px', background: EDGE_STYLE.CALLS.color, opacity: EDGE_STYLE.CALLS.opacity + 0.4 }} />
        <span>Function Call</span>
      </div>
    </div>
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
  const [contextResult, setContextResult] = useState<ContextResult | null>(null);
  const [viewMode, setViewMode] = useState<GraphViewMode>('full');
  const [syncStatus, setSyncStatus] = useState<'SYNCING' | 'LIVE' | 'ERROR'>('SYNCING');
  const vscode = getVsCode();

  useEffect(() => {
    const messageHandler = (event: MessageEvent) => {
      if (event.data.command === 'graphData') {
        try {
          setGraphData(event.data.data);
          setSyncStatus('LIVE');
        } catch (err: any) {
          console.error('[Err] graphData failed:', err.message);
          setSyncStatus('ERROR');
        }
      } else if (event.data.command === 'contextResultData') {
        try {
          setContextResult(event.data.data);
          if (event.data.data.context.length > 0) setViewMode('context');
        } catch (err: any) {
          console.error('[Err] contextResultData failed:', err.message);
        }
      }
    };

    window.addEventListener('message', messageHandler);

    const fetchGraph = () => {
      if (vscode) {
        setSyncStatus('SYNCING');
        vscode.postMessage({ command: 'fetchGraphData' });
      } else {
        setSyncStatus('ERROR');
      }
    };

    fetchGraph();
    const interval = setInterval(fetchGraph, 10000);

    return () => {
      clearInterval(interval);
      window.removeEventListener('message', messageHandler);
    };
  }, []);

  const hasContext = contextResult !== null && contextResult.context.length > 0;

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 0 }}>
      <StatusIndicator status={syncStatus} />
      <QueryPanel contextResult={contextResult} />
      <EdgeLegend />
      <ViewModeToggle mode={viewMode} onChange={setViewMode} hasContext={hasContext} />

      <Canvas camera={{ position: [0, 0, 28], fov: 60 }}>
        <color attach="background" args={['#090a0f']} />
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={1.5} color="#00f2fe" />
        <pointLight position={[-10, -10, -10]} intensity={1} color="#ff0a54" />
        <Stars radius={50} depth={50} count={3000} factor={4} saturation={1} fade speed={1} />
        {graphData && graphData.nodes && graphData.nodes.length > 0 ? (
          <NodeCloud
            graphData={graphData}
            contextResult={contextResult}
            viewMode={viewMode}
          />
        ) : (
          <LoadingCloud />
        )}
        <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} autoRotate autoRotateSpeed={0.3} />
      </Canvas>
    </div>
  );
};
