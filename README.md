> ⚠️ **DEPRECATED — 2026-06-18 (INIT-22).** Този дашборд се извежда от употреба.
> CTA тренд слоят (trigger нивата) е сгънат в **cot-monitor** (таб „CTA тренд");
> `macro-satellite` вече не чете това repo. Седмичното обновяване е спряно (само ръчно).
> Доларовите оценки и „CTA-vs-CFTC Gap" не се пренасят — бяха подвеждащи (виж INIT-22 одита).
> Не добавяй ново тук — ползвай cot-monitor.

# COT-CTA Positioning Dashboard — Minimum Viable GitHub Package

This package is a practical starter repo for publishing a **weekly COT/CTA-style positioning dashboard** on GitHub.

It is designed around three principles:

1. **Free public data** from the CFTC Public Reporting API.
2. **Static hosting** so the project can run on GitHub Pages with minimal maintenance.
3. **Editorial usefulness** so the dashboard is not just a chart collection, but also produces a watchlist and a weekly "What changed this week?" summary.

The package reflects the most useful parts of two open-source references:

- The idea of a **static, client-side COT viewer** from `proprietary/cftc-cot-viewer`. [Source](https://github.com/proprietary/cftc-cot-viewer)
- The emphasis on **rolling statistics, z-scores, summary tables and automated ingestion** from `kustex/CFTC-COT-Report`. [Source](https://github.com/kustex/CFTC-COT-Report)

It also follows the CFTC publication cadence: COT data is **generally published every Friday at 3:30 p.m. ET** and reflects positions **as of the preceding Tuesday**. [Source](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)

---

## Included in this package

```text
cot-cta-mvp-package/
  README.md
  requirements.txt
  docs/
    implementation-plan.md
    methodology.md
    github-pages-setup.md
  scripts/
    fetch_cot.py
    derive_metrics.py
  data/
    manifest.example.json
  ui/
    dashboard-spec.md
  .github/
    workflows/
      weekly-refresh.yml
  .gitignore
```

---

## What this package gives you now

This is a **minimum viable repo package**, not a full final app.

It gives you:

- a clean repo structure
- a working Python ingestion script for CFTC JSON endpoints
- a derived metrics script for watchlist ranking and weekly-change summaries
- a weekly GitHub Action refresh workflow
- documentation for methodology and implementation
- a dashboard specification you can hand to a developer or use yourself

It does **not** include a full React/Next.js frontend build yet. That is the correct **Phase 2** step after the repo is published and the data pipeline is stable.

---

## Recommended setup path

### Phase 1 — Publish fast

1. Create a new GitHub repo.
2. Upload the files from this package.
3. Add your existing `cot-positioning-dashboard.html` as the initial frontend.
4. Adjust `scripts/fetch_cot.py` market mappings if needed.
5. Run the workflow manually once.
6. Confirm that `data/manifest.json` and `data/derived/*.json` are being produced.
7. Enable GitHub Pages.

### Phase 2 — Upgrade UI

Once the data layer is stable, migrate the dashboard UI to **React / Next.js static export** while keeping the same `data/*.json` contract.

That approach matches the static architecture philosophy used by `proprietary/cftc-cot-viewer`. [Source](https://github.com/proprietary/cftc-cot-viewer)

---

## Data sources used in the scripts

### Financial futures / macro markets
- CFTC TFF JSON API: https://publicreporting.cftc.gov/resource/gpe5-46if.json [Source](https://publicreporting.cftc.gov/resource/gpe5-46if.json)

Useful fields include:
- `market_and_exchange_names`
- `report_date_as_yyyy_mm_dd`
- `open_interest_all`
- `asset_mgr_positions_long`
- `asset_mgr_positions_short`
- `lev_money_positions_long`
- `lev_money_positions_short`
- `dealer_positions_long_all`
- `dealer_positions_short_all` [Source](https://publicreporting.cftc.gov/resource/gpe5-46if.json)

### Commodity / disaggregated markets
- CFTC Disaggregated JSON API: `kh3c-gbw2.json` (the package uses this endpoint in the script because it is appropriate for commodities such as gold, WTI and corn).

### Legacy reference
- Legacy COT example endpoint: https://publicreporting.cftc.gov/resource/jun7-fc8e.json [Source](https://publicreporting.cftc.gov/resource/jun7-fc8e.json)

---

## Why the weekly workflow is scheduled on Friday

Because the CFTC generally releases the report on **Friday** while the positions are measured on **Tuesday**, the workflow in this package runs after the normal release window. This avoids stale fetches and keeps the dashboard aligned with the official reporting schedule. [Source](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)

---

## Suggested first commit sequence

1. Commit everything from this package.
2. Add your existing `cot-positioning-dashboard.html`.
3. Create `data/` and `data/derived/` folders in the repo.
4. Run the workflow manually with `workflow_dispatch`.
5. Inspect generated JSON.
6. Publish the first GitHub Pages version.

---

## Practical note on CTA wording

The dashboard should present CTA language carefully:

- **Leveraged Money** or **Managed Money** can be used as a **CTA / fast-money proxy**.
- **Asset Managers** can be used as a **slow-money / allocator proxy**.
- **Dealers / Commercials / Producers** represent the hedging or dealer side, depending on report family.

This keeps the dashboard analytically useful without overstating what the public CFTC fields explicitly identify.

---

## Recommended next file to open

Start with:

- `docs/implementation-plan.md`
- `scripts/fetch_cot.py`
- `scripts/derive_metrics.py`
- `.github/workflows/weekly-refresh.yml`

If you want, the next step after upload is to build **Phase 2: the actual polished frontend** on top of this data contract.
