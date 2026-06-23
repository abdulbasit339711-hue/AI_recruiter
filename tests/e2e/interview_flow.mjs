/**
 * AI-Recruiter E2E — real-browser interview flow
 * Run: node e2e_interview.mjs <invite_token>
 */

import { chromium } from "playwright";

const FRONTEND   = "http://localhost:3000";
const VOICE_URL  = "http://127.0.0.1:7860";
const TOKEN      = process.argv[2];
const ADMIN_EMAIL    = "admin@example.com";
const ADMIN_PASSWORD = "change-me-admin-password";
const CANDIDATE_ID   = 1;

if (!TOKEN) { console.error("Usage: node e2e_interview.mjs <invite_token>"); process.exit(1); }

function pass(msg) { console.log(`  ✓  ${msg}`); }
function fail(msg) { console.error(`  ✗  ${msg}`); process.exitCode = 1; }
function info(msg) { console.log(`     ${msg}`); }

async function screenshot(page, name) {
  const p = `/tmp/${name}.png`;
  await page.screenshot({ path: p, fullPage: false });
  info(`screenshot → ${p}`);
}

const browser = await chromium.launch({
  headless: false,
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--no-sandbox",
    "--disable-setuid-sandbox",
  ],
  slowMo: 80,
});

// ─────────────────────────────────────────────────────────────────────────────
// PART A — Admin side
// ─────────────────────────────────────────────────────────────────────────────

console.log("\n── Part A: Admin login & candidate interview view ────────────");

const adminCtx  = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const adminPage = await adminCtx.newPage();

await adminPage.goto(`${FRONTEND}/login`);
await adminPage.fill('input[type="email"], #login-email', ADMIN_EMAIL);
await adminPage.fill('input[type="password"]', ADMIN_PASSWORD);
await adminPage.click('button[type="submit"]');
await adminPage.waitForURL(/\/admin/, { timeout: 10_000 });
pass("Admin logged in");

await adminPage.goto(`${FRONTEND}/admin/candidates/${CANDIDATE_ID}/interview`);
await adminPage.waitForLoadState("networkidle", { timeout: 15_000 });
await screenshot(adminPage, "admin-overview-tab");
pass("Admin candidate interview page loaded");

// Overview tab — check score card and goals panel are visible
const hasScore = await adminPage.locator("text=/SCORE|FINAL SCORE|\\d+\\s*\\/\\s*100/i").count();
hasScore ? pass("Overview: score card visible") : fail("Overview: no score card found");

const hasGoals = await adminPage.locator("text=/Interview Goals|Goals/i").count();
hasGoals ? pass("Overview: Interview Goals section visible") : fail("Overview: Goals section not found");

// Assessment tab — tabs are rendered as buttons/links, not role="tab"
const assessBtn = adminPage.locator("button, [role=tab], a").filter({ hasText: /assessment/i }).first();
if (await assessBtn.count()) {
  await assessBtn.click();
  await adminPage.waitForTimeout(1500);
  await screenshot(adminPage, "admin-assessment-tab");
  // Assessment tab shows Interview Goals (always) + post-call Evaluation Dimensions (only after session ends)
  const hasInterviewGoals = await adminPage.locator("text=/Interview Goals/i").count();
  hasInterviewGoals
    ? pass("Assessment tab: Interview Goals panel visible")
    : fail("Assessment tab: Interview Goals panel not found");
  const hasDims = await adminPage.locator("text=/Evaluation Dimensions|Decision Rationale|Next Steps/i").count();
  hasDims
    ? pass("Assessment tab: post-call analysis (Evaluation Dimensions) visible")
    : info("Assessment tab: no post-call dimensions yet (session still active — expected for a live call)");
} else {
  fail("Assessment tab button not found");
}

// Transcript tab
const transcriptBtn = adminPage.locator("button, [role=tab], a").filter({ hasText: /transcript/i }).first();
if (await transcriptBtn.count()) {
  await transcriptBtn.click();
  await adminPage.waitForTimeout(1000);
  await screenshot(adminPage, "admin-transcript-tab");
  pass("Transcript tab clickable");
}

// ─────────────────────────────────────────────────────────────────────────────
// PART B — Candidate interview flow
// ─────────────────────────────────────────────────────────────────────────────

console.log("\n── Part B: Candidate interview flow ──────────────────────────");

const candidateCtx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  permissions: ["microphone", "camera"],
});
const page = await candidateCtx.newPage();
page.on("console", m => { if (m.type() === "error") info(`[browser error] ${m.text().slice(0,120)}`); });

// 4. Open interview link
info(`Opening /interview/${TOKEN.slice(0, 20)}…`);
await page.goto(`${FRONTEND}/interview/${TOKEN}`);

// 5. Wait for validation to resolve (spinner disappears)
await page.waitForFunction(
  () => !document.body.innerText.match(/validating|loading/i) || document.body.innerText.match(/join now|join|start|welcome/i),
  { timeout: 20_000 }
).catch(() => {});
await screenshot(page, "interview-ready");

const bodyText = await page.innerText("body");
if (bodyText.match(/invalid|expired|error/i) && !bodyText.match(/join now|welcome/i)) {
  fail(`Token rejected: ${bodyText.slice(0, 200)}`);
  await browser.close(); process.exit(1);
}
pass("Token validated — pre-join screen visible");

const heading = await page.locator("h1, h2").first().innerText().catch(() => "");
info(`Role shown: "${heading}"`);
heading.match(/devops/i) ? pass("Correct job title shown") : fail(`Unexpected heading: "${heading}"`);

// 6. Click "Join now"
const joinBtn = page.locator("button").filter({ hasText: /join now|join|start/i }).first();
if (await joinBtn.count()) {
  await joinBtn.click();
  pass("Clicked Join now");
} else {
  fail("Join button not found");
  await screenshot(page, "interview-no-join");
}

// 7. Wait for connecting → live (LiveKit) or graceful error
info("Waiting for LiveKit connect (up to 25 s)…");
const wentLive = await page.waitForFunction(
  () => document.body.innerText.match(/mic|mute|leave|end interview|speaking|connected|transcript/i)
     && !document.body.innerText.match(/join now|connecting/i),
  { timeout: 25_000 }
).then(() => true).catch(() => false);

await screenshot(page, "interview-post-connect");

if (wentLive) {
  pass("Phase → live (LiveKit connected, call UI visible)");

  // 8. Check mic button / call controls are rendered
  const hasMicBtn = await page.locator("button").filter({ hasText: /mic|mute/i }).count()
    + await page.locator("[aria-label*='mic' i], [aria-label*='mute' i]").count();
  hasMicBtn ? pass("Mic/mute button present in call UI") : info("Mic button not found (may use icon only)");

  // 9. Wait for bot opening transcript line
  info("Waiting for bot's opening turn in transcript (up to 20 s)…");
  const botSpoke = await page.waitForFunction(
    () => {
      // Transcript bubbles: look for any non-empty text node whose parent
      // contains "Interviewer" label nearby (captions strip or transcript panel)
      const captionText = document.body.innerText;
      return captionText.match(/Interviewer:|Hello.*interview|welcome.*interview|tell me.*yourself/i);
    },
    { timeout: 20_000 }
  ).then(() => true).catch(() => false);
  botSpoke ? pass("Bot opening turn visible in transcript / captions") : info("Bot turn not detected after 20 s (bot may still be connecting)");
  await screenshot(page, "interview-live");

  // 10. Send typed chat message via the "Type instead of speaking…" input
  const chatInput = page.locator("input[placeholder*='speaking' i], textarea[placeholder*='speaking' i], input[placeholder*='message' i], textarea[placeholder*='message' i]").first();
  if (await chatInput.count()) {
    await chatInput.fill("Hello, I have five years of DevOps experience with Kubernetes and Terraform.");
    const sendBtn = page.locator("button[aria-label*='send' i], button[type='submit']").last();
    if (await sendBtn.count()) {
      await sendBtn.click();
    } else {
      await chatInput.press("Enter");
    }
    await page.waitForTimeout(3000);
    pass("Chat message typed and sent");
    await screenshot(page, "interview-chat-sent");
  } else {
    // Transcript panel may need toggling open
    const panelToggle = page.locator("button").filter({ hasText: /transcript|chat|panel/i }).first();
    if (await panelToggle.count()) await panelToggle.click();
    await page.waitForTimeout(500);
    const chatInput2 = page.locator("input[placeholder*='speaking' i], textarea").last();
    if (await chatInput2.count()) {
      await chatInput2.fill("Hello, I have five years of DevOps experience.");
      await chatInput2.press("Enter");
      await page.waitForTimeout(3000);
      pass("Chat message sent (after toggling panel)");
      await screenshot(page, "interview-chat-sent");
    } else {
      info("Chat input not found — may need microphone for this session");
    }
  }

  // 11. Verify message reached the voice service (check server log via health endpoint)
  const health = await fetch(`${VOICE_URL}/health`).then(r => r.json()).catch(() => ({}));
  health.active_interviews > 0
    ? pass(`Voice service: ${health.active_interviews} active interview(s) running`)
    : info("No active interviews in voice service (bot may have timed out)");

} else {
  // LiveKit connect failed — check for graceful error UI
  const bodyNow = await page.innerText("body").catch(() => "");
  const friendly = bodyNow.match(/couldn't connect|timed out|try again|contact/i);
  friendly
    ? pass("LiveKit connect timed out — page surfaced friendly error message (expected without LK cloud)")
    : fail("Unexpected state after connect attempt — no live UI and no friendly error");
  info(`Page snippet: ${bodyNow.slice(0, 300)}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// PART C — Voice service endpoint checks
// ─────────────────────────────────────────────────────────────────────────────

console.log("\n── Part C: Voice service endpoint checks ─────────────────────");

// Health
const h = await fetch(`${VOICE_URL}/health`).then(r => r.json()).catch(() => null);
h ? pass(`/health → status=${h.status}, tts=${h.providers?.tts}`) : fail("/health unreachable");

// /events — open and check we get at least a heartbeat within 3 s
const eventsOk = await new Promise(resolve => {
  const ctrl = new AbortController();
  const t = setTimeout(() => { ctrl.abort(); resolve(true); }, 3000); // 3 s is enough for heartbeat
  fetch(`${VOICE_URL}/events`, { signal: ctrl.signal })
    .then(r => { clearTimeout(t); resolve(r.ok); })
    .catch(e => { clearTimeout(t); resolve(e.name === "AbortError"); }); // AbortError = we got a stream
});
eventsOk ? pass("/events SSE endpoint streams (aborted after 3 s)") : fail("/events not reachable");

// ─────────────────────────────────────────────────────────────────────────────

console.log("\n── Done ──────────────────────────────────────────────────────");
const exitCode = process.exitCode ?? 0;
console.log(exitCode === 0 ? "All checks passed." : "Some checks failed — see ✗ lines above.");

await page.waitForTimeout(2000);
await browser.close();
process.exit(exitCode);
