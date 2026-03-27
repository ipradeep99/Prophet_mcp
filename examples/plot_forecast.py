import requests
import json
import webbrowser
import os

def call_tool_with_args(base_url="http://localhost:3000", token=None):
    """
    Calls /mcp endpoint with tools/call → forecast_time_series.
    Token is read from MCP_TOKEN environment variable.
    """
    if token is None:
        token = os.environ.get("MCP_TOKEN", "")
    if not token:
        raise ValueError("MCP token missing. Set MCP_TOKEN env var or pass token=...")
    url = f"{base_url}/mcp"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    
    # Forecast payload
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "forecast_time_series",
            "arguments": {
                "ds": [
                    "2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05",
                    "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10"
                ],
                "y": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
                "periods": 5,
                "growth": "logistic",
                "cap": 25,
                "floor": 5
            }
        },
        "id": 1
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error calling API: {e}")
        return None


def extract_chartjs_config(content_items):
    """
    Extract the Chart.js config dict from the MCP response content items.
    The new format returns chartjs config in content[1] as:
      'chartjs_config:{...json...}'
    """
    for item in content_items:
        text = item.get("text", "")
        if text.startswith("chartjs_config:"):
            json_str = text[len("chartjs_config:"):]
            return json.loads(json_str)
    return None


def generate_html(chartjs_config, title="Prophet Forecast"):
    """
    Generate a premium HTML page with Chart.js rendering the forecast.
    Handles the annotation plugin and replaces filter function placeholders.
    """
    config_json = json.dumps(chartjs_config, indent=2)
    config_json = config_json.replace(
        '"__FILTER_FN__"',
        'function(item) { return !item.text.includes("Confidence") && !item.text.includes("Fitted"); }'
    )
    config_json = config_json.replace(
        '"__TOOLTIP_FILTER_FN__"',
        'function(tooltipItem) { return !tooltipItem.dataset.label.includes("Confidence"); }'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation"></script>
    <style>
        * {{{{ margin: 0; padding: 0; box-sizing: border-box; }}}}
        body {{{{
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: linear-gradient(145deg, #0b1120 0%, #131b2e 35%, #1a1040 70%, #0f0c29 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}}}
        .chart-wrapper {{{{
            width: 95%;
            max-width: 1000px;
        }}}}
        .chart-header {{{{
            text-align: center;
            margin-bottom: 24px;
        }}}}
        .chart-header h1 {{{{
            color: rgba(226, 232, 240, 0.95);
            font-size: 1.4rem;
            font-weight: 500;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}}}
        .chart-header p {{{{
            color: rgba(148, 163, 184, 0.6);
            font-size: 0.82rem;
            font-weight: 300;
        }}}}
        .chart-container {{{{
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(99, 102, 241, 0.12);
            border-radius: 20px;
            padding: 32px 28px 24px;
            box-shadow:
                0 4px 24px rgba(0, 0, 0, 0.25),
                0 0 80px rgba(99, 102, 241, 0.04),
                inset 0 1px 0 rgba(255, 255, 255, 0.04);
            position: relative;
            overflow: hidden;
        }}}}
        .chart-container::before {{{{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg,
                transparent,
                rgba(99, 102, 241, 0.3),
                rgba(79, 142, 247, 0.3),
                transparent
            );
        }}}}
        canvas {{{{
            max-height: 480px;
        }}}}
        .chart-footer {{{{
            text-align: center;
            margin-top: 16px;
            color: rgba(148, 163, 184, 0.35);
            font-size: 0.72rem;
            font-weight: 300;
        }}}}
    </style>
</head>
<body>
    <div class="chart-wrapper">
        <div class="chart-header">
            <h1>{title}</h1>
            <p>Generated by Prophet MCP Server</p>
        </div>
        <div class="chart-container">
            <canvas id="forecastChart"></canvas>
        </div>
        <div class="chart-footer">
            Powered by Meta Prophet &middot; Chart.js
        </div>
    </div>
    <script>
        const ctx = document.getElementById('forecastChart').getContext('2d');
        const config = {config_json};
        new Chart(ctx, config);
    </script>
</body>
</html>"""



# ===== Main =====
if __name__ == "__main__":
    print("Fetching forecast data...")
    result = call_tool_with_args()

    if result and "result" in result:
        try:
            content = result["result"]["content"]
            summary = content[0].get("text", "")
            print(summary[:500])
            print()

            # Extract Chart.js config from content[1]
            chartjs_config = extract_chartjs_config(content)

            if chartjs_config:
                html = generate_html(chartjs_config, title="Prophet Forecast: Daily Conversions")

                # Save and open in browser
                output_path = os.path.join(os.path.dirname(__file__), "forecast_chart.html")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html)

                print(f"Chart saved to: {output_path}")
                webbrowser.open(f"file://{os.path.abspath(output_path)}")
                print("Opened in browser!")
            else:
                print("Could not extract Chart.js config from response.")
                print("Make sure the server is returning the new two-content-item format.")

        except Exception as e:
            print(f"Error: {e}")
    else:
        print("API call failed or returned invalid result.")
