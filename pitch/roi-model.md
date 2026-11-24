# RoboFleet Return on Investment (ROI) & Economic Model

**Disclaimer & Presentation Notice**:  
*The figures produced by this model are estimates generated from parametric simulations in the RoboFleet digital twin under stated operational assumptions. They are not contractual performance guarantees. Clients are invited to calibrate the model using their actual historical transaction logs via `robofleet calibrate`.*

---

## 1. Executive Summary & Economics

For a standard high-velocity micro-fulfillment store processing **1,500 orders/day** with an average basket size of **4.5 items/order**:

- **Direct Annual Labor Savings**: **$583,756 / year** (reducing pick labor hours from 103.8 to 38.6 hours/day by eliminating manual transit).
- **Annual SLA Breach & Penalty Reduction**: **$246,562 / year** (reducing on-demand delivery breaches from 6.5% to < 0.5%).
- **Total Gross Operating Savings**: **$830,319 / year**.
- **Net Annual Benefit (After Platform & AMR Lease)**: **$506,319 / year**.
- **Estimated Payback Period**: **4.7 Months**.

---

## 2. Core Operational Formulas

### A. Direct Picking Labor Savings
Manual dark store picking forces human operators to walk miles through aisles pushing manual carts, achieving an average rate of 60–70 units/hour:

$$\text{Daily Units} = \text{Daily Orders} \times \text{Avg Basket Size}$$

$$\text{Manual Labor Hours/Day} = \frac{\text{Daily Units}}{\text{Manual Pick Rate (65 units/hr)}}$$

In the RoboFleet automated goods-to-person station model, AMRs bring totes directly to station pickers, elevating throughput to 175+ units/hour:

$$\text{RoboFleet Labor Hours/Day} = \frac{\text{Daily Units}}{\text{Assisted Pick Rate (175 units/hr)}}$$

$$\text{Annual Labor Savings} = (\text{Manual Hours} - \text{RoboFleet Hours}) \times \text{Hourly Wage} \times 365$$

### B. SLA Breach & Spoilage Avoidance
Under manual operation during rush periods (2.5x demand), pick queues stall, leading to late dispatch penalties, canceled orders, and customer compensation vouchers:

$$\text{Baseline Penalty} = \text{Annual Orders} \times \text{Breach Rate (6.5\%)} \times \text{Cost per Breach (\$7.50)}$$

$$\text{RoboFleet Penalty} = \text{Annual Orders} \times \text{Evidenced Breach Rate (0.5\%)} \times \text{Cost per Breach (\$7.50)}$$

$$\text{Annual SLA Savings} = \text{Baseline Penalty} - \text{RoboFleet Penalty}$$

---

## 3. Customizing for Your Facility

To run your specific store parameters:
1. Open `pitch/roi-calculator.csv` in Excel, Google Sheets, or your preferred spreadsheet tool.
2. Update Column D (`Client_Input`) with:
   - Your daily order volume
   - Your local fully burdened labor rate ($/hour)
   - Your historical SLA breach rate (%)
3. The spreadsheet formulas automatically calculate your projected net savings and payback schedule.
4. Run `robofleet calibrate --file your_orders.csv` to replace synthetic basket and arrival assumptions with your actual customer data.
