import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should allow a user to login with valid credentials', async ({ page }) => {
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));

    // Go to login page
    await page.goto('/login');

    // Fill credentials
    await page.fill('#login-email', 'test@example.com');
    await page.fill('#login-password', 'Password123!');

    // Click sign in
    await page.click('#login-submit');

    // Should be redirected to dashboard
    await expect(page).toHaveURL(/\/dashboard/);
    
    // Verify dashboard content
    await expect(page.locator('.page-header__title')).toContainText('Dashboard');
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#login-email', 'wrong@example.com');
    await page.fill('#login-password', 'WrongPass123!');
    await page.click('#login-submit');

    // Error message should appear
    await expect(page.locator('.auth-error')).toBeVisible();
  });
});
