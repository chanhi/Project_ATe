import { defineConfig } from '@playwright/test';

/**
 * ATe 워커 안에서 사용하는 Playwright 설정
 * 각 Task가 임시 디렉토리에 spec 파일을 생성하고
 * `npx playwright test --config <이파일>` 으로 실행한다.
 */
export default defineConfig({
  testDir: './specs',
  timeout: 30_000,
  expect: { timeout: 5_000 },

  fullyParallel: false,
  workers: 1,

  reporter: [
    ['list'],
    ['json', { outputFile: 'results.json' }],
  ],

  use: {
    actionTimeout: 10_000,
    navigationTimeout: 10_000,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'off',
  },

  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
