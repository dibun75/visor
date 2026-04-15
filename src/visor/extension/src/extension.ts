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

async function ensureMCPConnected(workspaceFolder: string, context: vscode.ExtensionContext) {
    if (mcpClient) return mcpClient;

    // Clean up any previous transport
    if (activeTransport) {
        try { await activeTransport.close(); } catch {}
        activeTransport = undefined;
    }

    let uvPath = 'uv';
    try {
        uvPath = cp.execSync('which uv', { env: process.env }).toString().trim();
    } catch {
        const home = process.env.HOME;
        if (fs.existsSync(`${home}/.local/bin/uv`)) uvPath = `${home}/.local/bin/uv`;
        else if (fs.existsSync(`${home}/.cargo/bin/uv`)) uvPath = `${home}/.cargo/bin/uv`;
    }

    const serverPath = path.join(workspaceFolder, 'src', 'visor', 'server.py');
    
    outputChannel.appendLine(`[VISOR] uv path: ${uvPath}`);
    outputChannel.appendLine(`[VISOR] server path: ${serverPath}`);
    outputChannel.appendLine(`[VISOR] server exists: ${fs.existsSync(serverPath)}`);
    outputChannel.appendLine(`[VISOR] workspace: ${workspaceFolder}`);
    outputChannel.appendLine(`[VISOR] VISOR_DB_PATH: ${context.storageUri ? context.storageUri.fsPath : context.globalStorageUri.fsPath}`);

    const stderrStream = new (require('stream').PassThrough)();
    stderrStream.on('data', (chunk: Buffer) => {
        const line = chunk.toString().trim();
        if (line) {
            outputChannel.appendLine(`[server stderr] ${line}`);
        }
    });
    
    activeTransport = new StdioClientTransport({
        command: uvPath,
        args: ['--directory', workspaceFolder, 'run', '-q', serverPath],
        env: { 
            ...process.env, 
            WORKSPACE_ROOT: workspaceFolder, 
            PYTHONPATH: workspaceFolder,
            VISOR_DB_PATH: context.storageUri ? context.storageUri.fsPath : context.globalStorageUri.fsPath
        },
        stderr: stderrStream,
    });

    activeTransport.onerror = (err) => {
        outputChannel.appendLine(`[VISOR] Transport error: ${err}`);
        console.error("Transport error:", err);
        mcpClient = undefined;
        activeTransport = undefined;
    };
    activeTransport.onclose = () => {
        outputChannel.appendLine("[VISOR] Transport closed");
        console.log("Transport closed — will reconnect on next call.");
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
        outputChannel.appendLine("[VISOR] MCP Connected successfully");
        console.log("VISOR MCP Connected via stdio");
        mcpClient = client;
    } catch (e: any) {
        mcpClient = undefined;
        activeTransport = undefined;
        const errMsg = e?.message || String(e);
        outputChannel.appendLine(`[VISOR] MCP Connect FAILED: ${errMsg}`);
        outputChannel.show(true);
        vscode.window.showErrorMessage(`V.I.S.O.R. MCP connection failed: ${errMsg}`);
        console.error("MCP Connect Error:", e);
        throw e;
    }

    return mcpClient;
}

function getWebviewContent(webview: vscode.Webview, workspaceFolder: string, viewType: string): string {
    const hudHtmlPath = path.join(workspaceFolder, 'src', 'visor', 'hud', 'dist', 'index.html');
    let htmlContent = "";
    try {
        htmlContent = fs.readFileSync(hudHtmlPath, 'utf-8');
        htmlContent = htmlContent.replace('<head>', `<head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} https: data:; script-src 'unsafe-inline' 'unsafe-eval' ${webview.cspSource} https:; style-src 'unsafe-inline' ${webview.cspSource} https:; font-src data: ${webview.cspSource} https:; connect-src ws: wss: https: http:;">`);
        const assetsUri = webview.asWebviewUri(vscode.Uri.file(path.join(workspaceFolder, 'src', 'visor', 'hud', 'dist', 'assets')));
        htmlContent = htmlContent.replace(/(href|src)="\/assets([^"]+)"/g, `$1="${assetsUri}$2"`);
        htmlContent = htmlContent.replace('</head>', `<script>window.INITIAL_VIEW_MODE = "${viewType}";</script></head>`);
    } catch(e) {
        htmlContent = `<h1>HUD Build Not Found</h1><p>Run <code>npm run build</code> in src/visor/hud</p>`;
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
            localResourceRoots: [vscode.Uri.file(path.join(this._workspaceFolder, 'src', 'visor', 'hud', 'dist'))]
        };

        webviewView.webview.html = getWebviewContent(webviewView.webview, this._workspaceFolder, 'sidebar');

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
                localResourceRoots: [vscode.Uri.file(path.join(workspaceFolder, 'src', 'visor', 'hud', 'dist'))]
            }
        );

        currentPanel.webview.html = getWebviewContent(currentPanel.webview, workspaceFolder, 'panel');
        
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
