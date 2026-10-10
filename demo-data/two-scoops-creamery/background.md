# Two Scoops Creamery — demo business #1

A fictional mom-and-pop ice cream shop. Use it to demo Hedgehog for a small, weather-driven
business. Its financials are in [`financials.csv`](financials.csv): 129 months, Jan 2016 – Sep 2026.

## Snapshot

| | |
|---|---|
| **Business** | Family-run ice cream shop with a walk-up window and a shaded outdoor patio |
| **Location** | South Congress Ave, Austin, TX |
| **Opened** | January 2016 |
| **Owners** | Rosa and Marcus Delgado, a married couple. Rosa makes the ice cream; Marcus runs the books, catering and the van. |
| **Staff** | 4–12 part-time scoopers depending on the season (mostly students) |
| **Sells** | Scoops and cones in the shop (~80% of sales), event catering, pint delivery, and wholesale pints to 6 local grocers |
| **Size** | ~$730k revenue in 2025, ~$145k operating income. The owners pay themselves through quarterly distributions, not salaries. |

## The story

- **2016 — Opening.** Rosa and Marcus put their savings and a **$90k equipment loan (fixed 6.5%)** into the shop. The patio fills up on hot evenings, and the first summer does about twice what January does.
- **Jun 2017 — Catering.** Weddings and office parties ask for an ice cream cart. Catering peaks in spring and around the December holidays.
- **Jun 2018 — Freezer scare.** The walk-in freezer's compressor dies in June. It costs $3,800, and they nearly lose the inventory.
- **Sep 2019 — Wholesale.** Three local grocers start carrying Two Scoops pints.
- **Mar–Jun 2020 — COVID.** In-store sales stop on March 20. April has no in-store sales at all; they pivot to pint delivery and get a **$24k PPP loan that is later forgiven**. The landlord cuts rent in half for April and May. The patio reopens May 15, at reduced capacity.
- **Feb 2021 — Winter Storm Uri.** The power goes out, the shop is closed 6 days, **$4.2k of inventory melts**, and a pipe bursts ($1.9k). It's the worst February they've had.
- **2022 — Everything costs more.** The dairy co-op raises prices from **$4.05 to $4.80 a gallon**, and gas peaks at **$4.32/gal in June**. Austin has a record number of 100°F days. The heat brings crowds, but the electric bill more than doubles in July, and the AC unit fails mid-heat-wave ($2.6k). The startup loan is paid off in December.
- **Mar 2023 — The van.** They buy a delivery van and a second freezer with a **$68k SBA loan at a variable rate (prime + 2.75%)**. Fed hikes push the rate from 10.50% to **11.25%** by August.
- **Jan 2024 — New lease.** Rent goes from $4,500 to $4,900.
- **May–Jun 2024 — The rainy season from hell.** The rainiest late spring in years keeps the patio empty most weekends. In-store sales fall **about 25–30% below normal** just as the busy season should start.
- **Dec 2024 — Locking in dairy.** After 2022, Marcus signs a **fixed-price dairy contract with the Hill Country co-op: $4.25/gal for all of 2025–2026.**
- **2025–2026 — Steady but exposed.** Wholesale grows to 6 grocers. Fed cuts bring the loan rate down to **9.50%**. As of Sep 2026 the shop is healthy, but one bad summer (rain or extreme heat) or a dairy price jump when the contract ends in 2027 could wipe out a year's profit.

## What the business depends on

- **Weather.** About 80% of sales are walk-in, and the patio is half the seating. Rain empties it. Moderate heat brings crowds, but extreme heat (100°F+) keeps people inside and sends the electric bill up.
- **Dairy.** It's the biggest single cost, about $7k a month. It's on a fixed-price contract until Dec 2026; after that it's exposed to market prices again.
- **Electricity.** Freezers run 24/7, plus AC on the patio-side counter. Summer bills are about twice winter's.
- **Fuel.** For the delivery van and the wholesale runs, since March 2023.
- **The SBA loan.** Variable rate, about $44k left. A 1-point rate rise costs about $440 a year, which is small but real.
- **Customers' spending money.** Ice cream is a treat. When prices rise everywhere, people cut back on treats first.

## What keeps Rosa and Marcus up at night

1. Another rainy May–June like 2024, right when they need the patio full.
2. Extreme heat: a summer of 105°F days means fewer evening crowds *and* a huge electric bill.
3. What happens to dairy prices when the fixed-price contract ends after 2026.
4. Their variable loan rate if the Fed reverses course.

## Demo answers (paste into the questionnaire)

| Question | Answer |
|---|---|
| What does your business do? | Family-run ice cream shop with a walk-up window and outdoor patio seating. We also cater events, deliver pints, and wholesale pints to six local grocery stores. |
| Who are your customers? | Families, UT students, and tourists walking South Congress, mostly on warm evenings and weekends. When prices go up everywhere, people cut back on treats like ours first. |
| Where is your business located? | Austin, TX |
| What does your business rely on to operate day to day? | Freezers and refrigeration running 24/7, good patio weather, foot traffic, and our delivery van for pint deliveries and grocery runs. |
| What materials or services do you use the most? | Dairy (milk and cream) is our biggest cost, then sugar, cones and pint containers. Electricity for the freezers and gas for the van. |
| What outside events have hurt your business before, or worry you most? | Rainy weekends empty the patio — May and June 2024 cost us about a third of our patio sales. Extreme heat waves keep people inside and our electric bill doubles. Winter Storm Uri closed us for 6 days. Gas spikes and our variable-rate van loan going up also hurt. |
| What times of year matter most to your business, and why? | June through August is over a third of our year, so a bad summer is a bad year. Winter is slow. Spring and December are big for catering. |
| Are any of your costs locked in? | Our dairy is on a fixed-price contract with a co-op through December 2026. |

## What Hedgehog should find (judging checklist)

**Should hedge:**
- **Rain in Austin, TX**, especially in May–August. This is the clearest risk in the data (May–Jun 2024).
- **Extreme heat in Austin, TX** (100°F+ days): lost evening traffic plus a big electric bill (Jul 2022).
- **Electricity / energy prices**: freezers and AC.
- **Gas prices**: the van and wholesale runs. It's a small dollar amount, but a real exposure.
- **Interest rates**: the variable-rate SBA loan. Small.
- **Inflation / consumer spending**: they sell a discretionary treat.

**Should *not* hedge:**
- **Dairy prices before 2027**: already locked in by the contract. A smart answer might mention the 2027 renewal risk.

**Where to see it in the CSV:** `notes` marks every event. Useful columns are `in_store_revenue` (rain and COVID dips), `electricity_cost` (summer peaks), `dairy_cost_per_gallon` (the 2022 spike, then flat $4.25), `fuel_cost_per_gallon` (2022) and `loan_interest_rate` (from 2023).
