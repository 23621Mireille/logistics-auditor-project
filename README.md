# Veridi Logistics — Last Mile Delivery Auditor

> Olist Brazilian E-Commerce Delivery Performance Audit | AmaliTech Data Lab Challenge

---

## Executive Summary

Analysis of approximately 96,000 delivered Olist orders reveals that around 6.8% of shipments arrived later than the estimated delivery date, with the worst-performing states concentrated in Brazil's remote northern regions — Amazonas (AM), Roraima (RR), Acre (AC), and Amapa (AP) — which sit far from the primary Sao Paulo distribution hubs. Late deliveries correlate directly with poor customer sentiment: on-time orders average a review score of approximately 4.1 out of 5, while orders arriving more than five days late (classified as "Super Late") drop to roughly 2.3 out of 5. Pipeline breakdown analysis identifies transit time — the carrier-to-customer phase — as the dominant contributor to delay, not internal warehouse processing. This finding directs intervention toward carrier SLA renegotiation rather than internal operations, giving Veridi a clear, prioritised action.

---

## Live Dashboard

[https://logistics-auditor-project-y8kkn9hybsyaeswofjreg9.streamlit.app](https://logistics-auditor-project-y8kkn9hybsyaeswofjreg9.streamlit.app)

The dashboard loads data automatically on first visit. No setup is required to view it.

---

## Project Structure

```
logistics-lab/
├── data/                          # Raw CSVs (gitignored — downloaded automatically)
├── notebooks/
│   ├── 01_schema_builder.ipynb
│   ├── 02_delay_calculator.ipynb
│   ├── 03_geographic_heatmap.ipynb
│   ├── 04_sentiment_correlation.ipynb
│   ├── 05_category_translation.ipynb
│   ├── 06_pipeline_breakdown.ipynb
│   └── delivery_audit.ipynb       # Combined submission notebook
├── dashboard/
│   ├── app.py                     # Streamlit dashboard
│   └── requirements.txt
├── exports/                       # HTML export of notebook
└── README.md
```

---

## Running Locally

### Prerequisites

- Python 3.9 or higher
- A free [Kaggle account](https://www.kaggle.com) with an API token

### 1. Clone the repository

```bash
git clone https://github.com/23621Mireille/logistics-auditor-project.git
cd logistics-auditor-project
```

### 2. Download the dataset

Download the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) from Kaggle and extract all CSV files into the `data/` directory:

```
data/
├── olist_orders_dataset.csv
├── olist_order_reviews_dataset.csv
├── olist_customers_dataset.csv
├── olist_products_dataset.csv
├── olist_order_items_dataset.csv
└── product_category_name_translation.csv
```

### 3. Run the notebooks

Install notebook dependencies and run the six notebooks in order (01 through 06). Each notebook saves a Parquet file consumed by the next:

```bash
pip install pandas numpy matplotlib plotly jupyter pyarrow
jupyter notebook
```

Open `notebooks/` and run cells top to bottom in sequence: `01` → `02` → `03` → `04` → `05` → `06`.

Alternatively, run the combined notebook:

```bash
jupyter notebook notebooks/delivery_audit.ipynb
```

### 4. Run the dashboard

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

The app will open at `http://localhost:8501`. If the Parquet files from step 3 exist in `data/`, they are loaded directly. Otherwise the app falls back to reading the raw CSVs.

---

## Dashboard Usage Guide

The dashboard has a sidebar and four analysis tabs.

**Sidebar filters**

- **Filter by State** — select one or more Brazilian states to scope all charts. Use the "All" button to restore the full selection or "Clear" to reset.
- **Delivery Status** — toggle between On Time, Late, and Super Late order groups.

The sidebar live-updates a summary panel showing the order count and breakdown for the current selection.

**Geographic tab**

Choropleth map and horizontal bar chart showing the late delivery rate (%) by state. Red indicates high late rates; green indicates low. Hover over any state on the map for order count, average delay, and average review score.

**Sentiment tab**

Two charts showing average review score by delivery status and the full score distribution. A bubble scatter plot below them shows how average review score changes across delay bins, with a trend line confirming the negative correlation.

**Categories tab**

Horizontal bar chart of the top product categories by late delivery rate. Use the sliders to adjust the minimum order threshold and the number of categories displayed. Bar colour reflects the average review score for that category.

**Pipeline Breakdown tab**

Stacked bar chart decomposing average delivery time into three phases — Payment Processing, Warehouse to Carrier, and Carrier to Customer (Transit) — for each delivery status group. A summary below the chart identifies the dominant delay phase and recommends a targeted action.

---

## Technical Notes

### Data cleaning

- All timestamp columns were parsed with `pd.to_datetime()`.
- Orders with status `canceled` or `unavailable`, and any rows with a null `order_delivered_customer_date`, were excluded before delay calculations.
- The reviews table can contain multiple rows per order. Rows were deduplicated by keeping the earliest review per `order_id` to prevent row inflation on join.
- A row-count assertion after all joins confirms no accidental duplication.

### Candidate's Choice — Pipeline Breakdown

The pipeline breakdown decomposes total delivery time into three measurable phases:

| Phase | Calculation |
|-------|-------------|
| Payment Processing | `order_approved_at` minus `order_purchase_timestamp` |
| Warehouse to Carrier | `order_delivered_carrier_date` minus `order_approved_at` |
| Carrier to Customer | `order_delivered_customer_date` minus `order_delivered_carrier_date` |

Comparing these averages across On Time, Late, and Super Late orders isolates where the extra time accumulates. This moves the analysis from diagnosis ("deliveries are late") to prescription ("the carrier phase adds X extra days — renegotiate SLAs").

---

## Dataset

[Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — licensed under CC BY-NC-SA 4.0.
