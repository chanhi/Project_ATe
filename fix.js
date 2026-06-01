db.getSiblingDB('ate_db').test_cases.updateOne(
  { test_case_id: 'tc-f91b9cc3' },
  { $set: { playwright_code: `import { test, expect } from '@playwright/test';

test('Add first item to cart', async ({ page }) => {
  await page.goto('https://www.saucedemo.com');
  await page.fill('[data-test="username"]', 'standard_user');
  await page.fill('[data-test="password"]', 'secret_sauce');
  await page.click('[data-test="login-button"]');
  await page.waitForSelector('.inventory_item');
  await page.locator('.inventory_item button').first().click();
  await expect(page.locator('.shopping_cart_badge')).toBeVisible();
});` } }
);
