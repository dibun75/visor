import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

let currentPanel: vscode.WebviewPanel | undefined = undefined;
let mcpClient: Client | undefined = undefined;
let activeTransport: StdioClientTransport | undefined = undefined;

const outputChannel = vscode.window.createOutputChannel("V.I.S.O.R.");

/**
 * Resolve the absolute path to `uv` across all environments:
 *   - Local VS Code / Antigravity
 *   - SSH Remote (minimal PATH in extension host)
 */
function resolveUvPath(): string {
    const home = process.env.HOME || '';
    const candidates = [
        `${home}/.local/bin/uv`,
        `${home}/.cargo/bin/uv`,
        '/usr/local/bin/uv',
        '/usr/bin/uv',
    ];

    // Try `which uv` with an augmented PATH that includes common locations
    const augmentedPath = [
        `${home}/.local/bin`,
        `${home}/.cargo/bin`,
        '/usr/local/bin',
        process.env.PATH || ''
    ].join(':');

    try {
        const found = cp.execSync('which uv', { 
            env: { ...process.env, PATH: augmentedPath },
            timeout: 5000 
        }).toString().trim();
        if (found && fs.existsSync(found)) return found;
    } catch {}

    // Fallback: check candidate paths directly
    for (const p of candidates) {
        if (fs.existsSync(p)) return p;
    }

    return 'uv'; // last resort — hope it's on PATH
}

/**
 * Build environment for the spawned server process.
 * Ensures PATH includes common tool locations even when
 * the extension host has a minimal environment.
 */
function buildServerEnv(workspaceFolder: string): Record<string, string> {
    const home = process.env.HOME || '';
    const extraPaths = [
        `${home}/.local/bin`,
        `${home}/.cargo/bin`,
        '/usr/local/bin',
    ];
    const currentPath = process.env.PATH || '/usr/bin:/bin';
    const fullPath = [...extraPaths, currentPath].join(':');

    return {
        ...process.env as Record<string, string>,
        PATH: fullPath,
        WORKSPACE_ROOT: workspaceFolder,
        PYTHONPATH: workspaceFolder,
    };
}

async function ensureMCPConnected(workspaceFolder: string, context: vscode.ExtensionContext) {
    if (mcpClient) return mcpClient;

    // Clean up any previous transport
    if (activeTransport) {
        try { await activeTransport.close(); } catch {}
        activeTransport = undefined;
    }

    const uvPath = resolveUvPath();
    const config = vscode.workspace.getConfiguration('visor');
    let customServerPath = config.get<string>('serverPath');
    
    const localServerPath = path.join(workspaceFolder, 'src', 'visor', 'server.py');
    const serverEnv = buildServerEnv(workspaceFolder);
    
    let cmd = uvPath;
    let args: string[] = [];

    outputChannel.appendLine(`[VISOR] === Connection attempt at ${new Date().toISOString()} ===`);
    outputChannel.appendLine(`[VISOR] uv path: ${uvPath}`);

    if (customServerPath) {
        outputChannel.appendLine(`[VISOR] Using configured serverPath: ${customServerPath}`);
        args = ['--directory', workspaceFolder, 'run', '-q', customServerPath];
    } else if (fs.existsSync(localServerPath)) {
        outputChannel.appendLine(`[VISOR] Found local server.py in workspace: ${localServerPath}`);
        args = ['--directory', workspaceFolder, 'run', '-q', localServerPath];
    } else {
        outputChannel.appendLine(`[VISOR] No local server.py found. Trying global 'visor-mcp' tool...`);
        // Use uv to run the globally installed visor-mcp or fetch it
        args = ['tool', 'run', 'visor-mcp'];
    }

    // Pre-flight: verify uv can run
    try {
        const uvVersion = cp.execSync(`"${uvPath}" --version`, { 
            env: serverEnv, timeout: 10000 
        }).toString().trim();
        outputChannel.appendLine(`[VISOR] uv version: ${uvVersion}`);
    } catch (e: any) {
        const msg = `Cannot run uv at "${uvPath}": ${e.message}`;
        outputChannel.appendLine(`[VISOR] FATAL: ${msg}`);
        outputChannel.show(true);
        vscode.window.showErrorMessage(`V.I.S.O.R.: ${msg}`);
        throw new Error(msg);
    }

    activeTransport = new StdioClientTransport({
        command: cmd,
        args: args,
        env: serverEnv,
        stderr: 'pipe',
    });

    // Capture stderr from the server process for diagnostics
    activeTransport.stderr?.on('data', (chunk: Buffer) => {
        const lines = chunk.toString().trim();
        if (lines) outputChannel.appendLine(`[server] ${lines}`);
    });

    activeTransport.onerror = (err) => {
        outputChannel.appendLine(`[VISOR] Transport error: ${err}`);
        console.error("Transport error:", err);
        mcpClient = undefined;
        activeTransport = undefined;
    };
    activeTransport.onclose = () => {
        outputChannel.appendLine("[VISOR] Transport closed");
        mcpClient = undefined;
        activeTransport = undefined;
    };

    const client = new Client({
        name: "VSCode-HUD",
        version: "1.0.0"
    }, {
        capabilities: {}
    });

    try {
        outputChannel.appendLine("[VISOR] Connecting to MCP server...");
        await client.connect(activeTransport);
        outputChannel.appendLine("[VISOR] ✅ MCP Connected successfully!");
        mcpClient = client;
    } catch (e: any) {
        mcpClient = undefined;
        activeTransport = undefined;
        const errMsg = e?.message || String(e);
        outputChannel.appendLine(`[VISOR] ❌ MCP Connect FAILED: ${errMsg}`);
        outputChannel.show(true);
        vscode.window.showErrorMessage(`V.I.S.O.R. connection failed. Check Output → V.I.S.O.R. for details.`);
        console.error("MCP Connect Error:", e);
        throw e;
    }

    return mcpClient;
}

function getWebviewContent(webview: vscode.Webview, extensionPath: string, viewType: string): string {
    const hudHtmlPath = path.join(extensionPath, 'hud-dist', 'index.html');
    let htmlContent = "";
    try {
        htmlContent = fs.readFileSync(hudHtmlPath, 'utf-8');
        htmlContent = htmlContent.replace('<head>', `<head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} https: data:; script-src 'unsafe-inline' 'unsafe-eval' ${webview.cspSource} https:; style-src 'unsafe-inline' ${webview.cspSource} https:; font-src data: ${webview.cspSource} https:; connect-src ws: wss: https: http:;">`);
        const assetsUri = webview.asWebviewUri(vscode.Uri.file(path.join(extensionPath, 'hud-dist', 'assets')));
        htmlContent = htmlContent.replace(/(href|src)="\/assets([^"]+)"/g, `$1="${assetsUri}$2"`);
        htmlContent = htmlContent.replace('</head>', `<script>window.INITIAL_VIEW_MODE = "${viewType}";</script></head>`);
    } catch(e) {
        htmlContent = `<h1>HUD Build Not Found</h1><p>Expected bundled UI at ${hudHtmlPath}</p>`;
    }
    return htmlContent;
}

function setupMessageListener(webview: vscode.Webview) {
    webview.onDidReceiveMessage(async (message) => {
        if (message.command === 'fetchTelemetry' && mcpClient) {
            try {
                const result = await mcpClient.callTool({
                    name: 'get_telemetry',
                    arguments: {}
                });
                if (result.content && (result.content as any[]).length > 0) {
                    const jsonStr = (result.content as any)[0].text;
                    const data = JSON.parse(jsonStr as string);
                    webview.postMessage({
                        command: 'telemetryData',
                        data: data
                    });
                    if (data.agent_focus) {
                        webview.postMessage({
                            command: 'agentFocusData',
                            data: data.agent_focus
                        });
                    }
                    if (data.drift_files && data.drift_files.length > 0) {
                        webview.postMessage({
                            command: 'driftFilesData',
                            data: data.drift_files
                        });
                    }
                }
            } catch(err) {
                console.error("Tool call failed", err);
            }
        } else if (message.command === 'fetchGraphData' && mcpClient) {
            try {
                const result = await mcpClient.callTool({
                    name: 'get_architecture_map',
                    arguments: { depth: 1 }
                });
                
                if (result.content && (result.content as any[]).length > 0) {
                    const jsonStr = (result.content as any)[0].text;
                    const data = JSON.parse(jsonStr as string);
                    webview.postMessage({
                        command: 'graphData',
                        data: data
                    });
                } else {
                    console.error("V.I.S.O.R.: Empty result content from get_architecture_map");
                }
            } catch(err: any) {
                console.error("Graph data fetch failed", err);
            }
        } else if (message.command === 'fetchSkills' && mcpClient) {
            try {
                const result = await mcpClient.callTool({ name: 'list_custom_skills', arguments: {} });
                if (result.content && (result.content as any[]).length > 0) {
                    webview.postMessage({ command: 'skillsData', data: JSON.parse((result.content as any)[0].text as string) });
                }
            } catch(err) { console.error("fetchSkills failed", err); }
        } else if (message.command === 'addCustomSkill' && mcpClient) {
            try {
                await mcpClient.callTool({ name: 'add_custom_skill', arguments: message.payload });
            } catch(err) { console.error("addCustomSkill failed", err); }
        } else if (message.command === 'deleteSkill' && mcpClient) {
            try {
                await mcpClient.callTool({ name: 'delete_custom_skill', arguments: message.payload });
            } catch(err) { console.error("deleteSkill failed", err); }
        } else if (message.command === 'openFullGraph') {
            vscode.commands.executeCommand('visor.startHUD');
        } else if (message.command === 'fetchContextResult' && mcpClient) {
            try {
                const args: any = { query: message.payload.query };
                if (message.payload.skill) { args.skill = message.payload.skill; }
                const result = await mcpClient.callTool({ name: 'build_context', arguments: args });
                if (result.content && (result.content as any[]).length > 0) {
                    const data = JSON.parse((result.content as any)[0].text as string);
                    webview.postMessage({ command: 'contextResultData', data: data });
                }
            } catch(err) { console.error("fetchContextResult failed", err); }
        }
    });
}

class VisorSidebarProvider implements vscode.WebviewViewProvider {
    constructor(private readonly _extensionUri: vscode.Uri, private readonly _workspaceFolder: string, private readonly _context: vscode.ExtensionContext) {}

    public async resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.file(path.join(this._context.extensionPath, 'hud-dist'))]
        };

        webviewView.webview.html = getWebviewContent(webviewView.webview, this._context.extensionPath, 'sidebar');

        setupMessageListener(webviewView.webview);
        await ensureMCPConnected(this._workspaceFolder, this._context);
    }
}

export async function activate(context: vscode.ExtensionContext) {
    try {
        cp.execSync('uv --version', { stdio: 'ignore' });
    } catch {
        vscode.window.showInformationMessage('Installing uv for V.I.S.O.R...');
        try {
            cp.execSync('curl -LsSf https://astral.sh/uv/install.sh | sh', { stdio: 'inherit' });
        } catch (e) {
            vscode.window.showErrorMessage('Failed to install uv...');
            return;
        }
    }

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();

    // Register Sidebar Provider
    const sidebarProvider = new VisorSidebarProvider(context.extensionUri, workspaceFolder, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('visor-sidebar', sidebarProvider)
    );

    let disposable = vscode.commands.registerCommand('visor.startHUD', async () => {
        if (currentPanel) {
            currentPanel.reveal(vscode.ViewColumn.Two);
            return;
        }

        await ensureMCPConnected(workspaceFolder, context);

        currentPanel = vscode.window.createWebviewPanel(
            'visorHUD',
            'V.I.S.O.R JARVIS HUD',
            vscode.ViewColumn.Two,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.file(path.join(context.extensionPath, 'hud-dist'))]
            }
        );

        currentPanel.webview.html = getWebviewContent(currentPanel.webview, context.extensionPath, 'panel');
        
        setupMessageListener(currentPanel.webview);

        currentPanel.onDidDispose(() => {
            currentPanel = undefined;
        }, null, context.subscriptions);
    });

    context.subscriptions.push(disposable);
}

export function deactivate() {
    if (mcpClient && activeTransport) {
        activeTransport.close();
        mcpClient = undefined;
        activeTransport = undefined;
    }
}
