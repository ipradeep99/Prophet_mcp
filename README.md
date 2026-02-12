# Prophet MCP Server

An open-source **Model Context Protocol (MCP)** server that exposes a **forecasting tool** using **Facebook Prophet**. The server accepts lists of dates and numerical values, formats them for Prophet, runs a forecast, and returns the output as raw JSON.

This project is a modified version of the [sendgrid-mcp](https://github.com/garethcull/sendgrid-mcp) server, extended with a Prophet-based time-series forecasting tool. It is built with **Flask** and follows the JSON-RPC MCP protocol.

---

## Objective

- Create/modify an open-source MCP server to feature a **forecasting tool** using **Facebook Prophet**.
- The tool accepts **lists of dates and values**, formats them for Prophet, runs a forecast, and returns the result as **raw JSON**.
- Provide a clear path to set up the environment (Anaconda), run the server, and test the forecast tool via a **Jupyter Notebook**.

---

## Deliverables

- **Modified MCP server** with the Prophet forecasting tool implemented (`app.py`, `mcp_helper.py`).
- **Tool schema** that accepts dates (`ds`) and numerical values (`y`), plus optional `periods` for future steps.
- **JSON-based forecast output** with `meta` (e.g. periods, date range) and `forecast` (rows with `ds`, `yhat`, `yhat_lower`, `yhat_upper`).
- **Jupyter Notebook** example demonstrating how to call the tool locally.
- **README** with environment setup, how to run the server, and how to use the notebook to test the forecast.

---

## MCP Forecast Tool

### Tool: `forecast_time_series`

- **Input:**  
  - `ds` – list of date strings (e.g. `"2025-01-01"`)  
  - `y` – list of numeric values (same length as `ds`)  
  - `periods` – (optional) number of future periods to forecast; default `10`

- **Output:** Raw JSON with:
  - `meta`: `periods`, `n_history`, `start`, `end`
  - `forecast`: array of `{ "ds", "yhat", "yhat_lower", "yhat_upper" }`

All requests require a valid **Bearer token** (e.g. set in `app.py`) for authorization.

---

## Environment Installation (Anaconda)

### 1. Prerequisites

- [Anaconda](https://www.anaconda.com/download) or Miniconda installed.

### 2. Create and activate environment

```bash
conda create -n prophet-mcp python=3.11
conda activate prophet-mcp
```

### 3. Install dependencies

From the project root:

```bash
pip install -r requirements.txt
```

This installs **Flask**, **Prophet**, **pandas**, and related dependencies.  
*(Prophet requires NumPy &lt; 2; the `requirements.txt` pins this.)*

### 4. Install CmdStan (required for Prophet)

Prophet uses **CmdStan** under the hood. Install it with:

```bash
# Optional: use a short path on Windows to avoid long-path issues
set CMDSTAN=C:\cmdstan

# Install CmdStan (may take 5–10 minutes)
python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"
```

Verify Prophet:

```bash
python -c "from prophet import Prophet; m = Prophet(); print('Prophet OK')"
```

### 5. Windows: long path / Prophet install issues

If Prophet or CmdStan fail (e.g. long path errors):

- **Option A:** Enable [Windows long path support](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) (registry or Group Policy), then re-run the installs.
- **Option B:** Use a short install path: `set CMDSTAN=C:\cmdstan` before `cmdstanpy.install_cmdstan()`.
- **Option C:** Install via conda-forge:  
  `conda install -c conda-forge prophet cmdstanpy`

---

## How to Run the MCP Server

### Option 1: Flask CLI

```bash
conda activate prophet-mcp
set FLASK_APP=app.py
flask run --debug --host localhost --port 3000
```

### Option 2: Direct Python

```bash
conda activate prophet-mcp
python app.py
```

By default, `app.py` runs the server at **http://localhost:3000**.  
The MCP endpoint is: **http://localhost:3000/mcp**.

### Auth

Requests must include:

- Header: `Authorization: Bearer <your-token>`  
The token is configured in `app.py` (e.g. `MCP_TOKEN`). Change it for your environment.

---

## How to Use the Jupyter Notebook to Test the Forecast Tool

### 1. Start the MCP server

From a terminal (with `prophet-mcp` active):

```bash
python app.py
```

Keep this running so the notebook can call **http://localhost:3000/mcp**.

### 2. In Jupyter: call the forecast tool

Use a notebook cell with the same pattern as below. It sends a JSON-RPC `tools/call` request with `forecast_time_series` and your `ds`, `y`, and `periods`.

```python
import requests
import json

def call_tool_with_args(base_url="http://localhost:3000", token=None):
    """
    Calls /mcp with tools/call → forecast_time_series.
    Token must match the one in app.py (e.g. 'MCP_TOKEN').
    """
    if token is None:
        token = 'MCP_TOKEN'
    if not token:
        raise ValueError("MCP token missing. Pass token=... or set it in app.py.")

    url = f"{base_url}/mcp"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

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
                "periods": 5
            }
        },
        "id": 1
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.status_code, resp.json()
    except Exception as e:
        return None, f"Error: {str(e)}"

# Call the tool
status, result = call_tool_with_args(base_url="http://localhost:3000", token=None)
print(f"Status Code: {status}")
print(json.dumps(result, indent=2))
```

### 3. Parse the forecast from the response

The forecast is in the MCP `content` text (JSON string). Example of how to use it:

```python
if status == 200 and "result" in result and "content" in result["result"]:
    text = result["result"]["content"][0]["text"]
    data = json.loads(text)
    if "forecast" in data:
        print("Forecast (last 5 rows):")
        for row in data["forecast"][-5:]:
            print(row)
    if "meta" in data:
        print("Meta:", data["meta"])
```

---

## Project Structure

| File            | Role |
|-----------------|------|
| **app.py**      | Flask app: `POST /mcp` endpoint, auth (Bearer token), delegates to `mcp_helper`. |
| **mcp_helper.py** | MCP logic: `initialize`, `tools/list`, `tools/call`; implements `forecast_time_series` (Prophet). |
| **requirements.txt** | Python dependencies (Flask, Prophet, pandas, etc.). |

---

## Protocol Summary

- **Endpoint:** `POST /mcp`  
- **Content-Type:** `application/json`  
- **Auth:** `Authorization: Bearer <token>`  
- **Methods:**  
  - `initialize` → server info and capabilities  
  - `tools/list` → list of tools and `inputSchema` (e.g. `ds`, `y`, `periods`)  
  - `tools/call` → run a tool (e.g. `forecast_time_series`) and return JSON in `content`  

---

## References

- Original MCP server: [sendgrid-mcp](https://github.com/garethcull/sendgrid-mcp) by Gareth Cull  
- MCP: [Model Context Protocol](https://modelcontextprotocol.io/)  
- Prophet: [Facebook Prophet](https://facebook.github.io/prophet/)  
- Tutorial: *How to Build an MCP Server* (Python) – for building or customizing MCP servers from scratch  

---

## License

MIT.

---

## Acknowledgments

This project extends the [sendgrid-mcp](https://github.com/garethcull/sendgrid-mcp) repository with a Prophet-based forecasting tool for use with MCP clients and local testing via Jupyter.
