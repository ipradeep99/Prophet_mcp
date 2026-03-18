import requests
import json
import webbrowser
import os
import re

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


def extract_chartjs_config(text):
    """
    Extract the Chart.js config dict from the tool's text output.
    Looks for the 'chartjs = { ... }' block in the summary.
    """
    # Find the chartjs config block
    match = re.search(r'chartjs\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if match:
        config_str = match.group(1)
        # Convert Python-style booleans/None to JSON
        config_str = config_str.replace("True", "true").replace("False", "false").replace("None", "null")
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            # Try fixing common issues (trailing commas, etc.)
            config_str = re.sub(r',\s*}', '}', config_str)
            config_str = re.sub(r',\s*]', ']', config_str)
            return json.loads(config_str)
    return None


def generate_html(chartjs_config, title="Prophet Forecast"):
    """
    Generate an HTML page with Chart.js rendering the forecast.
    """
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

        // Override chart options for dark theme styling
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
                beginAtZero: true,
                ticks: {{ color: '#aaa', font: {{ size: 11 }} }},
                grid: {{ color: 'rgba(255,255,255,0.08)' }}
            }}
        }};

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
            content_text = result["result"]["content"][0]["text"]

            # Extract Chart.js config from the tool output
            chartjs_config = extract_chartjs_config(content_text)

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
                print("Could not extract Chart.js config from tool output.")
                print("Raw output (first 500 chars):")
                print(content_text[:500])

        except Exception as e:
            print(f"Error: {e}")
    else:
        print("API call failed or returned invalid result.")
