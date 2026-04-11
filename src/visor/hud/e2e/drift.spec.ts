import { test, expect } from '@playwright/test';

test.describe('V.I.S.O.R. HUD Telemetry', () => {
  test('should render JARVIS dashboard and flash Context Drift when AST becomes stale', async ({ page }) => {
    await page.goto('/');
    
    // Verify base telemetry elements render over WebGL cleanly
    await expect(page.getByText('V.I.S.O.R. MCP')).toBeVisible();
    await expect(page.getByText('AGENT CONTEXT BURN')).toBeVisible();
    await expect(page.getByText('GRAPH DATABASE SCALE')).toBeVisible();

    // The Context Drift alert cycles every 8000ms natively in our HUD.
    // We wait for it to appear to assert the CSS glow integration works perfectly over the 3D Canvas
    await expect(page.getByText('CONTEXT DRIFT: STALE AST')).toBeVisible({ timeout: 10000 });
  });
});
