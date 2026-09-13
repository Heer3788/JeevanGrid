# Demo data and its sources

These sites demonstrate the optimizer. A cited installation establishes a historical location or equipment reference; it does not establish the current operational status of that installation. Coordinates are approximate map positions. Demand curves, costs, fuel, priorities and live readings are simulated.

| Site | Published reference | Demo assumptions |
| --- | --- | --- |
| Leporiang | Published study: 600 kW PV, 100 kW wind, 200 kW diesel, 3,000 kWh storage; 876.41 kWh/day, 101 kW peak | Existing reference values are preserved. This oversized configuration can produce zero-diesel plans. |
| Dharnai, Bihar | Greenpeace reports a 100 kW solar microgrid in 2014, including 30 kW for pumping | Growth-demand example: 680 kWh/day, 74 kW peak, 180 kWh storage, hypothetical 75 kW diesel backup |
| Darewadi, Maharashtra | Gram Oorja reports 9.36 kWp PV and a 28.8 kWh battery bank serving 39 families | 68 kWh/day, 8 kW peak, hypothetical 8 kW diesel backup; declared demo battery policy |
| Rewana, Uttar Pradesh | Tata Power FY2021–22 report identifies microgrid supply to over 100 customers | 30 kW PV, 55 kWh storage, 28 kW generator and 240 kWh/day are assumed |
| Bijua, Uttar Pradesh | Tata Power FY2021–22 report identifies village microgrid supply | 45 kW PV, 80 kWh storage, 40 kW generator and 380 kWh/day are assumed |

Sources:

- [Leporiang original study](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/joe.2017.0447)
- [Greenpeace: Dharnai launch, 20 July 2014](https://www.greenpeace.org/india/en/story/278/dharnai-goes-live-powered-by-greenpeaces-first-solar-microgrid/)
- [Gram Oorja: Darewadi mini-grid case study](https://gramoorja.in/wp-content/uploads/2024/12/Micro-GridPaper.pdf)
- [Tata Power annual report FY2021–22](https://www.tatapower.com/content/dam/tatapoweraemsitesprogram/tatapower/pdf-root/company-financials/annual-reports/103AnnualReport-2021-22.pdf)
- [Tata Power general microgrid offering: sizes start at 30 kW](https://www.tatapower.com/renewables/solar-microgrids)

The four new examples include variable water-pumping and productive-work schedules, limited storage, generator minimum output and start costs. Diesel requirements and shortages are solver outputs; they are never hardcoded to manufacture a saving. Standard stress checks can produce shortages or reserve warnings.

Seeding preserves existing sites, passwords, plans and operator-entered readings. The original reference and two existing compact/constrained examples remain. New sites are found by name so repeating the seed command does not duplicate them.

## Accounts

Supported permission roles remain Admin and Operator. Example identities are:

| Email | Access |
| --- | --- |
| admin@jeevangrid.local | All organization sites and settings |
| operator@jeevangrid.local | Original assigned examples plus the four new village demos |
| bihar.operator@jeevangrid.local | Dharnai demo |
| maharashtra.operator@jeevangrid.local | Darewadi demo |
| up.operator@jeevangrid.local | Rewana and Bijua demos |

These are example identities, not a claim about the original problem statement’s users. The original user/role list was not included in the available repository or pasted run-history attachments.

The login page lists seeded active accounts from this catalog in local debug mode. A quick-login button uses the known default demo password only when it matches the account; custom-password accounts require manual entry. Custom passwords are never returned by the API. Seeding never resets a password.
