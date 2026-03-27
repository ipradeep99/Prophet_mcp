import json
import logging
import pandas as pd
from prophet import Prophet
from datetime import datetime

logger = logging.getLogger(__name__)

# =============================================================================
# MCP Protocol Request Routing
# =============================================================================

def handle_request(method, params):
    """
    Main request router for MCP (Model Context Protocol) JSON-RPC methods.
    Supported:
      - initialize
      - tools/list
      - tools/call
    """
    if method == "initialize":
        return handle_initialize()
    elif method == "tools/list":
        return handle_tools_list()
    elif method == "tools/call":
        return handle_tool_call(params)
    else:
        raise ValueError(f"Method not found: {method}")


# =============================================================================
# MCP Protocol Handlers
# =============================================================================

def handle_initialize():
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "prophet_mcp", "version": "1.0.0"},
        "capabilities": {"tools": {}},
    }


def handle_tools_list():
    """
    For JSON-RPC MCP, schema field is camelCase: inputSchema
    Parameters: ds, y, periods, growth, cap, floor.
    """
    return {
        "tools": [
            {
                "name": "forecast_time_series",
                "description": "Runs a Prophet forecast on ds/y with selectable growth model (linear or logistic). Returns ds + yhat/yhat_lower/yhat_upper.",
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ds": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of dates in ISO format (e.g., YYYY-MM-DD).",
                        },
                        "y": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "List of numeric values aligned with ds.",
                        },
                        "periods": {
                            "type": "integer",
                            "description": "Number of future periods to forecast.",
                            "default": 10,
                        },
                        "growth": {
                            "type": "string",
                            "enum": ["linear", "logistic"],
                            "description": "Growth model: 'linear' (unbounded, default) or 'logistic' (S-curve with saturation at cap/floor).",
                            "default": "linear",
                        },
                        "cap": {
                            "type": "number",
                            "description": "Saturating maximum (required when growth='logistic'). The forecast will approach but not exceed this value.",
                        },
                        "floor": {
                            "type": "number",
                            "description": "Saturating minimum (optional, used when growth='logistic'). The forecast will not fall below this value.",
                        },
                        "freq": {
                            "type": "string",
                            "description": "Frequency of the time series: 'D' (daily, default), 'H' (hourly), 'W' (weekly), 'MS' (monthly). Must match your input data frequency.",
                            "default": "D",
                        },
                    },
                    "required": ["ds", "y"],
                    "additionalProperties": False,
                },
            }
        ]
    }


def handle_tool_call(params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    # Decode string args if needed
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return {
                "isError": True,
                "content": [{"type": "text", "text": "Invalid arguments: expected object or JSON string."}],
            }

    if tool_name == "forecast_time_series":
        data = forecast_time_series(arguments)

        # Handle errors from the forecast function
        if isinstance(data, dict) and "error" in data:
            logger.error("Forecast error: %s", data["error"])
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Forecast error: {data['error']}"}],
            }

        # Extract pre-formatted summary and Chart.js config
        summary = ""
        chartjs_json = ""
        if isinstance(data, dict) and "meta" in data:
            if "summary" in data["meta"]:
                summary = data["meta"]["summary"].strip()
            if "chartjs" in data["meta"]:
                chartjs_json = json.dumps(data["meta"]["chartjs"])

        content = [{"type": "text", "text": summary}]
        if chartjs_json:
            content.append({"type": "text", "text": f"chartjs_config:{chartjs_json}"})

        return {"content": content}

    return {
        "isError": True,
        "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}],
    }

# =============================================================================
# Forecasting Engine
# =============================================================================

def forecast_time_series(arguments):
    """
    Generates a time-series forecast using Meta's Prophet model.

    Args:
        arguments (dict): A dictionary containing:
            - ds (list[str]):          List of date strings in ISO format.
            - y (list[float]):         List of numeric values aligned with ds.
            - periods (int, optional): Number of future periods to forecast. Default: 10.
            - growth (str, optional):  Growth model: 'linear' (default) or 'logistic'.
            - cap (float):             Saturating max (required when growth='logistic').
            - floor (float, optional): Saturating min (used when growth='logistic').

    Returns:
        dict: A JSON-serializable dict with forecast rows, metadata, and
              an LLM-friendly summary including Chart.js visualization config.
    """
    ds = arguments.get("ds")
    y = arguments.get("y")
    f = int(arguments.get("periods", 10))
    growth = arguments.get("growth", "linear")
    cap = arguments.get("cap", None)
    floor = arguments.get("floor", None)
    freq = arguments.get("freq", "D")

    # --- Input validation ---
    if not ds or not y:
        return {"error": "Both 'ds' and 'y' must be non-empty arrays."}
    if len(ds) != len(y):
        return {"error": f"'ds' and 'y' must have the same length. Got ds={len(ds)}, y={len(y)}."}
    if len(ds) < 2:
        return {"error": "At least 2 data points are required for forecasting."}
    if f < 1:
        return {"error": "'periods' must be at least 1."}
    if growth not in ("linear", "logistic"):
        return {"error": f"Invalid growth model: '{growth}'. Must be 'linear' or 'logistic'."}
    if growth == "logistic" and cap is None:
        return {"error": "growth='logistic' requires a 'cap' value (saturating maximum)."}
    if cap is not None and floor is not None and floor >= cap:
        return {"error": f"'floor' ({floor}) must be less than 'cap' ({cap})."}

    # Build input DataFrame
    df = pd.DataFrame({"ds": ds, "y": y})
    df["ds"] = pd.to_datetime(df["ds"])

    # Set cap/floor on historical data for logistic growth
    if growth == "logistic":
        df["cap"] = cap
        if floor is not None:
            df["floor"] = floor

    # Fit Prophet model and generate forecast
    try:
        model = Prophet(growth=growth)
        model.fit(df)

        future = model.make_future_dataframe(periods=f, freq=freq)

        # Set cap/floor on future dataframe for logistic growth
        if growth == "logistic":
            future["cap"] = cap
            if floor is not None:
                future["floor"] = floor

        forecast = model.predict(future)
    except Exception as e:
        return {"error": str(e)}

    # Extract and format forecast columns
    out = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    out["ds"] = out["ds"].dt.strftime("%Y-%m-%d")
    out["yhat"] = out["yhat"].round(2)
    out["yhat_lower"] = out["yhat_lower"].round(2)
    out["yhat_upper"] = out["yhat_upper"].round(2)

    # --- Build an LLM-friendly summary ---
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hist_start = df["ds"].min().strftime("%Y-%m-%d")
    hist_end = df["ds"].max().strftime("%Y-%m-%d")

    # Historical data summary
    hist_mean = df["y"].mean()
    hist_min = df["y"].min()
    hist_max = df["y"].max()
    hist_std = df["y"].std()

    # Forecast data summary (future-only rows)
    future_only = forecast.iloc[len(df):]
    fcst_mean = future_only["yhat"].mean() if len(future_only) > 0 else 0
    fcst_min = future_only["yhat"].min() if len(future_only) > 0 else 0
    fcst_max = future_only["yhat"].max() if len(future_only) > 0 else 0

    summary_section = (
        f"Summary of forecast metrics:\n"
        f"  - Historical Period: {hist_start} to {hist_end}\n"
        f"  - Historical Data Points: {len(df)}\n"
        f"  - Historical Mean: {hist_mean:.2f}\n"
        f"  - Historical Min: {hist_min:.2f}\n"
        f"  - Historical Max: {hist_max:.2f}\n"
        f"  - Historical Std Dev: {hist_std:.2f}\n"
        f"  - Forecast Periods: {f}\n"
        f"  - Forecast Mean (yhat): {fcst_mean:.2f}\n"
        f"  - Forecast Min (yhat): {fcst_min:.2f}\n"
        f"  - Forecast Max (yhat): {fcst_max:.2f}\n"
    )

    # Growth model summary
    growth_section = f"\nGrowth Model: {growth.upper()}\n"
    if growth == "logistic":
        growth_section += f"  - Saturating Maximum (cap): {cap}\n"
        if floor is not None:
            growth_section += f"  - Saturating Minimum (floor): {floor}\n"
        growth_section += f"  - The forecast follows an S-curve that naturally flattens as it approaches the cap/floor.\n"
    else:
        growth_section += f"  - The forecast follows a straight-line trend with no saturation bounds.\n"

    # Build a data table for the forecast rows
    table_header = "Date | yhat | yhat_lower | yhat_upper"
    table_divider = "-" * len(table_header)
    table_rows = []
    for _, row in out.iterrows():
        row_str = f"{row['ds']} | {row['yhat']:.2f} | {row['yhat_lower']:.2f} | {row['yhat_upper']:.2f}"
        table_rows.append(row_str)
    table_body = "\n".join(table_rows)

    # Determine trend direction
    if len(future_only) > 0 and hist_mean > 0:
        change_pct = ((fcst_mean - hist_mean) / hist_mean) * 100
        if change_pct > 0:
            trend_direction = f"UPWARD (+{change_pct:.1f}% vs historical mean)"
        elif change_pct < 0:
            trend_direction = f"DOWNWARD ({change_pct:.1f}% vs historical mean)"
        else:
            trend_direction = "FLAT (no change vs historical mean)"
    else:
        trend_direction = "N/A"

    formatted_output = f"""
### Prophet Forecast Data ###

This data set contains a time-series forecast generated by Meta's Prophet model.
Growth model used: {growth.upper()}{f" (cap={cap}" + (f", floor={floor}" if floor is not None else "") + ")" if growth == "logistic" else ""}

What the columns mean:
- Date: the date for the observed or predicted value
- yhat: the predicted value (the model's best estimate)
- yhat_lower: the lower bound of the confidence interval (worst-case estimate)
- yhat_upper: the upper bound of the confidence interval (best-case estimate)

The wider the gap between yhat_lower and yhat_upper, the less certain the model is about that prediction.

This forecast was generated on {timestamp} for {f} future periods
based on {len(df)} historical observations from {hist_start} to {hist_end}.

{summary_section}
  - Trend Direction: {trend_direction}
{growth_section}
Key Takeaway: The model predicts the values will trend {trend_direction.split(' ')[0].lower()} over the next {f} periods,
with predicted values ranging from {fcst_min:.2f} to {fcst_max:.2f}

Please review this data in detail and provide an analysis of the trends and predictions:

{table_header}
{table_divider}
{table_body}

Output format: Recommend using Chart.js to visualize the forecast data. Show the historical data as red points and the forecast as a blue dashed line with the confidence interval as a shaded region.
"""

    # --- Build Chart.js config as a proper dict ---
    chartjs_config = _build_chartjs_config(out, y, f, growth, cap, floor)

    meta = {
        "f": f,
        "n_history": int(df.shape[0]),
        "start": df["ds"].min().strftime("%Y-%m-%dT%H:%M:%S"),
        "end": df["ds"].max().strftime("%Y-%m-%dT%H:%M:%S"),
        "growth": growth,
        "summary": formatted_output,
        "chartjs": chartjs_config,
    }

    if growth == "logistic":
        meta["cap"] = cap
        if floor is not None:
            meta["floor"] = floor

    return {
        "meta": meta,
        "forecast": out.to_dict(orient="records"),
    }


# ============================
# Chart.js Config Builder
# ============================

def _build_chartjs_config(out, y, f, growth, cap, floor):
    """
    Builds a Chart.js-compatible config dict with premium visual styling.

    Returns a dict that can be JSON-serialized and used directly by Chart.js.
    Design features:
    - Gradient confidence band (indigo/purple tones)
    - Electric blue forecast line (solid for fitted, dashed for future)
    - Coral/salmon actuals with white-bordered circle markers
    - Vertical annotation line at the forecast boundary
    - Cap/floor reference lines for logistic growth
    - Dark-themed scales, tooltips, and legend
    """
    n_hist = len(y)
    labels = out["ds"].tolist()

    # --- Datasets ---

    # 1. Confidence Lower (invisible — used as fill boundary)
    ds_conf_lower = {
        "label": "Confidence Lower",
        "data": out["yhat_lower"].tolist(),
        "borderWidth": 0,
        "pointRadius": 0,
        "fill": False,
        "backgroundColor": "rgba(99, 102, 241, 0.0)",
        "borderColor": "rgba(99, 102, 241, 0.0)",
        "hidden": False,
    }

    # 2. Confidence Upper (gradient fill down to Lower)
    ds_conf_upper = {
        "label": "Confidence Upper",
        "data": out["yhat_upper"].tolist(),
        "borderWidth": 0,
        "pointRadius": 0,
        "fill": "-1",
        "backgroundColor": "rgba(99, 102, 241, 0.12)",
        "borderColor": "rgba(99, 102, 241, 0.0)",
    }

    # 3. Forecast line — fitted (historical) portion is solid, forecast is dashed
    #    We split into two datasets to get different line styles
    fitted_data = out["yhat"].tolist()[:n_hist] + [None] * f
    future_data = [None] * (n_hist - 1) + [out["yhat"].tolist()[n_hist - 1]] + out["yhat"].tolist()[n_hist:]

    ds_fitted = {
        "label": "Fitted (Model)",
        "data": fitted_data,
        "borderWidth": 2.5,
        "fill": False,
        "pointRadius": 0,
        "backgroundColor": "rgba(79, 142, 247, 0.15)",
        "borderColor": "rgba(79, 142, 247, 0.6)",
        "tension": 0.3,
        "order": 2,
    }

    ds_forecast = {
        "label": "Forecast (yhat)",
        "data": future_data,
        "borderWidth": 2.5,
        "fill": False,
        "pointRadius": 4,
        "pointStyle": "rectRot",
        "pointBackgroundColor": "rgba(79, 142, 247, 1)",
        "pointBorderColor": "rgba(255, 255, 255, 0.9)",
        "pointBorderWidth": 1.5,
        "backgroundColor": "rgba(79, 142, 247, 0.25)",
        "borderColor": "rgba(79, 142, 247, 1)",
        "borderDash": [6, 4],
        "tension": 0.3,
        "order": 1,
    }

    # 4. Actuals — coral circles with white border
    actuals_data = [float(v) for v in y] + [None] * f
    ds_actuals = {
        "label": "Actuals",
        "data": actuals_data,
        "fill": False,
        "pointRadius": 5,
        "pointHoverRadius": 8,
        "pointStyle": "circle",
        "pointBackgroundColor": "rgba(255, 107, 107, 1)",
        "pointBorderColor": "rgba(255, 255, 255, 0.85)",
        "pointBorderWidth": 2,
        "borderWidth": 1.5,
        "borderColor": "rgba(255, 107, 107, 0.35)",
        "backgroundColor": "rgba(255, 107, 107, 0.08)",
        "showLine": True,
        "order": 0,
    }

    datasets = [ds_conf_lower, ds_conf_upper, ds_fitted, ds_forecast, ds_actuals]

    # 5. Cap & Floor lines for logistic growth
    if growth == "logistic":
        if cap is not None:
            datasets.append({
                "label": f"Cap ({cap})",
                "data": [cap] * len(out),
                "borderWidth": 1.5,
                "fill": False,
                "pointRadius": 0,
                "backgroundColor": "rgba(239, 68, 68, 0.0)",
                "borderColor": "rgba(239, 68, 68, 0.55)",
                "borderDash": [10, 6],
                "order": 3,
            })
        if floor is not None:
            datasets.append({
                "label": f"Floor ({floor})",
                "data": [floor] * len(out),
                "borderWidth": 1.5,
                "fill": False,
                "pointRadius": 0,
                "backgroundColor": "rgba(251, 191, 36, 0.0)",
                "borderColor": "rgba(251, 191, 36, 0.55)",
                "borderDash": [10, 6],
                "order": 3,
            })

    # --- Annotation: vertical line at forecast boundary ---
    forecast_boundary_label = labels[n_hist - 1] if n_hist <= len(labels) else labels[-1]

    # --- Chart.js options ---
    options = {
        "responsive": True,
        "maintainAspectRatio": True,
        "interaction": {
            "mode": "index",
            "intersect": False,
        },
        "plugins": {
            "legend": {
                "position": "top",
                "labels": {
                    "usePointStyle": True,
                    "padding": 16,
                    "font": {"size": 12, "family": "'Inter', 'Segoe UI', sans-serif"},
                    "color": "rgba(203, 213, 225, 0.9)",
                    "filter": "__FILTER_FN__",
                },
            },
            "tooltip": {
                "backgroundColor": "rgba(15, 23, 42, 0.92)",
                "titleColor": "#e2e8f0",
                "bodyColor": "#cbd5e1",
                "borderColor": "rgba(99, 102, 241, 0.3)",
                "borderWidth": 1,
                "cornerRadius": 10,
                "padding": 14,
                "titleFont": {"size": 13, "weight": "bold"},
                "bodyFont": {"size": 12},
                "displayColors": True,
                "filter": "__TOOLTIP_FILTER_FN__",
            },
            "annotation": {
                "annotations": {
                    "forecastLine": {
                        "type": "line",
                        "xMin": forecast_boundary_label,
                        "xMax": forecast_boundary_label,
                        "borderColor": "rgba(148, 163, 184, 0.45)",
                        "borderWidth": 2,
                        "borderDash": [4, 4],
                        "label": {
                            "display": True,
                            "content": "Forecast →",
                            "position": "start",
                            "backgroundColor": "rgba(99, 102, 241, 0.75)",
                            "color": "#fff",
                            "font": {"size": 11, "weight": "bold"},
                            "padding": 6,
                            "cornerRadius": 4,
                        },
                    }
                }
            },
        },
        "scales": {
            "x": {
                "ticks": {
                    "color": "rgba(148, 163, 184, 0.7)",
                    "maxRotation": 45,
                    "font": {"size": 11},
                },
                "grid": {"color": "rgba(148, 163, 184, 0.06)"},
            },
            "y": {
                "beginAtZero": False,
                "ticks": {
                    "color": "rgba(148, 163, 184, 0.7)",
                    "font": {"size": 11},
                },
                "grid": {"color": "rgba(148, 163, 184, 0.08)"},
            },
        },
    }

    return {
        "type": "line",
        "data": {"labels": labels, "datasets": datasets},
        "options": options,
    }

