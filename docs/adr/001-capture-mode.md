# ADR-001: Capture mode — Chrome MV3 extension + official vendor exports

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead |
| **Tags** | capture, legal, security |

## Context and Problem Statement

Phase 1 must capture a user's ChatGPT and Claude history. Two broad mechanisms exist:

1. **Scrape** the vendor's web UI (or use undocumented HTTP endpoints) directly.
2. **Ingest** the user's own data via the vendor's official export feature.

Scraping is faster to ship and works for any account state, but is a legal/ethical minefield (vendor ToS), brittle (DOM changes break it), and creates an attack surface (the scraper runs against authenticated sessions).

## Decision Drivers

- Legal/ethical posture (proposal-v2 §1, market-research §6 *Plurality positioning critique*).
- Stability: vendors break scrapers quarterly.
- Threat model §4: avoid expanding the extension's permission set.
- Phase-1 ships only what the user can already do legally.

## Considered Options

1. **Headless scraping inside the extension** — Operate against the user's logged-in session.
2. **Official chat-export ingestion** — Drop a `conversations.json` (ChatGPT) or `.json` (Claude) export into the extension/CLI.
3. **Hybrid** — official export by default; optional opt-in scraper for power users.

## Decision Outcome

**Chosen: Option 2 — official chat-export ingestion only.**

### Consequences

- ✅ Eliminates ToS exposure: the user is downloading their own data via the vendor's sanctioned export.
- ✅ Extension permissions stay minimal (`nativeMessaging`, `storage`); no `host_permissions`, no content scripts.
- ✅ Stable to vendor UI changes.
- ⚠️ User must trigger the export themselves — slower onboarding than scraping.
- ❌ Cannot capture data the vendor doesn't include in the export (e.g., custom GPT chats only available through the UI).

## Pros and Cons of the Options

### Option 1 — Scraping
- ✅ Works for any account state, no user action beyond install.
- ❌ ToS violations; breaks on DOM changes; runs against authenticated session — security risk.

### Option 2 — Official export (chosen)
- ✅ Legal, stable, minimal permissions.
- ❌ Adds a manual "request export → wait → drop file" step.

### Option 3 — Hybrid
- ✅ Best of both for power users.
- ❌ Doubles the surface area; still keeps the ToS risk; complicates the threat model.

## More Information

- SRS §F-1, F-2 — capture features.
- SDD §2.1, §2.2 — extension permissions and ingestion pipeline.
- threat model §4.1 — supply-chain implications of the extension.
- Next review: when a vendor publishes a sanctioned memory-export API.
