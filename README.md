# Veridi Logistics — "Last Mile" Delivery Auditor

> **Olist E-Commerce Delivery Performance Audit** | AmaliTech Data Lab Challenge

---

## A. Executive Summary

<!-- Fill this in after completing your analysis -->
<!-- Example structure:
Analysis of ~100,000 Olist orders reveals that X% of deliveries arrived later than the estimated date,
with the worst-performing states being [AM, RR, AC] — remote northern regions far from São Paulo's
distribution hubs. Late deliveries correlate strongly with poor customer reviews: on-time orders average
a review score of ~4.2/5, while "Super Late" orders (>5 days past estimate) drop to ~2.0/5. Pipeline
breakdown analysis shows that transit time — not warehouse processing — is the primary driver of delays,
pointing to carrier SLA negotiation as the highest-leverage intervention.
-->

---

## B. Project Links

| Deliverable | Link |
|-------------|------|
| Notebook (GitHub) | *(link once pushed)* |
| Notebook (HTML export) | *(link once pushed — see `exports/delivery_audit.html`)* |
| Dashboard | *(Streamlit Cloud URL — add after deploy)* |
| Presentation | *(Google Slides / PDF link)* |
| Video Walkthrough (optional) | *(YouTube link)* |

---

## C. Technical Explanation

### Data Cleaning Approach

1. **Datetime parsing** — All timestamp columns were parsed with `pd.to_datetime()`.
2. **Non-delivered orders excluded** — Orders with `order_status` of `canceled` or `unavailable`, and any rows with a null `order_delivered_customer_date`, were filtered out before delay calculations.
3. **Duplicate review handling** — The reviews table can have multiple entries per `order_id`. Rows were deduplicated by keeping the first review per order (by `review_creation_date`), preventing row explosion on join.
4. **Row integrity check** — An assertion `len(master) == len(orders)` was run after all joins to confirm no accidental duplication.

### Candidate's Choice — Pipeline Breakdown Analysis

**Feature:** The notebook and dashboard include a "Where Does the Delay Happen?" analysis that decomposes total delivery time into three phases:
- **Processing time**: `order_approved_at − order_purchase_timestamp`
- **Warehouse-to-carrier time**: `order_delivered_carrier_date − order_approved_at`
- **Transit time**: `order_delivered_customer_date − order_delivered_carrier_date`

**Why it matters:** Telling a CEO "deliveries are late" is not actionable. Knowing *which phase* is responsible tells Veridi exactly where to invest: if transit time is the culprit, the fix is carrier SLA renegotiation or switching providers. If warehouse time is the bottleneck, the fix is internal ops. This transforms the audit from a diagnosis into a roadmap.

---

## Setup & Reproducibility

1. Download the [Olist dataset from Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and place all CSVs in the `data/` directory.
2. Install dependencies: `pip install pandas numpy matplotlib seaborn plotly jupyter`
3. Run: `jupyter notebook notebooks/delivery_audit.ipynb`
4. All file paths are **relative** — no local path changes needed.

### Dashboard (local)
```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

---

*Dataset: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — CC BY-NC-SA 4.0*
