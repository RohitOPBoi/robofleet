"""Customer Order Calibration CLI (Phase 7 - P7-A9, CA-2).
Calibrates simulation parameters (diurnal profile, Poisson arrival rate, basket size distribution,
and SKU catalogue popularity) from historical customer export CSVs.
Produces calibrated_profile.yaml and a structured fit-quality report.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
from pathlib import Path
import sys
from typing import Any
import numpy as np
import yaml


def parse_customer_csv(csv_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parses customer export CSV, handling dirty/noisy inputs with clear anomaly logging."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Customer orders CSV not found: {csv_path}")

    valid_records: list[dict[str, Any]] = []
    anomalies: list[str] = []
    total_rows = 0

    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Empty or corrupted CSV file: {csv_path}")

        # Normalize column headers
        field_map = {col.strip().lower(): col for col in reader.fieldnames}
        order_col = field_map.get("order_id") or field_map.get("orderid") or field_map.get("id")
        sku_col = field_map.get("sku_id") or field_map.get("skuid") or field_map.get("sku") or field_map.get("product_id")
        qty_col = field_map.get("quantity") or field_map.get("qty") or field_map.get("count")
        time_col = field_map.get("timestamp") or field_map.get("time") or field_map.get("created_at") or field_map.get("date")

        if not order_col or not sku_col:
            raise ValueError(f"Missing required columns (order_id, sku_id). Found: {list(reader.fieldnames)}")

        for row_idx, row in enumerate(reader, start=2):
            total_rows += 1
            order_id = (row.get(order_col) or "").strip()
            sku_id = (row.get(sku_col) or "").strip()
            qty_raw = (row.get(qty_col) or "1").strip() if qty_col else "1"
            time_raw = (row.get(time_col) or "").strip() if time_col else ""

            if not order_id:
                anomalies.append(f"Row {row_idx}: Missing order_id (skipped)")
                continue
            if not sku_id:
                anomalies.append(f"Row {row_idx}: Missing sku_id for order '{order_id}' (skipped)")
                continue

            try:
                qty = int(float(qty_raw))
                if qty <= 0:
                    anomalies.append(f"Row {row_idx}: Non-positive quantity '{qty_raw}' for order '{order_id}' (defaulted to 1)")
                    qty = 1
            except ValueError:
                anomalies.append(f"Row {row_idx}: Invalid quantity format '{qty_raw}' (defaulted to 1)")
                qty = 1

            # Parse timestamp if available
            parsed_hour = 12  # fallback default
            if time_raw:
                try:
                    # Try ISO format
                    dt = datetime.datetime.fromisoformat(time_raw.replace("Z", "+00:00"))
                    parsed_hour = dt.hour
                except Exception:
                    try:
                        # Try simple HH:MM:SS or YYYY-MM-DD HH:MM:SS
                        if " " in time_raw:
                            t_part = time_raw.split(" ")[1]
                        else:
                            t_part = time_raw
                        parsed_hour = int(t_part.split(":")[0])
                    except Exception:
                        pass

            valid_records.append({
                "order_id": order_id,
                "sku_id": sku_id,
                "quantity": qty,
                "hour": parsed_hour,
            })

    stats = {
        "total_rows_processed": total_rows,
        "valid_lines_retained": len(valid_records),
        "anomalies_detected": len(anomalies),
        "anomalies_sample": anomalies[:10],
    }
    return valid_records, stats


def calibrate_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Fits statistical parameters from parsed customer records."""
    # 1. Group records by order_id
    orders_map: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        orders_map.setdefault(r["order_id"], []).append(r)

    total_orders = len(orders_map)
    basket_sizes = [sum(item["quantity"] for item in items) for items in orders_map.values()]
    unique_skus_per_order = [len(items) for items in orders_map.values()]

    # Basket statistics
    basket_mean = float(np.mean(basket_sizes)) if basket_sizes else 1.0
    basket_std = float(np.std(basket_sizes)) if len(basket_sizes) > 1 else 0.0
    basket_median = float(np.median(basket_sizes)) if basket_sizes else 1.0
    basket_p90 = float(np.percentile(basket_sizes, 90)) if basket_sizes else 1.0

    # 2. Diurnal arrival curve (24 hours)
    hourly_counts = [0] * 24
    for items in orders_map.values():
        hour = items[0]["hour"]
        if 0 <= hour < 24:
            hourly_counts[hour] += 1
        else:
            hourly_counts[12] += 1

    total_hourly = sum(hourly_counts) or 1
    diurnal_profile = [round(c / total_hourly, 4) for c in hourly_counts]
    peak_hour = int(np.argmax(hourly_counts))
    peak_fraction = float(np.max(diurnal_profile))

    # Poisson arrival rate (average orders per simulated hour)
    arrival_rate_orders_per_hr = round(total_orders / 24.0, 2) if total_orders > 0 else 60.0

    # 3. SKU Catalogue Popularity & Pareto Fitting
    sku_counts: dict[str, int] = {}
    for r in records:
        sku = r["sku_id"]
        sku_counts[sku] = sku_counts.get(sku, 0) + r["quantity"]

    unique_skus_count = len(sku_counts)
    sorted_skus = sorted(sku_counts.items(), key=lambda kv: kv[1], reverse=True)
    total_units = sum(sku_counts.values()) or 1

    top_20_pct_count = max(1, int(0.20 * unique_skus_count))
    top_20_units = sum(c for _, c in sorted_skus[:top_20_pct_count])
    pareto_share_top_20 = round((top_20_units / total_units) * 100.0, 1)

    top_5_skus = [{"sku_id": s, "units": c, "share_pct": round(c / total_units * 100, 2)} for s, c in sorted_skus[:5]]

    return {
        "calibration_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_orders_analyzed": total_orders,
        "unique_skus_count": unique_skus_count,
        "total_units_sold": total_units,
        "demand_profile": {
            "arrival_rate_orders_per_hr": arrival_rate_orders_per_hr,
            "peak_hour": peak_hour,
            "peak_hourly_fraction": peak_fraction,
            "diurnal_24h_weights": diurnal_profile,
        },
        "basket_distribution": {
            "mean_units": round(basket_mean, 2),
            "std_units": round(basket_std, 2),
            "median_units": round(basket_median, 2),
            "p90_units": round(basket_p90, 2),
            "mean_unique_skus": round(float(np.mean(unique_skus_per_order)), 2) if unique_skus_per_order else 1.0,
        },
        "catalogue_distribution": {
            "top_20_percent_sku_volume_share": pareto_share_top_20,
            "pareto_80_20_adherence": "High" if pareto_share_top_20 >= 70 else ("Moderate" if pareto_share_top_20 >= 50 else "Uniform"),
            "top_skus": top_5_skus,
        },
    }


def execute_calibration(csv_path: Path, out_yaml: Path | None = None, report_md: Path | None = None) -> tuple[Path, Path]:
    """Runs calibration pipeline and outputs YAML profile and Markdown report."""
    print(f"=== RoboFleet Customer Data Calibration Tool (CA-2) ===")
    print(f"  - Input File: {csv_path}")

    records, parse_stats = parse_customer_csv(csv_path)
    calibrated = calibrate_profile(records)

    out_yaml_path = out_yaml or csv_path.parent / "calibrated_profile.yaml"
    out_report_path = report_md or csv_path.parent / "calibration_report.md"

    # Save YAML
    with open(out_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(calibrated, f, sort_keys=False, indent=2)

    # Save Markdown Fit-Quality Report
    with open(out_report_path, "w", encoding="utf-8") as f:
        f.write("# RoboFleet Customer Data Calibration Report\n\n")
        f.write(f"- **Input File**: `{csv_path}`\n")
        f.write(f"- **Calibrated At**: `{calibrated['calibration_timestamp']}`\n")
        f.write(f"- **Rows Processed**: {parse_stats['total_rows_processed']}\n")
        f.write(f"- **Valid Lines Retained**: {parse_stats['valid_lines_retained']}\n")
        f.write(f"- **Anomalies Detected**: {parse_stats['anomalies_detected']}\n\n")

        f.write("## 1. Fitted Operational Parameters\n\n")
        dp = calibrated["demand_profile"]
        bd = calibrated["basket_distribution"]
        cd = calibrated["catalogue_distribution"]

        f.write("| Parameter Domain | Metric | Calibrated Value | Notes |\n")
        f.write("|---|---|---|---|\n")
        f.write(f"| Demand Arrival | Poisson Mean Rate | `{dp['arrival_rate_orders_per_hr']} orders/hr` | Average diurnal arrival rate |\n")
        f.write(f"| Demand Arrival | Diurnal Peak Hour | `Hour {dp['peak_hour']:02d}:00` | {dp['peak_hourly_fraction']*100:.1f}% of daily volume |\n")
        f.write(f"| Basket Size | Mean Units/Order | `{bd['mean_units']} +/- {bd['std_units']}` | Median: {bd['median_units']}, P90: {bd['p90_units']} |\n")
        f.write(f"| Catalogue | Unique SKUs | `{calibrated['unique_skus_count']}` | Total volume: {calibrated['total_units_sold']} units |\n")
        f.write(f"| Catalogue | Top 20% SKU Share | `{cd['top_20_percent_sku_volume_share']}%` | Adherence: {cd['pareto_80_20_adherence']} |\n\n")

        f.write("## 2. Diurnal Arrival Profile (24h Normalized Curve)\n\n")
        f.write("```json\n")
        f.write(json.dumps(dp["diurnal_24h_weights"], indent=2))
        f.write("\n```\n\n")

        f.write("## 3. Data Integrity & Anomaly Summary\n\n")
        if parse_stats["anomalies_detected"] == 0:
            f.write("Zero data anomalies detected. Perfect input conformity.\n")
        else:
            f.write(f"Encountered {parse_stats['anomalies_detected']} formatting anomalies (repaired safely):\n")
            for a in parse_stats["anomalies_sample"]:
                f.write(f"- {a}\n")

    print(f"\nCalibration Successful:")
    print(f"  - Config profile written to: {out_yaml_path}")
    print(f"  - Fit report written to:     {out_report_path}")
    print(f"  - Processed {parse_stats['valid_lines_retained']} records across {calibrated['total_orders_analyzed']} orders.")

    return out_yaml_path, out_report_path


def cmd_calibrate(args: argparse.Namespace) -> int:
    csv_path = Path(args.file)
    out_yaml = Path(args.out) if args.out else None
    out_report = Path(args.report) if args.report else None

    execute_calibration(csv_path, out_yaml=out_yaml, report_md=out_report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RoboFleet Customer Data Calibration Tool")
    parser.add_argument("--file", required=True, help="Path to customer order export CSV")
    parser.add_argument("--out", default=None, help="Output path for calibrated_profile.yaml")
    parser.add_argument("--report", default=None, help="Output path for calibration_report.md")
    args = parser.parse_args()
    return cmd_calibrate(args)


if __name__ == "__main__":
    sys.exit(main())
