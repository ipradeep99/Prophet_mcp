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
import re
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


def extract_chartjs_config(text):
    """Extract the Chart.js config dict from the tool's text output."""
    match = re.search(r'chartjs\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if match:
        config_str = match.group(1)
        config_str = config_str.replace("True", "true").replace("False", "false").replace("None", "null")
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            config_str = re.sub(r',\s*}', '}', config_str)
            config_str = re.sub(r',\s*]', ']', config_str)
            return json.loads(config_str)
    return None


def generate_html(chartjs_config, title="Prophet Forecast"):
    """Generate an HTML page with Chart.js rendering the forecast."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .chart-container {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 30px;
            width: 90%;
            max-width: 900px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            color: #e0e0e0;
            text-align: center;
            margin-bottom: 20px;
            font-size: 1.5rem;
            font-weight: 300;
            letter-spacing: 1px;
        }}
        canvas {{ max-height: 500px; }}
    </style>
</head>
<body>
    <div class="chart-container">
        <h1>📈 {title}</h1>
        <canvas id="forecastChart"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('forecastChart').getContext('2d');
        const config = {json.dumps(chartjs_config, indent=2)};

        config.options = config.options || {{}};
        config.options.responsive = true;
        config.options.plugins = {{
            legend: {{
                labels: {{
                    color: '#ccc',
                    font: {{ size: 13 }},
                    usePointStyle: true,
                    filter: function(item) {{
                        return !item.text.includes('Confidence');
                    }}
                }}
            }},
            tooltip: {{
                backgroundColor: 'rgba(0,0,0,0.8)',
                titleColor: '#fff',
                bodyColor: '#ddd',
                cornerRadius: 8,
                padding: 12
            }}
        }};
        config.options.scales = {{
            x: {{
                ticks: {{ color: '#aaa', maxRotation: 45, font: {{ size: 11 }} }},
                grid: {{ color: 'rgba(255,255,255,0.05)' }}
            }},
            y: {{
                beginAtZero: false,
                ticks: {{ color: '#aaa', font: {{ size: 11 }} }},
                grid: {{ color: 'rgba(255,255,255,0.08)' }}
            }}
        }};

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
            text = content[0].get("text", "")

            # Print the summary
            if "chartjs" in text:
                summary = text[:text.index("chartjs")].strip()
            else:
                summary = text
            print("Response Summary:")
            print("-" * 60)
            print(summary)
            print()

            # Generate and open the Chart.js visualization
            chartjs_config = extract_chartjs_config(text)
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

