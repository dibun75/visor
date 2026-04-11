import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

let currentPanel: vscode.WebviewPanel | undefined = undefined;
let mcpClient: Client | undefined = undefined;
let heartbeatInterval: NodeJS.Timeout | undefined = undefined;

export async function activate(context: vscode.ExtensionContext) {
    // Ensure uv is installed
    try {
        cp.execSync('uv --version', { stdio: 'ignore' });
    } catch {
        vscode.window.showInformationMessage('Installing uv for V.I.S.O.R...');
        try {
            cp.execSync('curl -LsSf https://astral.sh/uv/install.sh | sh', { stdio: 'inherit' });
        } catch (e) {
            vscode.window.showErrorMessage('Failed to install uv. Please install it manually.');
            return;
        }
    }

	let disposable = vscode.commands.registerCommand('visor.startHUD', async () => {
        if (currentPanel) {
            currentPanel.reveal(vscode.ViewColumn.Two);
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();

        let uvPath = 'uv';
        try {
            uvPath = cp.execSync('which uv', { env: process.env }).toString().trim();
        } catch {
            const home = process.env.HOME;
            if (fs.existsSync(`${home}/.local/bin/uv`)) uvPath = `${home}/.local/bin/uv`;
            else if (fs.existsSync(`${home}/.cargo/bin/uv`)) uvPath = `${home}/.cargo/bin/uv`;
        }

        const serverPath = path.join(workspaceFolder, 'src', 'visor', 'server.py');
        
        const transport = new StdioClientTransport({
            command: uvPath,
            args: ['--directory', workspaceFolder, 'run', '-q', serverPath],
            env: { ...process.env, WORKSPACE_ROOT: workspaceFolder, PYTHONPATH: workspaceFolder }
        });

        transport.onerror = (err) => console.error("Transport error:", err);
        transport.onclose = () => console.log("Transport closed.");

        mcpClient = new Client({
            name: "VSCode-HUD",
            version: "1.0.0"
        }, {
            capabilities: {}
        });

        // Attach stderr listener before connecting
        Object.defineProperty(transport, 'stderr', {
            get: function() { return undefined; } // prevent error if absent
        });
        
        try {
            await mcpClient.connect(transport);
            console.log("VISOR MCP Connected via stdio");
        } catch (e) {
            vscode.window.showErrorMessage(`Failed to connect MCP: ${e}`);
            console.error("MCP Connect Error:", e);
            throw e;
        }

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

        // Serve the Vite built index.html
        const hudHtmlPath = path.join(workspaceFolder, 'src', 'visor', 'hud', 'dist', 'index.html');
        let htmlContent = "";
        try {
            htmlContent = fs.readFileSync(hudHtmlPath, 'utf-8');
        } catch(e) {
            htmlContent = `<h1>HUD Build Not Found</h1><p>Run <code>npm run build</code> in src/visor/hud</p>`;
        }
		currentPanel.webview.html = htmlContent;

        // Listen for messages from React HUD
        currentPanel.webview.onDidReceiveMessage(async (message) => {
            if (message.command === 'fetchTelemetry' && mcpClient) {
                try {
                    const result = await mcpClient.callTool({
                        name: 'get_telemetry',
                        arguments: {}
                    });
                    
                    if (result.content && (result.content as any[]).length > 0) {
                        const jsonStr = (result.content as any)[0].text;
                        const data = JSON.parse(jsonStr as string);
                        currentPanel?.webview.postMessage({
                            command: 'telemetryData',
                            data: data
                        });
                    }
                } catch(err) {
                    console.error("Tool call failed", err);
                }
            }
        });

        currentPanel.onDidDispose(() => {
            currentPanel = undefined;
            if (mcpClient) {
                transport.close();
                mcpClient = undefined;
            }
        }, null, context.subscriptions);
	});

	context.subscriptions.push(disposable);
}

export function deactivate() {
    if (mcpClient) {
        // transport close handles process
    }
}
