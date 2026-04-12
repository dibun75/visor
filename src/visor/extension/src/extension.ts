import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

let currentPanel: vscode.WebviewPanel | undefined = undefined;
let mcpClient: Client | undefined = undefined;
let activeTransport: StdioClientTransport | undefined = undefined;

async function ensureMCPConnected(workspaceFolder: string) {
    if (mcpClient) return mcpClient;

    let uvPath = 'uv';
    try {
        uvPath = cp.execSync('which uv', { env: process.env }).toString().trim();
    } catch {
        const home = process.env.HOME;
        if (fs.existsSync(`${home}/.local/bin/uv`)) uvPath = `${home}/.local/bin/uv`;
        else if (fs.existsSync(`${home}/.cargo/bin/uv`)) uvPath = `${home}/.cargo/bin/uv`;
    }

    const serverPath = path.join(workspaceFolder, 'src', 'visor', 'server.py');
    
    activeTransport = new StdioClientTransport({
        command: uvPath,
        args: ['--directory', workspaceFolder, 'run', '-q', serverPath],
        env: { ...process.env, WORKSPACE_ROOT: workspaceFolder, PYTHONPATH: workspaceFolder }
    });

    activeTransport.onerror = (err) => console.error("Transport error:", err);
    activeTransport.onclose = () => console.log("Transport closed.");

    const client = new Client({
        name: "VSCode-HUD",
        version: "1.0.0"
    }, {
        capabilities: {}
    });

    Object.defineProperty(activeTransport, 'stderr', {
        get: function() { return undefined; }
    });
    
    try {
        await client.connect(activeTransport);
        console.log("VISOR MCP Connected via stdio");
        mcpClient = client;
    } catch (e) {
        vscode.window.showErrorMessage(`Failed to connect MCP: ${e}`);
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
        } else if (message.command === 'openFullGraph') {
            vscode.commands.executeCommand('visor.startHUD');
        }
    });
}

class VisorSidebarProvider implements vscode.WebviewViewProvider {
    constructor(private readonly _extensionUri: vscode.Uri, private readonly _workspaceFolder: string) {}

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
        await ensureMCPConnected(this._workspaceFolder);
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
    const sidebarProvider = new VisorSidebarProvider(context.extensionUri, workspaceFolder);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('visor-sidebar', sidebarProvider)
    );

    let disposable = vscode.commands.registerCommand('visor.startHUD', async () => {
        if (currentPanel) {
            currentPanel.reveal(vscode.ViewColumn.Two);
            return;
        }

        await ensureMCPConnected(workspaceFolder);

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
