import { useState, useEffect } from 'react';
import { Activity, Database, ShieldAlert, Cpu, Maximize } from 'lucide-react';

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
            <div style={{ display: 'flex', flexDirection: isSidebar ? 'column' : 'row', justifyContent: 'space-between', alignItems: isSidebar ? 'stretch' : 'flex-start', gap: '16px' }}>
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', gap: '16px', alignItems: 'center' }}>
                    <Activity color="var(--primary)" size={32} />
                    <div>
                        <h2 style={{ fontSize: '12px', margin: 0, color: 'var(--text-muted)', letterSpacing: '2px' }}>V.I.S.O.R. MCP</h2>
                        <div style={{ fontSize: isSidebar ? '18px' : '24px', fontWeight: 'bold', color: 'var(--text-main)', letterSpacing: '1px' }}>SYSTEM NOMINAL</div>
                    </div>
                </div>

                {telemetry.drift && (
                    <div className="glass-panel critical-flash" style={{ padding: '16px', display: 'flex', gap: '16px', alignItems: 'center', backgroundColor: 'rgba(255, 10, 84, 0.1)' }}>
                        <ShieldAlert color="var(--accent-critical)" size={32} />
                        <div>
                            <h2 style={{ fontSize: '12px', margin: 0, color: 'var(--accent-critical)', letterSpacing: '2px' }}>CRITICAL ALERT</h2>
                            <div style={{ fontSize: isSidebar ? '14px' : '18px', fontWeight: 'bold', color: 'var(--text-main)' }}>CONTEXT DRIFT: STALE AST</div>
                        </div>
                    </div>
                )}
            </div>

            {/* Bottom Bar Telemetry */}
            <div style={{ display: 'flex', flexDirection: isSidebar ? 'column' : 'row', gap: '16px', width: '100%', maxWidth: isSidebar ? 'none' : '800px', margin: isSidebar ? '0' : '0 auto' }}>
                <div className="glass-panel" style={{ padding: '16px', flex: 1, display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <Cpu color="var(--primary)" size={32} />
                    <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px' }}>AGENT CONTEXT BURN</div>
                        <div style={{ fontSize: '20px', fontWeight: 600 }}>{telemetry.burn.toLocaleString()} <span style={{fontSize:'12px', color:'var(--text-muted)', display: isSidebar ? 'block' : 'inline'}}>/ 128,000 TOKENS</span></div>
                    </div>
                </div>
                
                <div className="glass-panel" style={{ padding: '16px', flex: 1, display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <Database color="var(--secondary)" size={32} />
                    <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px' }}>GRAPH DATABASE SCALE</div>
                        <div style={{ fontSize: '20px', fontWeight: 600 }}>{telemetry.nodes.toLocaleString()} <span style={{fontSize:'12px', color:'var(--text-muted)', display: isSidebar ? 'block' : 'inline'}}>LOCAL NODES</span></div>
                    </div>
                </div>
            </div>

            {/* Sidebar-only Actions */}
            {isSidebar && (
                <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column' }}>
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
                    <p style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px', marginTop: '16px' }}>
                        POWERED BY MCP
                    </p>
                </div>
            )}
        </div>
    );
};
