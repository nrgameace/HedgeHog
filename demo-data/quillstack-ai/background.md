# Quillstack AI — demo business #2

A fictional early-stage San Francisco AI startup. Use it to demo Hedgehog for a business whose
risks are compute prices, interest rates, regulation and the funding market rather than the
weather. Its financials are in [`financials.csv`](financials.csv): 31 months, Mar 2024 – Sep 2026.

## Snapshot

| | |
|---|---|
| **Business** | AI contract-review assistant for law firms. It reads contracts, flags risky clauses and suggests redlines. |
| **Location** | SoMa, San Francisco, CA |
| **Founded** | March 2024 |
| **Founders** | Priya Raman (CEO, ex-BigLaw associate turned engineer) and Devon Cole (CTO, ex-ML infrastructure) |
| **Team** | 17 people as of Sep 2026 (peaked at 18) |
| **Customers** | 80 mid-size US law firms (20–300 lawyers) |
| **Pricing** | Monthly subscription per firm (~$2k–$3k for new firms; the largest pays $12k), plus usage-based API charges and one-time onboarding fees |
| **Size** | $289k MRR / **$3.47M ARR** (Sep 2026), about 72% gross margin, burning about $180k a month |
| **Funding** | $1.5M pre-seed (Mar 2024), $5M seed (Feb 2025), $1.5M venture loan (Oct 2025) |
| **Cash** | $3.34M, about $3.17M of it in Treasury bills; **about 17 months of runway** |

## The story

- **Mar 2024 — Founded.** $1.5M pre-seed. Two founders in a $3,200/month SoMa sublet run free pilots with 3 law firms. The rest of the cash sits in T-bills at 5.25%.
- **Jun 2024 — First revenue.** The first 2 firms convert to paid at $2k/month each.
- **Oct–Dec 2024 — GPU crunch.** Their cloud region runs out of reserved H100 capacity, forcing them onto on-demand GPUs. The hourly price climbs from $2.70 to **$3.95 in November**. Together with expensive LLM API tokens ($6.00 per million), this pins **gross margin at about 40%**. December brings the first churn as firms slow down for the holidays.
- **Jan 2025 — The cheap-model shock.** A new low-cost open model lets them switch providers. Cost per million tokens falls **40% (from $6.00 to $3.60)**, and gross margin jumps to **64%** almost overnight.
- **Feb 2025 — Seed round.** They close **$5M**. 90% of the cash goes into T-bills yielding 4.30%, which earns about $20k a month in interest.
- **Mar–Oct 2025 — Scaling up.** They move into a full SF office ($28k/month, **lease fixed through Feb 2027**) and grow from 4 to 16 people.
- **Jul 2025 — The whale.** **Hartwell & Pike** (a fictional national law firm) signs at $9k MRR, plus a $15k onboarding fee. It's their largest customer by far.
- **Aug 2025.** They exhibit at a big legal-tech conference ($38k marketing month).
- **Sep–Dec 2025 — Rates fall.** The Fed starts cutting and their T-bill yield drops from 4.30% to 3.65%. A $1.5M venture loan (**prime + 1%, variable**, interest-only for 12 months) extends runway in October. A SOC 2 Type II audit runs Sep–Dec. Hartwell & Pike expands in November.
- **Feb 2026.** Hartwell & Pike expands again to **$14k MRR**, and the team peaks at 18.
- **Mar–Apr 2026 — Free hosting ends.** The startup cloud hosting program ends, so AWS now costs about $9k a month. Gross margin dips from 76% to 71.5%.
- **Apr–May 2026 — The AI-liability bill.** A proposed **state AI-liability bill** would make firms liable for AI-assisted legal work. Law firms pause new purchases pending legal review, new deals slow to a trickle, and Quillstack hires policy counsel and freezes hiring.
- **Jun 2026 — Lost the whale.** Hartwell & Pike cancels (**−$14k MRR**), citing the liability bill.
- **Jul 2026.** An engineer leaves and isn't replaced. Runway, at about 16 months, becomes the board's #1 topic.
- **Aug–Sep 2026 — Won back, but worried.** They win Hartwell & Pike back at **$12k MRR** by adding an indemnity clause. As of Sep 2026: $3.47M ARR, 80 firms, about 17 months of runway, and a **Series A to raise in 2027** into whatever the funding market looks like then. The venture loan starts amortizing in Oct 2026.

## What the business depends on

- **LLM API tokens.** The biggest cost of revenue, about $69k a month. Prices have fallen a lot, but a reversal would hit margins immediately.
- **Rented GPU hours (H100s).** Used for embeddings, rerankers and fine-tuned clause models. Prices spiked about 46% in late 2024.
- **AWS hosting.** Paid at full price since April 2026.
- **Interest rates, both ways.** $3.17M in T-bills earns less with every Fed cut (each 0.25% cut ≈ −$660 a month). The $1.5M venture loan is variable, so cuts help there, but on balance Quillstack is hurt by falling rates.
- **The funding market.** They have to raise a Series A within about 12 months. A tech or AI stock selloff makes that much harder.
- **Regulation.** One state bill already cost them their largest customer for two months.
- **Law-firm budget cycles.** December is dead, and Q1 budgets bring new deals.

## What keeps Priya and Devon up at night

1. The AI-liability bill passing, or similar bills spreading to other states.
2. Raising a Series A in a cold funding market with about 17 months of runway.
3. A GPU or token price spike like late 2024, now at about 10× the usage.
4. Rate cuts eating their interest income while burn stays at about $180k a month.

## Demo answers (paste into the questionnaire)

| Question | Answer |
|---|---|
| What does your business do? | AI software that reviews contracts for law firms — it flags risky clauses and suggests edits. We charge a monthly subscription plus usage-based API fees. |
| Who are your customers? | About 80 mid-size US law firms, from 20 to 300 lawyers. One national firm is our biggest account. |
| Where is your business located? | San Francisco, CA |
| What does your business rely on to operate day to day? | Rented GPUs, LLM APIs from model providers, AWS hosting, our engineering team, and a $1.5M venture loan plus the cash from our seed round sitting in T-bills. |
| What materials or services do you use the most? | LLM API tokens are our biggest cost, then GPU hours and AWS hosting. |
| What outside events have hurt your business before, or worry you most? | GPU prices spiked in late 2024 and cut our margin to 40%. Fed rate cuts shrank the interest on our cash. A proposed state AI-liability regulation made firms pause purchases and we lost our largest customer for two months. A weak funding market or a Nasdaq selloff would make our Series A much harder. |
| What times of year matter most to your business, and why? | Law firms freeze spending in December and buy in Q1 when new budgets open. We need to raise our Series A in early 2027. |
| Are any of your costs locked in at a set price, like a fixed-price supplier contract, a fixed-rate loan or a long-term lease? | Our office lease is fixed through February 2027. |
| How much budget would you have for risk mitigation? | Up to $6,000 a month. |

## What Hedgehog should find (judging checklist)

**Should hedge:**
- **AI regulation**: the state AI-liability bill. It's the clearest risk in the data (Apr–Aug 2026).
- **GPU prices**: the late-2024 spike.
- **Interest rates**: falling rates cut interest on $3.17M of T-bills, and the loan is variable. Net, they're hurt by *cuts*.
- **Funding market / tech stocks**: a Series A is due within about 12 months.

**Should *not* hedge:**
- **Office rent**: fixed through Feb 2027, and there's no market for it anyway.
- **Weather**: it doesn't affect a software company.

**Where to see it in the CSV:** `notes` marks every event. Useful columns are `gpu_cost_per_hour` (late-2024 spike), `cost_per_million_tokens` (Jan 2025 drop), `gross_margin_pct`, `treasury_yield_pct` and `interest_income` (falling from 2025), `new_mrr` and `churned_mrr` (the Apr–Aug 2026 regulation hit), and `runway_months`.
