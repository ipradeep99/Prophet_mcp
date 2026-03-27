# Prophet MCP Server

An open-source **Model Context Protocol (MCP)** server engineered for **Time-Series Forecasting**.

Powered by **Meta's Prophet**, this server enables LLMs to generate accurate forecasts, trend analyses, and confidence intervals from historical data — turning raw numbers into actionable insights within AI workflows.

> **Note:** This project is a specialized fork of the [sendgrid-mcp](https://github.com/garethcull/sendgrid-mcp) server, re-engineered to provide robust forecasting capabilities via the MCP protocol.

---

## 🚀 Key Capabilities

### 1. Predictive Modeling
Leverages **Meta's Prophet** to predict future trends based on historical data. Handles seasonality, outliers, and trend changes automatically.

### 2. Growth Model Selection
Choose the right forecasting model for your scenario:
- **Linear** (default): Unbounded straight-line trend — ideal for metrics with no natural ceiling.
- **Logistic** (S-curve): Saturating growth that respects a `cap` (max) and optional `floor` (min) — ideal for metrics like market share, adoption rates, or capacity-limited systems.

### 3. Multi-Frequency Forecasting
Supports daily, hourly, weekly, and monthly time series via the `freq` parameter — use the frequency that matches your input data.

### 4. LLM-Friendly Output
Returns data in a structured, two-part format optimized for Large Language Models:
- **`content[0]` — Text Summary:** Plain-English analysis with trend direction (e.g., *"UPWARD +26.1%"*), statistical breakdowns, growth model details, and a full forecast data table.
- **`content[1]` — Chart.js Config:** A proper JSON payload (`chartjs_config:{...}`) ready for visualization — no regex parsing needed.

### 5. Premium Interactive Visualization
Every response includes a Chart.js configuration with:
- 🟣 Indigo gradient **confidence band** (shaded between upper/lower bounds)
- 🔵 Solid blue **fitted line** for historical model fit
- 🔵 Dashed blue **forecast line** with diamond markers for future predictions
- 🔴 Coral **actuals** with white-bordered circle markers
- 📍 Vertical **"Forecast →" annotation** marking where predictions begin
- 🔴 Red/🟠 orange dashed **cap/floor lines** for logistic growth
- 🌙 Premium **dark theme** with glassmorphism styling

### 6. Robust Error Handling
Input validation with clear error messages for:
- Empty or mismatched data arrays
- Invalid growth model values
- Missing `cap` for logistic growth
- Invalid `floor >= cap` combinations

---

## 📖 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  1. LLM sends historical data (dates + values) via MCP     │
│  2. User selects growth model (linear or logistic)          │
│  3. Prophet model learns patterns and generates forecast    │
│  4. Response contains two content items:                    │
│     ├── content[0]: Human-readable summary + data table     │
│     └── content[1]: Chart.js JSON config for visualization  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Response Format

The MCP `tools/call` response returns **two content items**:

### content[0] — Text Summary
```text
### Prophet Forecast Data ###

Growth model used: LOGISTIC (cap=120, floor=30)

Summary of forecast metrics:
  - Historical Period: 2025-02-01 to 2025-03-02
  - Trend Direction: UPWARD (+26.1% vs historical mean)

Date | yhat | yhat_lower | yhat_upper
-------------------------------------
2025-03-03 | 79.56 | 76.93 | 81.98
...
```

### content[1] — Chart.js JSON
```text
chartjs_config:{"type":"line","data":{"labels":[...],"datasets":[...]},"options":{...}}
```

This is valid JSON prefixed with `chartjs_config:` — parse it as:
```python
cfg_json = content[1]["text"][len("chartjs_config:"):]
config = json.loads(cfg_json)
```

---

## 🛠️ Tool: `forecast_time_series`

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ds` | `array[string]` | ✅ Yes | — | List of dates in ISO format (YYYY-MM-DD) |
| `y` | `array[number]` | ✅ Yes | — | List of numeric values aligned with `ds` |
| `periods` | `integer` | No | `10` | Number of future periods to forecast |
| `growth` | `string` | No | `"linear"` | Growth model: `"linear"` or `"logistic"` |
| `cap` | `number` | When logistic | — | Saturating maximum (forecast won't exceed this) |
| `floor` | `number` | No | — | Saturating minimum (forecast won't go below this) |
| `freq` | `string` | No | `"D"` | Time series frequency: `"D"`, `"H"`, `"W"`, `"MS"` |

### When to Use Each Growth Model

| Scenario | Growth | Why |
|----------|--------|-----|
| Revenue, temperature, stock prices | `linear` | No natural ceiling or floor |
| Market share, adoption rate | `logistic` | Saturates at 100% |
| Server capacity, team bandwidth | `logistic` | Physical limits exist |
| Website conversion rate | `logistic` | Bounded between 0–100% |

### Output Columns

| Column | Meaning |
|--------|---------|
| `ds` | Date for the observed or predicted value |
| `yhat` | Predicted value (model's best estimate) |
| `yhat_lower` | Lower bound of confidence interval |
| `yhat_upper` | Upper bound of confidence interval |

---

## 📂 Project Structure

```
Prophet_mcp/
├── app.py                       # Flask server — MCP endpoint, auth, JSON-RPC routing
├── mcp_helper.py                # Core engine — Prophet forecasting, summary, Chart.js config
├── requirements.txt             # Python dependencies
├── Procfile                     # Cloud deployment (gunicorn)
├── README.md                    # This file
├── .gitignore                   # Git exclusions
└── examples/                    # Local testing utilities (not required for deployment)
    ├── plot_forecast.py         # Basic forecast test with Chart.js visualization
    └── test_gcp_marketing.py    # Real-world marketing scenario (30-day conversions)
```

---

## 📦 Installation & Setup

### Prerequisites
- [Anaconda](https://www.anaconda.com/download) or Miniconda (recommended for Prophet dependencies)
- Python 3.11+

### 1. Environment Setup

```bash
# Create environment
conda create -n prophet-mcp python=3.11
conda activate prophet-mcp

# Install dependencies
pip install -r requirements.txt
```

> **Windows Users:** Prophet requires `CmdStan`. If you encounter issues, refer to the [Prophet Installation Guide](https://facebook.github.io/prophet/docs/installation.html) or install via conda: `conda install -c conda-forge prophet`.

### 2. Configuration

The server uses Bearer Token authentication. Set the `MCP_TOKEN` environment variable:

```bash
# Set your token (required)
export MCP_TOKEN="your-secure-token-here"
```

---

## 🏃‍♂️ Running the Server

### Local Development
```bash
MCP_TOKEN="your-token" python app.py
```

### Production (Cloud)
```bash
gunicorn app:app
```

- **Server URL:** `http://localhost:3000`
- **MCP Endpoint:** `POST http://localhost:3000/mcp`
- **Health Check:** `GET /health`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TOKEN` | *(required)* | Bearer token for authentication |
| `PORT` | `3000` | Server port |
| `MCP_DEBUG` | `false` | Enable Flask debug mode |

### Authentication
All `/mcp` requests must include the header:
```
Authorization: Bearer <your-token>
```

### Example API Call (cURL)

```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "forecast_time_series",
      "arguments": {
        "ds": ["2025-01-01","2025-01-02","2025-01-03","2025-01-04","2025-01-05",
               "2025-01-06","2025-01-07","2025-01-08","2025-01-09","2025-01-10"],
        "y": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        "periods": 5,
        "growth": "logistic",
        "cap": 25,
        "floor": 5
      }
    },
    "id": 1
  }'
```

---

## 🧪 Testing & Visualization

### Basic Test
```bash
MCP_TOKEN="your-token" python examples/plot_forecast.py
```

### Marketing Forecast Test (30-day real-world scenario)
```bash
MCP_TOKEN="your-token" python examples/test_gcp_marketing.py
```

Both scripts will:
1. Call your MCP server's API
2. Extract the Chart.js config from `content[1]`
3. Generate an interactive HTML chart with premium dark theme
4. Open it in your default browser

---

## ☁️ Cloud Deployment

For deploying to Google Cloud Run (or any cloud provider), you need:

```
app.py
mcp_helper.py
requirements.txt
Procfile
```

The `examples/` folder is for local testing only and is not required in production.

The server binds to `0.0.0.0` and reads the `PORT` environment variable automatically for cloud compatibility.

---

## 🔐 Security

- Bearer Token authentication on all `/mcp` endpoints
- Token configurable via `MCP_TOKEN` environment variable (no defaults — must be explicitly set)
- Debug mode disabled by default (enable via `MCP_DEBUG=true`)
- JSON-RPC error handling with proper error codes
- Input validation on all tool parameters
- No sensitive data stored in source code

---

## 📄 Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | Web server framework |
| `pandas` | Data manipulation |
| `prophet` | Time-series forecasting engine |
| `gunicorn` | Production WSGI server |
| `requests` | HTTP client (examples only) |

---

## 📄 License

**MIT License**

---

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

**Author:** Pradeep Chandra Kalahasthi  
**Original Base:** [sendgrid-mcp](https://github.com/garethcull/sendgrid-mcp)
