"""
Real-World Marketing Forecast Test
===================================
Scenario: An e-commerce marketing team tracked daily website conversions
over 30 days (a full month). They want to forecast the next 7 days to plan
their ad spend and staffing.

The data simulates realistic patterns:
- Weekday/weekend fluctuations
- A gradual upward trend from a new campaign launch
- Some natural noise

We use LOGISTIC growth because conversions have a natural ceiling
(team can process max ~120 orders/day) and floor (baseline organic ~30/day).
"""

import requests
import json
import os
import webbrowser


def call_tool_with_args(base_url=None, token=None):
    """
    Calls /mcp endpoint with tools/call → forecast_time_series.
    Tests a real-world marketing scenario: 30 days of daily conversions
    forecasted for the next 7 days with logistic growth.
    """
    if base_url is None:
        base_url = os.environ.get("MCP_BASE_URL", "http://localhost:3000")
    if token is None:
        token = os.environ.get("MCP_TOKEN", "")
    if not token:
        raise ValueError("MCP token missing. Set MCP_TOKEN env var or pass token=...")

    url = f"{base_url}/mcp"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Real-world data: 30 days of daily e-commerce conversions
    # Pattern: weekday highs (~60-90), weekend dips (~40-55), upward trend from new campaign
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "forecast_time_series",
            "arguments": {
                "ds": [
                    "2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04", "2025-02-05",
                    "2025-02-06", "2025-02-07", "2025-02-08", "2025-02-09", "2025-02-10",
                    "2025-02-11", "2025-02-12", "2025-02-13", "2025-02-14", "2025-02-15",
                    "2025-02-16", "2025-02-17", "2025-02-18", "2025-02-19", "2025-02-20",
                    "2025-02-21", "2025-02-22", "2025-02-23", "2025-02-24", "2025-02-25",
                    "2025-02-26", "2025-02-27", "2025-02-28", "2025-03-01", "2025-03-02"
                ],
                "y": [
                    42, 38, 55, 61, 63, 58, 48,   # Week 1: campaign just launched
                    45, 40, 62, 68, 72, 65, 52,   # Week 2: gaining traction
                    50, 44, 70, 75, 78, 71, 56,   # Week 3: growing steadily
                    54, 48, 76, 82, 85, 79, 60,   # Week 4: strong performance
                    58, 52                         # Start of week 5 (weekend)
                ],
                "periods": 7,
                "growth": "logistic",
                "cap": 120,
                "floor": 30
            }
        },
        "id": 1
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.status_code, resp.json()
    except Exception as e:
        return None, f"Error: {str(e)}"


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
    # Serialize config to JSON, then replace placeholder strings with real JS functions
    config_json = json.dumps(chartjs_config, indent=2)
    # These placeholders are used because JSON can't contain JS functions
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
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: linear-gradient(145deg, #0b1120 0%, #131b2e 35%, #1a1040 70%, #0f0c29 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .chart-wrapper {{
            width: 95%;
            max-width: 1000px;
        }}
        .chart-header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .chart-header h1 {{
            color: rgba(226, 232, 240, 0.95);
            font-size: 1.4rem;
            font-weight: 500;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .chart-header p {{
            color: rgba(148, 163, 184, 0.6);
            font-size: 0.82rem;
            font-weight: 300;
        }}
        .chart-container {{
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
        }}
        .chart-container::before {{
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
        }}
        canvas {{
            max-height: 480px;
        }}
        .chart-footer {{
            text-align: center;
            margin-top: 16px;
            color: rgba(148, 163, 184, 0.35);
            font-size: 0.72rem;
            font-weight: 300;
        }}
    </style>
</head>
<body>
    <div class="chart-wrapper">
        <div class="chart-header">
            <h1>📈 {title}</h1>
            <p>Generated by Prophet MCP Server</p>
        </div>
        <div class="chart-container">
            <canvas id="forecastChart"></canvas>
        </div>
        <div class="chart-footer">
            Powered by Meta Prophet · Chart.js
        </div>
    </div>
    <script>
        const ctx = document.getElementById('forecastChart').getContext('2d');
        const config = {config_json};
        new Chart(ctx, config);
    </script>
</body>
</html>"""


if __name__ == "__main__":
    print("=" * 60)
    print("  Prophet MCP — Real-World Marketing Forecast Test")
    print("  Endpoint: GCP Cloud Run")
    print("=" * 60)
    print()
    print("Scenario: 30 days of daily e-commerce conversions")
    print("  Growth: logistic (cap=120, floor=30)")
    print("  Forecast: next 7 days")
    print()
    print("Calling deployed MCP server...")
    print()

    status, result = call_tool_with_args()

    print(f"Status Code: {status}")
    print()

    if isinstance(result, dict) and "result" in result:
        content = result["result"].get("content", [])
        if content:
            # content[0] = text summary, content[1] = chartjs_config JSON
            summary = content[0].get("text", "")
            print("Response Summary:")
            print("-" * 60)
            print(summary)
            print()

            # Extract Chart.js config from content[1]
            chartjs_config = extract_chartjs_config(content)
            if chartjs_config:
                html = generate_html(chartjs_config, title="Marketing Forecast: Daily Conversions (Logistic Growth)")
                output_path = os.path.join(os.path.dirname(__file__), "marketing_forecast.html")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[Chart] Saved to: {output_path}")
                webbrowser.open(f"file://{os.path.abspath(output_path)}")
                print("[Chart] Opened in browser!")
            else:
                print("[Warning] Could not extract Chart.js config from response.")
        else:
            print("No content in response.")
    else:
        print(f"Response: {json.dumps(result, indent=2)}")

