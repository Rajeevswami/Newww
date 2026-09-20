import { test, expect } from '@playwright/test';

test('recruiter can filter candidates, review a scorecard, create and close a job', async ({ page }) => {
  const jobTitle = 'E2E Quality Engineer ' + Date.now();
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Good morning, Alex/ })).toBeVisible();
  await page.getByRole('button', { name: 'View all candidates' }).click();
  await page.getByPlaceholder('Search by name, email, or role…').fill('Emily Davis');
  await expect(page.getByRole('button', { name: 'Emily Davis', exact: true })).toHaveCount(3);
  await page.getByRole('button', { name: 'Emily Davis', exact: true }).first().click();
  await expect(page.getByRole('dialog', { name: 'Candidate profile' })).toBeVisible();
  await page.getByRole('button', { name: 'Shortlist candidate', exact: true }).click();
  await expect(page.getByLabel('Change candidate status')).toHaveValue('Shortlisted');
  await page.getByLabel('Change candidate status').selectOption('New');
  await expect(page.getByRole('button', { name: 'Shortlist candidate', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: /Get the full conversation/ }).click();
  await expect(page.getByRole('heading', { name: 'What went well' })).toBeVisible();
  await page.getByRole('button', { name: 'Conversation', exact: true }).click();
  await expect(page.getByText('How did you decide which problems to prioritize?')).toBeVisible();
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.locator('.main-nav').getByRole('button', { name: /^Jobs/ }).click();
  await page.getByRole('button', { name: 'Post a job', exact: true }).click();
  await page.getByLabel('Job title').fill(jobTitle);
  await page.getByLabel('Required skills').fill('Python, SQL');
  await page
    .getByLabel('Job description')
    .fill(
      'Help our product team build reliable applications, improve our automated test coverage, and support thoughtful releases.',
    );
  await page.getByRole('button', { name: 'Publish job' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByPlaceholder('Search job title or skill…').fill(jobTitle);
  await page.getByRole('button', { name: new RegExp(jobTitle) }).click();
  await expect(page.getByRole('dialog').getByRole('heading', { name: jobTitle })).toBeVisible();
  await page.getByRole('button', { name: 'Close job', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm close job' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'No roles found' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('candidate can complete an adaptive practice interview', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Good morning, Alex/ })).toBeVisible();
  await page.locator('.sidebar-profile').click();
  await page.getByRole('button', { name: 'Try candidate view' }).click();
  await expect(page.getByRole('heading', { name: 'Your next chapter, Sarah.' })).toBeVisible();
  await page.getByRole('button', { name: 'Practice interview', exact: true }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  for (let question = 1; question <= 5; question++) {
    await expect(page.getByText(`Question ${question} of 5`, { exact: true })).toBeVisible();
    await page
      .getByLabel('Your answer')
      .fill(
        'I worked closely with customers and engineering to understand the problem. We gathered evidence from interviews, compared three solutions, tested our hypothesis, and delivered a prototype. The project improved completion rates by twenty percent and taught our team the value of testing assumptions early.',
      );
    await page.getByRole('button', { name: 'Send answer' }).click();
  }
  await expect(page.getByRole('heading', { name: 'What went well' })).toBeVisible();
  await expect(page.getByText('Practice again, then request human review', { exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download feedback' }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('smarthire-feedback.json');
});

test('mobile navigation, search and layout work without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Good morning, Alex/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.locator('.main-nav').getByRole('button', { name: 'Analytics', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'See the bigger picture.' })).toBeVisible();
  await page.getByRole('button', { name: 'Search workspace' }).click();
  await page.getByPlaceholder('What are you looking for?').fill('Frontend');
  await page.getByRole('button', { name: /Frontend Developer/ }).click();
  await expect(page.getByRole('heading', { name: 'Frontend Developer', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close dialog' }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('sign out refreshes an expired access token and stays signed out after reload', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Good morning, Alex/ })).toBeVisible();
  let calls = 0;
  await page.route('**/api/auth/logout', async (route) => {
    calls++;
    if (calls === 1) {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Access token expired' }),
      });
    } else {
      await route.continue();
    }
  });
  await page.locator('.sidebar-profile').click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Good to have you back.' })).toBeVisible();
  expect(calls).toBe(2);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Good to have you back.' })).toBeVisible();
  await page.getByLabel('Email address').fill('alex@acme.design');
  await page.getByLabel('Password', { exact: true }).fill('DemoPass2026!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Good morning, Alex/ })).toBeVisible();
});
