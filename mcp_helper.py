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

        # Extract pre-formatted summary (includes Chart.js config)
        summary = ""
        if isinstance(data, dict) and "meta" in data and "summary" in data["meta"]:
            summary = data["meta"]["summary"].strip()

        return {"content": [{"type": "text", "text": summary}]}

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

    # Build Chart.js cap/floor line datasets
    limit_datasets = ""
    if growth == "logistic":
        cap_line_data = json.dumps([cap] * len(out))
        limit_datasets += f""",
            {{
                "label": "Cap ({cap})",
                "data": {cap_line_data},
                "borderWidth": 2,
                "fill": false,
                "pointRadius": 0,
                "backgroundColor": "rgba(255, 99, 132, 0.0)",
                "borderColor": "rgba(255, 99, 132, 0.8)",
                "borderDash": [10, 5],
                "order": 2
            }}"""
        if floor is not None:
            floor_line_data = json.dumps([floor] * len(out))
            limit_datasets += f""",
            {{
                "label": "Floor ({floor})",
                "data": {floor_line_data},
                "borderWidth": 2,
                "fill": false,
                "pointRadius": 0,
                "backgroundColor": "rgba(255, 165, 0, 0.0)",
                "borderColor": "rgba(255, 165, 0, 0.8)",
                "borderDash": [10, 5],
                "order": 2
            }}"""

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

Use these Chart.js settings to render the chart:
chartjs = {{
    "type": "line",
    "data": {{
        "labels": {json.dumps(out["ds"].tolist())},
        "datasets": [
            {{
                "label": "Confidence Lower",
                "data": {json.dumps(out["yhat_lower"].tolist())},
                "borderWidth": 0,
                "pointRadius": 0,
                "fill": false,
                "backgroundColor": "rgba(54, 162, 235, 0.0)",
                "borderColor": "rgba(54, 162, 235, 0.0)",
                "hidden": false
            }},
            {{
                "label": "Confidence Upper",
                "data": {json.dumps(out["yhat_upper"].tolist())},
                "borderWidth": 0,
                "pointRadius": 0,
                "fill": "-1",
                "backgroundColor": "rgba(54, 162, 235, 0.15)",
                "borderColor": "rgba(54, 162, 235, 0.0)"
            }},
            {{
                "label": "Forecast (yhat)",
                "data": {json.dumps(out["yhat"].tolist())},
                "borderWidth": 2,
                "fill": false,
                "pointRadius": 0,
                "backgroundColor": "rgba(54, 162, 235, 0.2)",
                "borderColor": "rgba(54, 162, 235, 0.8)",
                "borderDash": [5, 5],
                "order": 1
            }},
            {{
                "label": "Actuals",
                "data": {json.dumps(([float(v) for v in y] + [None] * f))},
                "fill": false,
                "pointRadius": 6,
                "pointHoverRadius": 8,
                "borderWidth": 0,
                "backgroundColor": "rgba(255, 107, 107, 1)",
                "borderColor": "rgba(255, 107, 107, 0.0)",
                "order": 0
            }}{limit_datasets}
        ]
    }},
    "options": {{
        "responsive": true,
        "plugins": {{
            "legend": {{
                "labels": {{
                    "filter": "function(item) {{ return !item.text.includes('Confidence'); }}"
                }}
            }}
        }},
        "scales": {{
            "y": {{
                "beginAtZero": true
            }}
        }}
    }}
}}

"""

    meta = {
        "f": f,
        "n_history": int(df.shape[0]),
        "start": df["ds"].min().strftime("%Y-%m-%dT%H:%M:%S"),
        "end": df["ds"].max().strftime("%Y-%m-%dT%H:%M:%S"),
        "growth": growth,
        "summary": formatted_output,
    }

    if growth == "logistic":
        meta["cap"] = cap
        if floor is not None:
            meta["floor"] = floor

    return {
        "meta": meta,
        "forecast": out.to_dict(orient="records"),
    }

