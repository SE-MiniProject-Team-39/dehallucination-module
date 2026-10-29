import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests', fullyParallel:false, workers:1, reporter:'list', timeout:30000,
  use:{baseURL:'http://127.0.0.1:8001',headless:true,...(process.env.DAM_BROWSER_CHANNEL?{channel:process.env.DAM_BROWSER_CHANNEL}:{})},
  webServer:{
    command:process.platform==='win32'?'..\\.venv\\Scripts\\python.exe -m uvicorn backend.dam.main:create_app --factory --host 127.0.0.1 --port 8001 --app-dir ..':'../.venv/bin/python -m uvicorn backend.dam.main:create_app --factory --host 127.0.0.1 --port 8001 --app-dir ..',
    url:'http://127.0.0.1:8001/health',reuseExistingServer:false,
    env:{DATABASE_URL:'sqlite:///./playwright-test.db',DAM_ADMIN_PASSWORD:'browser-test-password',DAM_REVIEWER_PASSWORD:'browser-reviewer-password',DAM_API_KEY:'browser-test-key',DAM_SESSION_SECRET:'browser-session-test-secret',DAM_LIVE_SOURCES:'false',DAM_SECURE_COOKIES:'false',DAM_LLM_URL:''}
  }
});
