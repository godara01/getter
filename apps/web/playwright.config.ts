import { defineConfig } from "@playwright/test";

// Runs the real API (offline dev models, throwaway SQLite database) and the
// static site, then drives a full practice interview in a browser.
const apiDir = "../../services/api";

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure" },
  webServer: [
    {
      command:
        "rm -f e2e.db && uv run alembic upgrade head && uv run uvicorn getter_api.main:create_app --factory --port 8100",
      cwd: apiDir,
      url: "http://localhost:8100/health",
      env: {
        GETTER_DATABASE_URL: "sqlite+aiosqlite:///./e2e.db",
        GETTER_CORS_ORIGINS: '["http://localhost:3100"]',
        GETTER_FREE_SESSIONS_PER_DAY: "100",
      },
      reuseExistingServer: false,
    },
    {
      command: "pnpm exec http-server out -p 3100 -s",
      url: "http://localhost:3100",
      reuseExistingServer: false,
    },
  ],
});
