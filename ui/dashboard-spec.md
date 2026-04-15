# Dashboard Specification

## Product position

This dashboard should sit between an analyst terminal and a media-ready editorial tool.

It is not just a chart page. It should help answer two questions quickly:

1. **Where is positioning most extreme or changing fastest?**
2. **What actually changed this week that is worth talking about?**

## Top-level structure

### Header

Required elements:

- product title
- short subtitle
- market selector
- lookback selector: 52 / 104 / 156 weeks
- `Last updated` timestamp
- `As of Tuesday / released Friday` badge

Suggested title:

```text
COT-CTA Positioning Monitor
```

Suggested subtitle:

```text
Weekly positioning across FX, rates, equities, volatility and commodities.
```

## Main panels

### 1. KPI strip

Show 4 cards:

- primary net
- primary percentile
- primary 4W delta
- price 4W change

### 2. Crowd regime chart

Line chart of the primary net series over the selected lookback.

Overlay:

- latest value marker
- percentile badge
- optional rolling mean band

### 3. Signal narrative card

One concise paragraph generated from rules.

Goal: explain the latest setup in plain market language.

### 4. Watchlist ranking

Table or ranked cards.

Columns:

- rank
- market
- regime
- score
- percentile
- 4W delta
- price 4W
- takeaway

### 5. What changed this week?

Show 3–5 bullets for the selected market.

Optional secondary block:

- top 5 movers across all markets

### 6. Cross-cohort structure

Bar chart comparing latest primary, secondary and tertiary net positions.

### 7. Price vs positioning

Two-axis chart or aligned panels:

- price
- primary net or percentile pressure

### 8. Historical table

Columns:

- date
- primary long
- primary short
- primary net
- 4W delta
- secondary net
- open interest

## Regime color system

- Crowded Long -> green
- Crowded Short -> red
- Contrarian Long -> teal
- Contrarian Short -> orange
- Divergence -> purple
- Neutral -> gray

## Watchlist scoring intent

The watchlist is for **editorial priority**, not raw size.

That means the ranking should surface:

- fresh extremes
- regime flips
- divergence between cohorts
- price-position dislocations

## Interaction design

- changing the market updates all panels
- changing lookback updates percentile and chart context
- tooltips should define metrics in one sentence
- narrative panel should refresh instantly from derived JSON

## Mobile behavior

- controls stacked vertically
- watchlist becomes card list
- historical table scrolls horizontally
- KPI strip becomes 2x2 grid

## Copy style

The dashboard should sound:

- concise
- analytical
- publishable
- not academic

Prefer:

- "Fast money added to shorts"
- "Allocator positioning remains structurally long"
- "Divergence widened"

Avoid overlong explanations inside the main view.

## Future Phase 2 recommendation

Migrate the frontend to **React / Next.js static export**. That is the cleanest long-term path for maintainability and a more professional UX, while keeping GitHub Pages compatibility. A static client-side COT viewer approach is already proven by `proprietary/cftc-cot-viewer`. [Source](https://github.com/proprietary/cftc-cot-viewer)
