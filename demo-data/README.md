# Demo data — Hedgehog's north star

Two fictional businesses that the whole team builds, tests and demos against. Use these instead of inventing data: the frontend mock, backend tests, model prompts and the live demo should all use them, so results can be compared.

| Business | What it shows | Files |
|---|---|---|
| **Two Scoops Creamery**: mom-and-pop ice cream shop, Austin, TX (Jan 2016 – Sep 2026, 129 months) | A small, weather-driven business. Rain, extreme heat, energy, gas, a variable-rate loan, and a dairy contract that's already locked in. | [background](two-scoops-creamery/background.md) · [financials.csv](two-scoops-creamery/financials.csv) |
| **Quillstack AI**: early-stage AI startup, San Francisco, CA (Mar 2024 – Sep 2026, 31 months) | A tech business with no weather risk. GPU and token prices, interest rates on its cash, AI regulation, and the funding market. | [background](quillstack-ai/background.md) · [financials.csv](quillstack-ai/financials.csv) |

## How to use it in a demo
1. Open the business's `background.md` and paste its **Demo answers** into the questionnaire.
2. Upload its `financials.csv`.
3. Compare the results with the **What Hedgehog should find** checklist at the bottom of the background.

## About the files
- **Fixed, hand-built files:** nothing is random or generated at runtime. If you change a story, update its CSV and `notes` together.
- **Monthly rows, one CSV per business.** The `notes` column marks the months where something happened (storms, price spikes, funding rounds), and each background's timeline matches those notes.
- **The numbers add up:** line items sum to totals, net income follows from operating income, interest and tax, cash rolls forward month to month, and the startup's MRR and customer counts roll forward.
- **Only what a business would record itself:** prices it actually paid, sales, staff and loans. Weather and market data aren't in the CSVs. Those come from the stories now and from live data in the backend later.
- **Real background events** (COVID, Winter Storm Uri, the 2022 inflation and gas spike, Fed rate changes) keep it believable. The businesses, people and law firms are invented.
