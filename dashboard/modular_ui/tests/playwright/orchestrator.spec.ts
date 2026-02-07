import { test, expect } from '@playwright/test'

test('Run Analysis triggers orchestrator decision', async ({ page }) => {
  await page.goto('http://localhost:5173/')

  // Wait for the widget to render and the button to be available
  await page.waitForSelector('text=Orchestrator Decisions', { timeout: 5000 })

  // Click Run Analysis and wait for response to appear
  await page.click('text=Run Analysis')

  // When clicked, UI shows "Analyzing..." then should show a new decision (engine stub returns BUY)
  await page.waitForSelector('text=BUY', { timeout: 10000 })

  const visible = await page.isVisible('text=BUY')
  expect(visible).toBe(true)
})