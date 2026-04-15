# Step-by-Step Implementation Plan

## Goal

Build a highly useful **COT-CTA positioning dashboard** that can be published on GitHub, refreshed automatically every week, and expanded later into a more professional React/Next.js product.

This implementation plan assumes:

- free public CFTC data
- GitHub-hosted source control
- GitHub Actions automation
- GitHub Pages publishing
- a first version built on static JSON + static frontend

## Step 1 — Create the repository

Create a GitHub repository such as:

```text
cot-cta-positioning-dashboard
```

Initial folders:

```text
.github/workflows/
scripts/
docs/
data/
ui/
```

Add the files from this package first. Then copy your existing dashboard file into the repo as the first frontend shell.

## Step 2 — Lock the data contract

Use a two-layer output model.

### Raw/normalized market files

Each market file should contain:

- market metadata
- normalized weekly COT rows
- aligned price series when available

Example destination:

```text
data/markets/eurfx.json
data/markets/us10y.json
data/markets/gold.json
```

### Derived files

These should be generated after fetch/normalization:

```text
data/derived/watchlist.json
data/derived/weekly_changes.json
data/derived/narratives.json
```

This keeps the frontend fast and simple.

## Step 3 — Ingest free CFTC APIs

### Financial futures

Use the TFF API endpoint:

- https://publicreporting.cftc.gov/resource/gpe5-46if.json [Source](https://publicreporting.cftc.gov/resource/gpe5-46if.json)

This endpoint is appropriate for markets such as:

- S&P 500
- Nasdaq
- US 10Y
- VIX
- EUR FX
- GBP FX
- DXY
- Bitcoin futures

Useful fields include market name, report date, open interest, dealer positions, asset manager positions and leveraged money positions. [Source](https://publicreporting.cftc.gov/resource/gpe5-46if.json)

### Commodities

Use the Disaggregated endpoint already referenced in the existing script architecture for markets such as:

- gold
- WTI crude
- corn

### Interpretation note

The CFTC notes that Traders in Financial Futures and Disaggregated reports are separate report families with different trader category structures, so the dashboard should map cohorts by family rather than force one identical taxonomy across all markets. [Source](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)

## Step 4 — Build derived intelligence

Create a second script, `derive_metrics.py`, to compute the dashboard's editorial features.

### 4A. Watchlist ranking

For each market, calculate:

- primary net position
- primary percentile over rolling history
- primary z-score
- 4-week net delta
- price 4-week change
- divergence versus secondary cohort
- open-interest confirmation
- regime label

Suggested ranking objective:

```text
interestingness > size
```

That means a divergence setup should often outrank a market that is merely large.

### 4B. What changed this week?

For each market, compare the latest week versus the prior week and produce short, readable bullets such as:

- largest shift in fast money positioning
- biggest percentile move
- regime flip
- widening divergence between cohorts
- price confirmation or failure

### 4C. Weekly narrative

Generate one short paragraph per market from deterministic rules.

Template:

```text
[Market] remains in a [regime] setup. Primary positioning is at the [X]th percentile over the last [lookback] weeks. Over the last 4 weeks, net positioning [rose/fell] by [N] contracts. [Secondary cohort] is [confirming/diverging]. Price is [up/down] [P]% over the same window.
```

## Step 5 — Use the existing dashboard as the first frontend

Do not wait for a perfect React build.

In the first publishable version, use your current static dashboard file and connect it to:

- `data/manifest.json`
- `data/markets/*.json`
- `data/derived/watchlist.json`
- `data/derived/weekly_changes.json`
- `data/derived/narratives.json`

## Step 6 — Add the new panels requested

### Watchlist panel

Display:

- market
- regime badge
- watchlist score
- percentile
- 4W delta
- 4W price change
- one-line takeaway

### What changed this week? panel

Display:

- latest report date
- top 3–5 bullet updates for selected market
- optional cross-market highlights box

## Step 7 — Improve the UI/UX

The first redesign should focus on hierarchy, not visual gimmicks.

Recommended layout:

1. Header with market selector, lookback selector, report date, refresh badge
2. KPI strip
3. Main net/regime chart
4. Signal narrative card
5. Watchlist ranking card
6. Weekly changes card
7. Position structure and price-vs-positioning row
8. Historical table and methodology drawer

### Design principles

- shorter copy
- stronger contrast between headline and metadata
- clear regime color system
- sticky controls on desktop
- mobile-first card stacking
- sparklines inside the watchlist when possible

## Step 8 — Automate weekly refresh

The CFTC states that reports are generally published Friday at 3:30 p.m. ET using Tuesday positions, so the workflow should run after the release window. [Source](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)

Workflow sequence:

1. install Python
2. install dependencies
3. run `scripts/fetch_cot.py`
4. run `scripts/derive_metrics.py`
5. validate output
6. commit updated data if changed

## Step 9 — Publish on GitHub Pages

For the MVP, publish the static dashboard directly.

Then in Phase 2, migrate the UI to **Next.js static export**, preserving the same data contract. This follows the proven static-site philosophy of `proprietary/cftc-cot-viewer`. [Source](https://github.com/proprietary/cftc-cot-viewer)

## Step 10 — Acceptance checklist

The MVP is good enough to publish when all of the following are true:

- repo is public and documented
- data refresh runs without manual intervention
- latest Friday release updates the JSON files
- dashboard shows `Last updated` and `As of Tuesday`
- watchlist ranking is visible
- weekly changes panel is visible
- methodology page explains cohort proxies
- GitHub Pages build is live

## Suggested immediate sequence

### This week

- upload package
- add existing dashboard HTML
- run workflow manually
- inspect generated JSON
- publish first GitHub Pages build

### Next week

- refine ranking weights
- improve copy and badges
- add better visual states for divergence
- begin Next.js migration
