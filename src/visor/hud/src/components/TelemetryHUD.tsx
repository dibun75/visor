import { useState, useEffect } from 'react';
import { Activity, Database, ShieldAlert, Cpu } from 'lucide-react';

export const TelemetryHUD = () => {
    // Simulating drifting context for the aesthetic
    const [drift, setDrift] = useState(false);

    useEffect(() => {
        const interval = setInterval(() => {
            setDrift((prev) => !prev);
        }, 8000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{ 
            position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', 
            pointerEvents: 'none', zIndex: 10, padding: '32px', 
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between', 
            boxSizing: 'border-box' 
        }}>
            
            {/* Top Bar HUD */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="glass-panel" style={{ padding: '20px', display: 'flex', gap: '20px', alignItems: 'center' }}>
                    <Activity color="var(--primary)" size={32} />
                    <div>
                        <h2 style={{ fontSize: '12px', margin: 0, color: 'var(--text-muted)', letterSpacing: '2px' }}>V.I.S.O.R. MCP</h2>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-main)', letterSpacing: '1px' }}>SYSTEM NOMINAL</div>
                    </div>
                </div>

                {drift && (
                    <div className="glass-panel critical-flash" style={{ padding: '20px', display: 'flex', gap: '20px', alignItems: 'center', backgroundColor: 'rgba(255, 10, 84, 0.1)' }}>
                        <ShieldAlert color="var(--accent-critical)" size={32} />
                        <div>
                            <h2 style={{ fontSize: '12px', margin: 0, color: 'var(--accent-critical)', letterSpacing: '2px' }}>CRITICAL ALERT</h2>
                            <div style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--text-main)' }}>CONTEXT DRIFT: STALE AST</div>
                        </div>
                    </div>
                )}
            </div>

            {/* Bottom Bar Telemetry */}
            <div style={{ display: 'flex', gap: '24px', maxWidth: '800px', margin: '0 auto' }}>
                <div className="glass-panel" style={{ padding: '20px', flex: 1, display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <Cpu color="var(--primary)" size={32} />
                    <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px' }}>AGENT CONTEXT BURN</div>
                        <div style={{ fontSize: '20px', fontWeight: 600 }}>12,840 <span style={{fontSize:'12px', color:'var(--text-muted)'}}>/ 128,000 TOKENS</span></div>
                    </div>
                </div>
                
                <div className="glass-panel" style={{ padding: '20px', flex: 1, display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <Database color="var(--secondary)" size={32} />
                    <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '1px' }}>GRAPH DATABASE SCALE</div>
                        <div style={{ fontSize: '20px', fontWeight: 600 }}>1,208 <span style={{fontSize:'12px', color:'var(--text-muted)'}}>LOCAL NODES</span></div>
                    </div>
                </div>
            </div>
        </div>
    );
};
