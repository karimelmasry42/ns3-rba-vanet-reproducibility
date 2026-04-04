#!/usr/bin/env python3

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


def sample_stddev(values):
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def nice_axis_max(value):
    if value <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def nice_step(value):
    if value <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 2.5:
        nice = 2.5
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def nice_axis_bounds(min_value, max_value, target_ticks=6, include_zero=False):
    if include_zero:
        min_value = min(min_value, 0.0)
        max_value = max(max_value, 0.0)

    if math.isclose(min_value, max_value):
        padding = max(abs(min_value) * 0.1, 1.0 if include_zero else 0.05)
        min_value -= padding
        max_value += padding

    raw_step = (max_value - min_value) / max(target_ticks - 1, 1)
    step = nice_step(raw_step)
    axis_min = math.floor(min_value / step) * step
    axis_max = math.ceil(max_value / step) * step

    if include_zero:
        axis_min = min(axis_min, 0.0)
        axis_max = max(axis_max, 0.0)

    tick_values = []
    current = axis_min
    while current <= axis_max + (step / 2):
        tick_values.append(round(current, 12))
        current += step

    return axis_min, axis_max, tick_values


def build_x_ticks(x_values, target_ticks=10):
    unique_values = sorted(set(x_values))
    if len(unique_values) <= 12:
        return unique_values

    min_x = unique_values[0]
    max_x = unique_values[-1]
    raw_step = (max_x - min_x) / max(target_ticks - 1, 1)
    step = max(10, int(round(nice_step(raw_step) / 10.0)) * 10)

    tick_values = [min_x]
    current = math.ceil(min_x / step) * step
    while current < max_x:
        if current > min_x:
            tick_values.append(int(current))
        current += step
    if tick_values[-1] != max_x:
        tick_values.append(max_x)

    return sorted(set(tick_values))


def format_number(value):
    return f"{value:.3f}".rstrip("0").rstrip(".")


def write_svg_plot(output_path, title, y_label, series, y_min, y_max, y_tick_values):
    width = 960
    height = 540
    margin_left = 88
    margin_right = 24
    margin_top = 56
    margin_bottom = 76
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    x_values = [point["x"] for point in series]
    min_x = min(x_values)
    max_x = max(x_values)
    x_span = max(max_x - min_x, 1)
    y_span = max(y_max - y_min, 1e-9)

    def x_to_svg(value):
        return margin_left + ((value - min_x) / x_span) * plot_width

    def y_to_svg(value):
        return margin_top + plot_height - ((value - y_min) / y_span) * plot_height

    x_ticks = build_x_ticks(x_values)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>',
        'text { font-family: Helvetica, Arial, sans-serif; fill: #13233a; }',
        '.title { font-size: 24px; font-weight: 700; }',
        '.axis-label { font-size: 16px; font-weight: 600; }',
        '.tick { font-size: 12px; }',
        '.grid { stroke: #d7e0ea; stroke-width: 1; }',
        '.axis { stroke: #13233a; stroke-width: 2; }',
        '.line { fill: none; stroke: #0b7285; stroke-width: 3; }',
        '.marker { fill: #0b7285; }',
        '.error { stroke: #2f4858; stroke-width: 1.5; }',
        '</style>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text class="title" x="{margin_left}" y="32">{title}</text>',
    ]

    for tick_value in y_tick_values:
        y = y_to_svg(tick_value)
        lines.append(
            f'<line class="grid" x1="{margin_left}" y1="{y}" x2="{width - margin_right}" y2="{y}"/>'
        )
        lines.append(
            f'<text class="tick" x="{margin_left - 12}" y="{y + 4}" text-anchor="end">{format_number(tick_value)}</text>'
        )

    for x_value in x_ticks:
        x = x_to_svg(x_value)
        lines.append(
            f'<line class="grid" x1="{x}" y1="{margin_top}" x2="{x}" y2="{height - margin_bottom}"/>'
        )
        lines.append(
            f'<text class="tick" x="{x}" y="{height - margin_bottom + 20}" text-anchor="middle">{x_value}</text>'
        )

    lines.append(
        f'<line class="axis" x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}"/>'
    )
    lines.append(
        f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}"/>'
    )

    lines.append(
        f'<text class="axis-label" x="{margin_left + plot_width / 2}" y="{height - 16}" text-anchor="middle">Number of Vehicles</text>'
    )
    lines.append(
        f'<text class="axis-label" x="22" y="{margin_top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 22 {margin_top + plot_height / 2})">{y_label}</text>'
    )

    polyline_points = " ".join(
        f"{x_to_svg(point['x'])},{y_to_svg(point['mean'])}" for point in series
    )
    lines.append(f'<polyline class="line" points="{polyline_points}"/>')

    for point in series:
        x = x_to_svg(point["x"])
        y = y_to_svg(point["mean"])
        low = y_to_svg(max(point["mean"] - point["stddev"], y_min))
        high = y_to_svg(min(point["mean"] + point["stddev"], y_max))
        if point["stddev"] > 0:
            lines.append(f'<line class="error" x1="{x}" y1="{low}" x2="{x}" y2="{high}"/>')
            lines.append(f'<line class="error" x1="{x - 6}" y1="{low}" x2="{x + 6}" y2="{low}"/>')
            lines.append(f'<line class="error" x1="{x - 6}" y1="{high}" x2="{x + 6}" y2="{high}"/>')
        lines.append(f'<circle class="marker" cx="{x}" cy="{y}" r="4.5"/>')

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def aggregate_rows(input_csv):
    groups = defaultdict(lambda: {"loss": [], "delay": []})

    with input_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            node_count = int(row["num_vehicles"])
            groups[node_count]["loss"].append(float(row["packet_loss_ratio"]))
            groups[node_count]["delay"].append(float(row["mean_rba_end_to_end_delay_ms"]))

    summary = []
    for node_count in sorted(groups):
        loss_values = groups[node_count]["loss"]
        delay_values = groups[node_count]["delay"]
        summary.append(
            {
                "num_vehicles": node_count,
                "runs": len(loss_values),
                "packet_loss_ratio_mean": mean(loss_values),
                "packet_loss_ratio_stddev": sample_stddev(loss_values),
                "packet_loss_ratio_min": min(loss_values),
                "packet_loss_ratio_max": max(loss_values),
                "end_to_end_delay_ms_mean": mean(delay_values),
                "end_to_end_delay_ms_stddev": sample_stddev(delay_values),
                "end_to_end_delay_ms_min": min(delay_values),
                "end_to_end_delay_ms_max": max(delay_values),
            }
        )
    return summary


def write_summary_csv(output_csv, summary_rows):
    fieldnames = [
        "num_vehicles",
        "runs",
        "packet_loss_ratio_mean",
        "packet_loss_ratio_stddev",
        "packet_loss_ratio_min",
        "packet_loss_ratio_max",
        "end_to_end_delay_ms_mean",
        "end_to_end_delay_ms_stddev",
        "end_to_end_delay_ms_min",
        "end_to_end_delay_ms_max",
    ]

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)


def build_plot_series(summary_rows, x_field, y_field, stddev_field):
    return [
        {"x": row[x_field], "mean": row[y_field], "stddev": row[stddev_field]}
        for row in summary_rows
    ]


def main():
    parser = argparse.ArgumentParser(description="Generate scaling plots from the RBA sweep CSV.")
    parser.add_argument("--input-csv", required=True, help="Input per-run CSV from the ns-3 sweep")
    parser.add_argument("--output-dir", required=True, help="Directory for the generated plot files")
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = aggregate_rows(input_csv)
    if not summary_rows:
        raise SystemExit("No rows found in input CSV")

    summary_csv = output_dir / "rba-node-count-summary.csv"
    loss_svg = output_dir / "packet-loss-vs-node-count.svg"
    delay_svg = output_dir / "end-to-end-delay-vs-node-count.svg"

    write_summary_csv(summary_csv, summary_rows)

    loss_series = build_plot_series(
        summary_rows, "num_vehicles", "packet_loss_ratio_mean", "packet_loss_ratio_stddev"
    )
    delay_series = build_plot_series(
        summary_rows, "num_vehicles", "end_to_end_delay_ms_mean", "end_to_end_delay_ms_stddev"
    )

    loss_axis_min, loss_axis_max, loss_ticks = nice_axis_bounds(
        min(point["mean"] - point["stddev"] for point in loss_series),
        max(point["mean"] + point["stddev"] for point in loss_series),
        target_ticks=8,
        include_zero=False,
    )
    delay_axis_max = nice_axis_max(max(point["mean"] + point["stddev"] for point in delay_series))
    _, _, delay_ticks = nice_axis_bounds(
        0.0,
        delay_axis_max,
        target_ticks=6,
        include_zero=True,
    )

    write_svg_plot(
        loss_svg,
        "Packet Loss vs Node Count",
        "Packet Loss Ratio",
        loss_series,
        loss_axis_min,
        loss_axis_max,
        loss_ticks,
    )
    write_svg_plot(
        delay_svg,
        "End-to-End Delay vs Node Count",
        "End-to-End Delay (ms)",
        delay_series,
        0.0,
        delay_axis_max,
        delay_ticks,
    )

    print(f"Wrote summary CSV: {summary_csv}")
    print(f"Wrote loss plot: {loss_svg}")
    print(f"Wrote delay plot: {delay_svg}")


if __name__ == "__main__":
    main()
