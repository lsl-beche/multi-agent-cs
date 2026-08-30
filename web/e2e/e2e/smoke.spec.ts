import { expect, test } from '@playwright/test'

test('shop home page renders', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('#app')).toBeVisible()
  await expect(page.getByText(/茗韵|茶叶|茶/).first()).toBeVisible()
})

