#!/usr/bin/env node

import { createRequire } from 'node:module';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const demoDir = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(demoDir, '..');
const hudDir = path.join(rootDir, 'src', 'visor', 'hud');
const outputPath = path.join(rootDir, 'docs', 'assets', 'hud_overview.png');
const requireFromHud = createRequire(path.join(hudDir, 'package.json'));
const { chromium } = requireFromHud('@playwright/test');

const python = String.raw`
import asyncio
import json
from visor.server import mcp

async def call(name, arguments):
    content, _ = await mcp.call_tool(name, arguments)
    return json.loads(content[0].text)

async def main():
    payload = {
        "graph": await call("get_architecture_map", {"depth": 1}),
        "telemetry": await call("get_telemetry", {}),
        "context": await call("build_context", {
            "query": "resolve local workspace project root",
            "skill": "architecture-explainer",
        }),
    }
    print("VISOR_CAPTURE=" + json.dumps(payload))

asyncio.run(main())
`;

const result = spawnSync('uv', ['run', 'python', '-c', python], {
  cwd: rootDir,
  env: { ...process.env, WORKSPACE_ROOT: rootDir },
  encoding: 'utf8',
});
if (result.status !== 0) {
  process.stderr.write(result.stderr);
  process.exit(result.status ?? 1);
}
const line = result.stdout.split('\n').find((value) => value.startsWith('VISOR_CAPTURE='));
if (!line) throw new Error('V.I.S.O.R. did not return capture data');
const data = JSON.parse(line.slice('VISOR_CAPTURE='.length));

const server = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '4173'], {
  cwd: hudDir,
  stdio: 'ignore',
});

async function waitForServer() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:4173');
      if (response.ok) return;
    } catch {
      // Vite has not bound the port yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Timed out waiting for the HUD development server');
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.addInitScript((capture) => {
    window.INITIAL_VIEW_MODE = 'panel';
    let sentContext = false;
    window.acquireVsCodeApi = () => ({
      postMessage(message) {
        const send = (command, value) => window.dispatchEvent(
          new MessageEvent('message', { data: { command, data: value } }),
        );
        if (message.command === 'fetchGraphData') send('graphData', capture.graph);
        if (message.command === 'fetchTelemetry') {
          send('telemetryData', capture.telemetry);
          if (!sentContext) {
            send('contextResultData', capture.context);
            sentContext = true;
          }
          if (capture.telemetry.agent_focus) {
            send('agentFocusData', capture.telemetry.agent_focus);
          }
          if (capture.telemetry.drift_files?.length) {
            send('driftFilesData', capture.telemetry.drift_files);
          }
        }
      },
    });
  }, data);
  await page.goto('http://127.0.0.1:4173', { waitUntil: 'networkidle' });
  await page.getByText('LIVE').waitFor();
  await page.getByText('LAST QUERY').waitFor();
  await page.getByRole('button', { name: 'FULL', exact: true }).click();
  await page.waitForTimeout(750);
  await page.screenshot({ path: outputPath });
  process.stdout.write(`Wrote ${outputPath}\n`);
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM');
}
