import { test, expect } from '@playwright/test';

test.describe('V.I.S.O.R. HUD telemetry', () => {
  test('renders current telemetry and a drift warning from VS Code messages', async ({ page }) => {
    await page.addInitScript(() => {
      Object.assign(window, {
        acquireVsCodeApi: () => ({
          postMessage(message: { command?: string }) {
            if (message.command !== 'fetchTelemetry') return;
            window.dispatchEvent(new MessageEvent('message', {
              data: {
                command: 'telemetryData',
                data: {
                  context_burn: 1200,
                  graph_nodes: 42,
                  drift_alert: true,
                  drift_files: ['src/visor/workspace.py'],
                  workspace_name: 'visor',
                },
              },
            }));
          },
        }),
      });
    });

    await page.goto('/');

    await expect(page.getByText('V.I.S.O.R. MCP')).toBeVisible();
    await expect(page.getByText('TOKENS PROCESSED')).toBeVisible();
    await expect(page.getByText('GRAPH DATABASE SCALE')).toBeVisible();
    await expect(page.getByText('CONTEXT DRIFT')).toBeVisible();
    await expect(page.getByText('workspace.py')).toBeVisible();
  });
});
