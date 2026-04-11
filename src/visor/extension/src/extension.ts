import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
	let disposable = vscode.commands.registerCommand('visor.startHUD', () => {
		const config = vscode.workspace.getConfiguration('visor');
        const port = config.get<number>('localProxyPort', 4173);

		const panel = vscode.window.createWebviewPanel(
			'visorHUD',
			'V.I.S.O.R JARVIS HUD',
			vscode.ViewColumn.Two,
			{
				enableScripts: true,
				retainContextWhenHidden: true,
                portMapping: [{ webviewPort: port, extensionHostPort: port }]
			}
		);

        // Serve the Vite dev server inside an iframe sandbox 
		panel.webview.html = getWebviewContent(port);
	});

	context.subscriptions.push(disposable);
}

function getWebviewContent(port: number) {
	return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V.I.S.O.R. HUD</title>
    <style>
        body, html { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #090a0f; }
        iframe { width: 100%; height: 100%; border: none; }
    </style>
</head>
<body>
    <iframe src="http://localhost:${port}" sandbox="allow-scripts allow-same-origin allow-forms"></iframe>
</body>
</html>`;
}

export function deactivate() {}
