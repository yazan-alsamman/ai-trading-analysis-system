# AI Trading Assistance — Round 5 Report

**Cinematic visual motion and immersive design**

| | |
| --- | --- |
| Date | 17 October 2026 |
| Scope | **Frontend only** (`web/`). No backend, API, database, auth service, payment or infrastructure change. |
| Branch | `e/web-client` (committed locally; not pushed) |
| Technical write-up | `web/docs/CINEMATIC_MOTION_IMPLEMENTATION.md` |
| Previous round | `WEBSITE_REPORT_ROUND4_MOTION_MEMBERSHIP.md` |

---

## 1. Summary

The public website now plays like a film, built from real material:

- **Real footage, licensed and self-hosted.** Six short loops (1.9 MB in total) of traders, screens and
  notes, from Coverr and Mixkit (Free licence). No photo is animated to fake motion, and nothing is
  hot-linked.
- **The product appears on screen as it really is.** The hero chart draws itself step by step. A
  **CSS-3D laptop** opens on scroll and shows the actual workspace UI. Every product number comes from the
  platform's own simulated fixtures, and each one says *Simulated*.
- **Eight distinct scenes:**
  - A: noise → order, in depth
  - the 3D workspace
  - B: modules with a travelling data packet
  - C: chart → structured research plan
  - D: risk gauge with cause → effect
  - E: violet AI-assistant scene
  - F: methodology with a self-drawing reliability diagram
  - G: plan cards that tilt into place
  - H: a cinematic close
- **Restraint where it matters:**
  - footage plays only on screen, pauses off-screen and in hidden tabs
  - posters only under reduced motion or Save-Data
  - phones fetch a single 155 KB clip
  - copy never sits on raw video
  - honest labels are unchanged: *Pricing to be announced*, *Rule-based demo*, *No verified live results exist yet*

---

## 2. What uses what

| Technique | Where |
| --- | --- |
| **Video** (licensed footage) | Hero; A (quote board); C header (hands at a laptop); E (screen reflected in glasses, graded violet); F (notes being written); H (trader in profile) |
| **CSS 3D** | The workspace laptop (lid, screen, deck, depth panels); scene A fragments arriving from different depths; plan cards tilting into place |
| **SVG drawing** | Hero chart (grid, axis, line, swing points, NOW pulse, levels, projection, ambient crosshair); exposure gauge; assistant evidence connectors; reliability diagram; the closing price line |
| **The app's own components** | Laptop screen, hero cards, research-plan card, signal checks, assistant reply (actual rule-based output), risk numbers (`computeTradeRisk`) |

---

## 3. Footage and licences

| Clip | Source | Licence | Size |
| --- | --- | --- | --- |
| Trader at a desk, monitor and laptop (hero) | Coverr, "A broker works with a cryptocurrency candlestick chart" | Coverr licence: free commercial use, no attribution required | 469 KB (+155 KB phone rendition) |
| Out-of-focus quote board (A) | Coverr, "A screen showing financial analysis of a cryptocurrency" | Coverr | 168 KB |
| Hands at a laptop chart (C) | Coverr, "A businessman working on a stock market trading platform" | Coverr | 296 KB |
| Screen reflected in glasses (E) | Mixkit #221, "Reflection of a screen in glasses" | Mixkit Stock Video **Free** License | 178 KB |
| Hand writing notes (F) | Coverr, "A trader writing analytical data in a notebook" | Coverr | 238 KB |
| Trader in profile (H) | Coverr, "A man analyzing the stock market" | Coverr | 344 KB |

- Mixkit clips under the **Restricted** licence (no commercial or advertising use) were rejected.
- Pexels and Pixabay were unreachable (HTTP 403) and were not used.
- The processing is reproducible with `web/scripts/build-media.sh`.
- A credit line is in the site footer, although neither licence requires one.

---

## 4. Verification

| Check | Result |
| --- | --- |
| Type check | ✅ 0 errors |
| Lint | ✅ 0 errors, 0 warnings |
| Unit / component tests | ✅ **142 / 142** in 15 files (was 128). New: `marketing/cinematic.test.tsx` (14) |
| Production build | ✅ Main chunk 107.7 KB gzip (was 100), CSS 19.3 KB (was 17); video is not bundled (served from `/media/`) |
| Playwright | ⚠️ **Incomplete.** The run was stopped by Claude Code because the machine ran low on memory. Before that, 63 tests ran and **60 passed**:

| Spec | Result |
| --- | --- |
| axe | 31 / 31 |
| round 5 (new) | 9 / 9 |
| round 4 (updated) | 6 / 6 |
| visual matrix | 4 of its 10 runs (the rest never ran) |
| app flows | 8 / 10 |
| round 3 | 6 / 7 |

**3 failed**, all in app routes this round did not touch (`/workspace` ×1, `/signals` ×1, round-3 personalised signals ×1). Their durations match the `settle()` timeouts under memory pressure, but the failure details were never printed, so this is unconfirmed. **Re-run `pnpm e2e` on a machine with free memory.** |

**Browser QA (local Chrome, scripted).** Screenshots are in `screenshots/round5/`. Covered:

- hero at 0.4 / 1.6 / 3.4 / 6.5 s
- every scene at several scroll points
- dark and light themes
- 1440 × 900, 834 × 1112 and 390 × 844
- reduced motion
- per-video play/pause state, media requests, console and network errors
- horizontal overflow sampled every 450 px down the page

**Defects found by that QA and fixed:**

| Defect | Fix |
| --- | --- |
| 552 px horizontal overflow mid-page: the finished data-packet track stayed translated past the connector | Connector strip clipped (`overflow-hidden`) |
| Hero crosshair started before the intro had finished (dev StrictMode re-ran the effect) | The "started" flag is set only when the first step fires |
| Light theme: the dark footage sat under the transparent header, making the navigation illegible; the dissolve also reached under the copy | Footage masked clear under the header (both themes); light theme dissolve starts later |
| Tablet: hero footage hidden behind the single-column copy | Phones and tablets (< 64 rem) use a footage band above the copy |
| 3D laptop too tall for 900 px viewports; closed lid almost invisible | Size bound to viewport height; closed pose seen from above and raised; lit cover with a gold mark |
| Risk cause → effect chain wrapped awkwardly | Label above value |

**After the fixes:** 0 overflow at every width, 0 console or network errors. Every clip plays only on
screen and pauses off-screen. Reduced motion and phones behave as specified (posters only, or the single
small clip).

---

## 5. Performance and compatibility

- Total video 1.9 MB. A desktop visitor loads clips only as they near the viewport (`preload="none"`).
  A phone loads one 155 KB clip. Reduced motion and Save-Data load **no** video.
- Grades are baked into the files: no runtime video filters and no `backdrop-filter` over playing video.
  Scroll work stays on the single shared animation-frame loop. No new dependency, no WebGL.
- Verified in Chrome only. Masks, 3D and view transitions are not checked in Safari or Firefox. Autoplay
  refusal (iOS Low Power Mode) falls back to the poster; this is unit-tested, not checked on a device.

## 6. Remaining work

1. Safari, Firefox and physical-device testing (autoplay, battery, 3D text sharpness).
2. Optional AV1/WebM renditions (≈ 30–40 % smaller).
3. Commissioned footage of the real product in use, when available.
4. Real, labelled model output through the API once Feature 12 is exposed; the scenes are data-driven.

---

### Follow-up (round 6, 17 October 2026)

The full Playwright suite has since passed (89 / 89, run in chunks). The three failures above were
**not** caused by memory pressure. The demo market follows real FX hours, and the run happened on a
Saturday, so three older tests that assumed an open market failed. They now pin the clock to a
weekday. See `WEBSITE_REPORT_ROUND6_ABOUT_ASSISTANT_FOOTER.md` §4.
