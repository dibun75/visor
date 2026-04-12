import { useState, useEffect } from 'react';
import { Activity, Database, ShieldAlert, Cpu, Maximize, Settings2, Plus, Trash2, X } from 'lucide-react';

interface TelemetryHUDProps {
    viewMode: 'sidebar' | 'panel';
}

const getVsCode = () => {
    if (!(window as any).vscodeApiInstance && (window as any).acquireVsCodeApi) {
        (window as any).vscodeApiInstance = (window as any).acquireVsCodeApi();
    }
    return (window as any).vscodeApiInstance || null;
};

export const TelemetryHUD = ({ viewMode }: TelemetryHUDProps) => {
    const [telemetry, setTelemetry] = useState({
        burn: 0,
        nodes: 0,
        drift: false
    });
    
    const [showSkillModal, setShowSkillModal] = useState(false);
    const [skills, setSkills] = useState<any[]>([]);
    const [newSkillName, setNewSkillName] = useState("");
    const [newSkillDesc, setNewSkillDesc] = useState("");
    const [newSkillContent, setNewSkillContent] = useState("");

    const isSidebar = viewMode === 'sidebar';
    const vscode = getVsCode();

    useEffect(() => {
        const messageHandler = (event: MessageEvent) => {
            const message = event.data;
            if (message.command === 'telemetryData') {
                setTelemetry({
                    burn: message.data.context_burn || 0,
                    nodes: message.data.graph_nodes || 0,
                    drift: message.data.drift_alert || false
                });
            } else if (message.command === 'skillsData') {
                setSkills(message.data || []);
            }
        };
        
        window.addEventListener('message', messageHandler);

        const fetchTelemetry = () => {
            if (vscode) {
                vscode.postMessage({ command: 'fetchTelemetry' });
            }
        };

        fetchTelemetry();
        const interval = setInterval(fetchTelemetry, 2000);
        
        return () => {
            clearInterval(interval);
            window.removeEventListener('message', messageHandler);
        };
    }, []);

    const openFullGraph = () => {
        if (vscode) {
            vscode.postMessage({ command: 'openFullGraph' });
        }
    };

    const fetchSkills = () => vscode?.postMessage({ command: 'fetchSkills' });
    const addSkill = () => {
        if (!newSkillName || !newSkillContent) return;
        vscode?.postMessage({ command: 'addCustomSkill', payload: { name: newSkillName, description: newSkillDesc, content: newSkillContent } });
        setNewSkillName(""); setNewSkillDesc(""); setNewSkillContent("");
        setTimeout(fetchSkills, 500);
    };
    const deleteSkill = (id: number) => {
        vscode?.postMessage({ command: 'deleteSkill', payload: { skill_id: id } });
        setTimeout(fetchSkills, 500);
    };

    useEffect(() => {
        if (showSkillModal) fetchSkills();
    }, [showSkillModal]);

    return (
        <div style={{ 
            position: isSidebar ? 'relative' : 'absolute', 
            top: 0, 
            left: 0, 
            width: '100%', 
            height: '100%', 
            pointerEvents: isSidebar ? 'auto' : 'none', 
            zIndex: 10, 
            padding: '24px 16px', 
            display: 'flex', 
            flexDirection: 'column', 
            justifyContent: isSidebar ? 'flex-start' : 'space-between', 
            gap: isSidebar ? '16px' : '0px',
            boxSizing: 'border-box' 
        }}>
            
            {/* Top Bar HUD */}
            <div style={{ display: 'flex', flexDirection: isSidebar ? 'column' : 'row', justifyContent: 'space-between', alignItems: isSidebar ? 'stretch' : 'flex-start', gap: '16px', pointerEvents: 'none' }}>
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', gap: '16px', alignItems: 'center', pointerEvents: 'auto' }}>
                    <Activity color="var(--primary)" size={32} />
                    <div>
                        <h2 style={{ fontSize: '12px', margin: 0, color: 'var(--text-muted)', letterSpacing: '2px' }}>V.I.S.O.R. MCP</h2>
                        <div style={{ fontSize: isSidebar ? '18px' : '24px', fontWeight: 'bold', color: 'var(--text-main)', letterSpacing: '1px' }}>SYSTEM NOMINAL</div>
                    </div>
                </div>

                {telemetry.drift && (
                    <div className="glass-panel critical-flash" style={{ padding: '16px', display: 'flex', gap: '16px', alignItems: 'center', backgroundColor: 'rgba(255, 10, 84, 0.1)', pointerEvents: 'auto' }}>
                        <ShieldAlert color="var(--accent-critical)" size={32} />
                        <div>
                            <h2 style={{ fontSize: '12px', margin: 0, color: 'var(--accent-critical)', letterSpacing: '2px' }}>CRITICAL ALERT</h2>
                            <div style={{ fontSize: isSidebar ? '14px' : '18px', fontWeight: 'bold', color: 'var(--text-main)' }}>CONTEXT DRIFT: STALE AST</div>
                        </div>
                    </div>
                )}
            </div>

            {/* Bottom Bar Telemetry */}
            <div style={{ display: 'flex', flexDirection: isSidebar ? 'column' : 'row', gap: '16px', width: '100%', maxWidth: isSidebar ? 'none' : '800px', margin: isSidebar ? '0' : '0 auto', pointerEvents: 'none' }}>
                <div className="glass-panel" style={{ padding: '16px', flex: 1, display: 'flex', alignItems: 'center', gap: '16px', pointerEvents: 'auto' }}>
                    <Cpu color="var(--primary)" size={32} />
                    <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px' }}>AGENT CONTEXT BURN</div>
                        <div style={{ fontSize: '20px', fontWeight: 600 }}>{telemetry.burn.toLocaleString()} <span style={{fontSize:'12px', color:'var(--text-muted)', display: isSidebar ? 'block' : 'inline'}}>/ 128,000 TOKENS</span></div>
                    </div>
                </div>
                
                <div className="glass-panel" style={{ padding: '16px', flex: 1, display: 'flex', alignItems: 'center', gap: '16px', pointerEvents: 'auto' }}>
                    <Database color="var(--secondary)" size={32} />
                    <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px' }}>GRAPH DATABASE SCALE</div>
                        <div style={{ fontSize: '20px', fontWeight: 600 }}>{telemetry.nodes.toLocaleString()} <span style={{fontSize:'12px', color:'var(--text-muted)', display: isSidebar ? 'block' : 'inline'}}>LOCAL NODES</span></div>
                    </div>
                </div>
            </div>

            {/* Sidebar-only Actions */}
            {isSidebar && (
                <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', pointerEvents: 'auto' }}>
                    <button 
                        onClick={openFullGraph}
                        style={{
                            background: 'linear-gradient(90deg, rgba(0,242,254,0.1), rgba(79,172,254,0.1))',
                            border: '1px solid var(--primary-glow)',
                            borderRadius: '8px',
                            color: 'var(--text-main)',
                            padding: '16px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '12px',
                            fontWeight: 'bold',
                            letterSpacing: '1px',
                            transition: 'all 0.2s ease',
                        }}
                        onMouseOver={(e) => (e.currentTarget.style.background = 'linear-gradient(90deg, rgba(0,242,254,0.2), rgba(79,172,254,0.2))')}
                        onMouseOut={(e) => (e.currentTarget.style.background = 'linear-gradient(90deg, rgba(0,242,254,0.1), rgba(79,172,254,0.1))')}
                    >
                        <Maximize size={20} color="var(--primary)" />
                        EXPAND 3D GRAPH
                    </button>
                    <p style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px', marginTop: '16px', marginBottom: '0px' }}>
                        POWERED BY MCP
                    </p>
                </div>
            )}
            
            {/* Manage Skills Button (Shown everywhere) */}
            <div style={{ display: 'flex', justifyContent: isSidebar ? 'center' : 'flex-end', marginTop: isSidebar ? '8px' : 'auto', position: isSidebar ? 'static' : 'absolute', bottom: isSidebar ? 'auto' : '24px', right: isSidebar ? 'auto' : '24px', zIndex: 10, pointerEvents: 'auto' }}>
                    <button 
                        onClick={() => setShowSkillModal(true)}
                        style={{
                            background: 'transparent',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '8px',
                            color: 'var(--text-muted)',
                            padding: '12px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '12px',
                            fontWeight: 'bold',
                            letterSpacing: '1px',
                            transition: 'all 0.2s ease',
                        }}
                        onMouseOver={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
                        onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                    >
                        <Settings2 size={18} />
                        MANAGE AI SKILLS
                    </button>
            </div>

            {showSkillModal && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100, display: 'flex', flexDirection: 'column', padding: '24px', pointerEvents: 'auto' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                        <h2 style={{ color: 'white', margin: 0 }}>Custom AI Skills</h2>
                        <button onClick={() => setShowSkillModal(false)} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}><X /></button>
                    </div>
                    
                    <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {skills.map(s => (
                            <div key={s.id} className="glass-panel" style={{ padding: '12px', display: 'flex', justifyContent: 'space-between' }}>
                                <div>
                                    <div style={{ fontWeight: 'bold' }}>{s.name}</div>
                                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{s.description}</div>
                                </div>
                                <button onClick={() => deleteSkill(s.id)} style={{ background: 'none', border: 'none', color: 'var(--accent-critical)', cursor: 'pointer' }}><Trash2 size={16}/></button>
                            </div>
                        ))}
                    </div>

                    <div className="glass-panel" style={{ padding: '16px', marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <input placeholder="Skill Name (e.g. impact_analysis)" value={newSkillName} onChange={(e) => setNewSkillName(e.target.value)} style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid #333', color: 'white', padding: '8px', borderRadius: '4px' }} />
                        <input placeholder="Short Description" value={newSkillDesc} onChange={(e) => setNewSkillDesc(e.target.value)} style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid #333', color: 'white', padding: '8px', borderRadius: '4px' }} />
                        <textarea placeholder="Markdown Instructions (The Prompt)" value={newSkillContent} onChange={(e) => setNewSkillContent(e.target.value)} rows={4} style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid #333', color: 'white', padding: '8px', borderRadius: '4px' }} />
                        <button onClick={addSkill} style={{ background: 'var(--primary)', color: 'black', border: 'none', padding: '8px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}><Plus size={16}/> ADD SKILL</button>
                    </div>
                </div>
            )}
        </div>
    );
};
