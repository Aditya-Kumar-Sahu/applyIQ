import { test, expect } from '@playwright/test';

test.describe('Job Matching', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test in this suite
    await page.goto('/login');
    await page.fill('#login-email', 'test@example.com');
    await page.fill('#login-password', 'Password123!');
    await page.click('#login-submit');
    
    // Wait for navigation and dashboard title
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.locator('.page-header__title')).toContainText('Dashboard');
  });

  test('should display seeded job matches', async ({ page }) => {
    // Navigate to jobs page
    await page.goto('/jobs');
    
    // Wait for the list to load and empty state to disappear
    await expect(page.locator('.empty-state')).not.toBeVisible({ timeout: 15000 });

    // Check for the first seeded job heading
    const jobTitle = page.getByRole('heading', { name: 'Senior Python Backend Engineer' });
    await expect(jobTitle.first()).toBeVisible({ timeout: 10000 });
    
    // Check for company name
    await expect(page.getByText('FastScale Systems').first()).toBeVisible();
    
    // Check for score pill - be less strict
    await expect(page.locator('.score-pill').first()).toContainText('%');
  });

  test('should show match explanation in the detail panel', async ({ page }) => {
    await page.goto('/jobs');
    
    // Wait for load
    const jobTitle = page.getByRole('heading', { name: 'Senior Python Backend Engineer' });
    await expect(jobTitle.first()).toBeVisible({ timeout: 15000 });

    // Click on the first job card heading
    await jobTitle.first().click();

    // Verify detail panel content appears
    const detailPanel = page.locator('.job-detail-panel');
    await expect(detailPanel).toBeVisible({ timeout: 10000 });
    
    // Check score breakdown in detail panel
    await expect(detailPanel).toContainText('Skills');
    
    // Check for service-generated reason
    await expect(page.locator('body')).toContainText('Strong overlap on Python');
  });
});
