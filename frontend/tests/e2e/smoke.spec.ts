/**
 * Phase 2 smoke tests — run against the live server at http://localhost:8001.
 *
 * Prerequisites:
 *   1. cd frontend && pnpm build
 *   2. uv run python -m src          (in project root)
 *   3. npx playwright test tests/e2e/
 *
 * These tests verify: page loads + is styled, the upload area is present,
 * the chat input is present, and Phase-2 features are wired (no stubs).
 * They do NOT upload a real file (no filesystem side-effect in the gate).
 */
import { test, expect } from '@playwright/test'

test.describe('Data Analysis Agent — Phase 2 smoke', () => {
  test('page loads at /app/ and shows the Data Analysis Agent heading', async ({ page }) => {
    await page.goto('/app/')
    // Either the loading spinner or the main heading must appear
    // (session init may take a moment)
    await expect(
      page.locator('h1', { hasText: 'Data Analysis Agent' })
        .or(page.locator('[class*="animate-spin"]'))
    ).toBeVisible({ timeout: 10_000 })
  })

  test('page is styled — Tailwind utility classes produce visible layout', async ({ page }) => {
    await page.goto('/app/')
    // Wait for the session to init (spinner disappears, heading appears)
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    // Header has a background-color set via Tailwind (bg-white = #ffffff)
    const header = page.locator('header').first()
    const bg = await header.evaluate(el => getComputedStyle(el).backgroundColor)
    // bg-white → rgb(255, 255, 255)
    expect(bg).toBe('rgb(255, 255, 255)')
  })

  test('file upload dropzone is present and accepts CSV/Excel', async ({ page }) => {
    await page.goto('/app/')
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    // The upload zone contains the instructional text
    const dropzone = page.getByText('Drop CSV or Excel file here')
    await expect(dropzone).toBeVisible()

    // The file input accepts the right extensions
    const fileInput = page.locator('input[type="file"]')
    await expect(fileInput).toHaveAttribute('accept', '.csv,.xlsx,.xls')
  })

  test('chat textarea and Ask button are present', async ({ page }) => {
    await page.goto('/app/')
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    const textarea = page.locator('textarea[placeholder="Ask a question about your data…"]')
    await expect(textarea).toBeVisible()

    const askBtn = page.locator('button', { hasText: 'Ask' })
    await expect(askBtn).toBeVisible()
    // Button is disabled when input is empty
    await expect(askBtn).toBeDisabled()
  })

  test('chat textarea enables the Ask button when text is typed', async ({ page }) => {
    await page.goto('/app/')
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    const textarea = page.locator('textarea[placeholder="Ask a question about your data…"]')
    await textarea.fill('What are the column names?')

    const askBtn = page.locator('button', { hasText: 'Ask' })
    await expect(askBtn).toBeEnabled()
  })

  test('session ID is shown in the header', async ({ page }) => {
    await page.goto('/app/')
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    // The session ID badge is shown as "Session xxxxxxxx…"
    const sessionBadge = page.locator('text=/Session [0-9a-f]/')
    await expect(sessionBadge).toBeVisible()
  })

  test('empty chat state shows the hint text', async ({ page }) => {
    await page.goto('/app/')
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    // Empty state hint text
    const hint = page.getByText('Upload a CSV or Excel file, then ask a question to get started.')
    await expect(hint).toBeVisible()
  })

  test('Phase 2 stubs are removed — Code it ran stub is not present', async ({ page }) => {
    await page.goto('/app/')
    await expect(page.locator('h1', { hasText: 'Data Analysis Agent' })).toBeVisible({ timeout: 15_000 })

    // Phase 2 stubs should be gone — real features replace them
    const stub = page.locator('text=Code it ran (Phase 2)')
    await expect(stub).not.toBeVisible()

    const tokenStub = page.locator('text=Token cost (Phase 2)')
    await expect(tokenStub).not.toBeVisible()

    const downloadStub = page.locator('text=Download CSV (Phase 2)')
    await expect(downloadStub).not.toBeVisible()
  })
})
