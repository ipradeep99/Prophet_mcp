import json
import pandas as pd
from prophet import Prophet

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
        "serverInfo": {"name": "prophet_mcp", "version": "0.1.0"},
        "capabilities": {"tools": {}},
    }


def handle_tools_list():
    """
    For JSON-RPC MCP, schema field is camelCase: inputSchema
    Keep only ds, y, f (future periods).
    """
    return {
        "tools": [
            {
                "name": "forecast_time_series",
                "description": "Runs a simple Prophet forecast on ds/y and returns ds + yhat/yhat_lower/yhat_upper.",
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
        return {"content": [{"type": "text", "text": json.dumps(data)}]}

    return {
        "isError": True,
        "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}],
    }


def forecast_time_series(arguments):
    """
    Input:
      - ds: list[str]  (dates)
      - y:  list[float]
      - f:  int (future periods, optional)

    Output:
      - JSON-serializable dict with forecast rows
    """

    print(arguments)
    ds = arguments.get("ds")
    y = arguments.get("y")
    f = int(arguments.get("periods", 10))
    #Transform the ds to a datetime object
    df = pd.DataFrame({
    'ds': ds,
    'y': y
})
    df["ds"]=pd.to_datetime(df["ds"])


    try:
        model = Prophet()
        model.fit(df)

        future = model.make_future_dataframe(periods=f)
        forecast = model.predict(future)
        print(forecast.tail())
    except Exception as e:
        return {"error": str(e)}

    out = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    out["ds"] = out["ds"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "meta": {
            "f": f,
            "n_history": int(df.shape[0]),
            "start": df["ds"].min().strftime("%Y-%m-%dT%H:%M:%S"),
            "end": df["ds"].max().strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "forecast": out.to_dict(orient="records"),
    }
