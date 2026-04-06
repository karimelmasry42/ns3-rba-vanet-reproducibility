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


def summarize_optional(values):
    if not values:
        return {
            "sum": "",
            "mean": "",
            "stddev": "",
            "min": "",
            "max": "",
        }
    return {
        "sum": sum(values),
        "mean": mean(values),
        "stddev": sample_stddev(values),
        "min": min(values),
        "max": max(values),
    }


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


def write_svg_plot(
    output_path,
    header_title,
    subtitle,
    x_label,
    y_label,
    legend_label,
    line_color,
    series,
    y_min,
    y_max,
    y_tick_values,
):
    width = 960
    height = 540
    margin_left = 92
    margin_right = 28
    margin_top = 72
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
        'text { font-family: Helvetica, Arial, sans-serif; fill: #222222; }',
        '.header { font-size: 17px; font-weight: 400; }',
        '.subtitle { font-size: 15px; font-weight: 400; }',
        '.axis-label { font-size: 13px; font-weight: 400; }',
        '.tick { font-size: 11px; }',
        '.grid { stroke: #bdbdbd; stroke-width: 1; stroke-dasharray: 1.5 2; }',
        '.axis { stroke: #000000; stroke-width: 1; }',
        '.legend { font-size: 11px; }',
        '.line { fill: none; stroke-width: 1.5; }',
        '.marker { stroke-width: 1.2; }',
        '.tick-mark { stroke: #000000; stroke-width: 1; }',
        '</style>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text class="header" x="{width / 2}" y="22" text-anchor="middle">{header_title}</text>',
        f'<text class="subtitle" x="{width / 2}" y="48" text-anchor="middle">{subtitle}</text>',
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
        f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{width - margin_right}" y2="{margin_top}"/>'
    )
    lines.append(
        f'<line class="axis" x1="{width - margin_right}" y1="{margin_top}" x2="{width - margin_right}" y2="{height - margin_bottom}"/>'
    )

    for tick_value in y_tick_values:
        y = y_to_svg(tick_value)
        lines.append(
            f'<line class="tick-mark" x1="{margin_left}" y1="{y}" x2="{margin_left + 6}" y2="{y}"/>'
        )
        lines.append(
            f'<line class="tick-mark" x1="{width - margin_right - 6}" y1="{y}" x2="{width - margin_right}" y2="{y}"/>'
        )

    for x_value in x_ticks:
        x = x_to_svg(x_value)
        lines.append(
            f'<line class="tick-mark" x1="{x}" y1="{height - margin_bottom - 6}" x2="{x}" y2="{height - margin_bottom}"/>'
        )
        lines.append(
            f'<line class="tick-mark" x1="{x}" y1="{margin_top}" x2="{x}" y2="{margin_top + 6}"/>'
        )

    lines.append(
        f'<text class="axis-label" x="{margin_left + plot_width / 2}" y="{height - 16}" text-anchor="middle">{x_label}</text>'
    )
    lines.append(
        f'<text class="axis-label" x="20" y="{margin_top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 20 {margin_top + plot_height / 2})">{y_label}</text>'
    )

    polyline_points = " ".join(
        f"{x_to_svg(point['x'])},{y_to_svg(point['mean'])}" for point in series
    )
    lines.append(f'<polyline class="line" points="{polyline_points}" stroke="{line_color}"/>')

    for point in series:
        x = x_to_svg(point["x"])
        y = y_to_svg(point["mean"])

        # Draw MATLAB-like plus markers.
        lines.append(
            f'<line class="marker" x1="{x - 4}" y1="{y}" x2="{x + 4}" y2="{y}" stroke="{line_color}"/>'
        )
        lines.append(
            f'<line class="marker" x1="{x}" y1="{y - 4}" x2="{x}" y2="{y + 4}" stroke="{line_color}"/>'
        )

    legend_text_x = width - margin_right - 120
    legend_line_x1 = width - margin_right - 64
    legend_line_x2 = width - margin_right - 14
    legend_y = margin_top + 18
    lines.append(
        f'<text class="legend" x="{legend_text_x}" y="{legend_y + 4}" text-anchor="start">{legend_label}</text>'
    )
    lines.append(
        f'<line x1="{legend_line_x1}" y1="{legend_y}" x2="{legend_line_x2}" y2="{legend_y}" stroke="{line_color}" stroke-width="2"/>'
    )
    marker_mid_x = (legend_line_x1 + legend_line_x2) / 2
    lines.append(
        f'<line class="marker" x1="{marker_mid_x - 4}" y1="{legend_y}" x2="{marker_mid_x + 4}" y2="{legend_y}" stroke="{line_color}"/>'
    )
    lines.append(
        f'<line class="marker" x1="{marker_mid_x}" y1="{legend_y - 4}" x2="{marker_mid_x}" y2="{legend_y + 4}" stroke="{line_color}"/>'
    )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def aggregate_rows(input_csv):
    groups = defaultdict(lambda: {"loss": [], "delay": [], "wall_clock": []})

    with input_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            node_count = int(row["num_vehicles"])
            groups[node_count]["loss"].append(float(row["packet_loss_ratio"]))
            groups[node_count]["delay"].append(float(row["mean_rba_end_to_end_delay_ms"]))
            wall_clock_elapsed = row.get("wall_clock_elapsed_s", "")
            if wall_clock_elapsed:
                groups[node_count]["wall_clock"].append(float(wall_clock_elapsed))

    summary = []
    for node_count in sorted(groups):
        loss_values = groups[node_count]["loss"]
        delay_values = groups[node_count]["delay"]
        wall_clock_values = groups[node_count]["wall_clock"]
        wall_clock_summary = summarize_optional(wall_clock_values)
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
                "wall_clock_elapsed_s_sum": wall_clock_summary["sum"],
                "wall_clock_elapsed_s_mean": wall_clock_summary["mean"],
                "wall_clock_elapsed_s_stddev": wall_clock_summary["stddev"],
                "wall_clock_elapsed_s_min": wall_clock_summary["min"],
                "wall_clock_elapsed_s_max": wall_clock_summary["max"],
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
        "wall_clock_elapsed_s_sum",
        "wall_clock_elapsed_s_mean",
        "wall_clock_elapsed_s_stddev",
        "wall_clock_elapsed_s_min",
        "wall_clock_elapsed_s_max",
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
    loss_observed_min = min(point["mean"] - point["stddev"] for point in loss_series)
    if loss_observed_min >= 0.4:
        loss_axis_min = max(loss_axis_min, 0.4)
        _, loss_axis_max, loss_ticks = nice_axis_bounds(
            loss_axis_min,
            max(point["mean"] + point["stddev"] for point in loss_series),
            target_ticks=8,
            include_zero=False,
        )
    delay_observed_max = max(point["mean"] + point["stddev"] for point in delay_series)
    delay_axis_max = nice_axis_max(delay_observed_max)
    if delay_observed_max <= 100.0:
        delay_axis_max = min(delay_axis_max, 100.0)
    _, _, delay_ticks = nice_axis_bounds(
        0.0,
        delay_axis_max,
        target_ticks=6,
        include_zero=True,
    )

    write_svg_plot(
        loss_svg,
        "Network Performance vs Node Count",
        "Packet Loss Ratio vs Node Count",
        "Node Count",
        "Packet Loss Ratio",
        "Packet Loss",
        "#ff0000",
        loss_series,
        loss_axis_min,
        loss_axis_max,
        loss_ticks,
    )
    write_svg_plot(
        delay_svg,
        "Network Performance vs Node Count",
        "End-to-End Delay vs Node Count",
        "Node Count",
        "End-to-End Delay (ms)",
        "Delay",
        "#0000ff",
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
