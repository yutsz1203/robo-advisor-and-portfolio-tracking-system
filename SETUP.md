# Setup Guide

## 1. Install Python

Ensure **Python 3.11 or later** is installed.

- **Windows**: Download from [python.org](https://www.python.org/downloads/). During installation, check **"Add Python to PATH"**.
- **macOS**: Download from [python.org](https://www.python.org/downloads/), or if you have Homebrew: `brew install python`

Verify the installation by opening a terminal and running:
```
python --version
```

---

## 2. Install uv

We used `uv`, a fast Python package manager, to install dependencies for this project.

**macOS / Linux** — open Terminal and run:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** — open PowerShell and run:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, **close and reopen your terminal**, then verify:
```
uv --version
```

---

## 3. Set Up the Project

Open a terminal, navigate to the project folder, and run the following commands.

**Create a virtual environment:**
```
uv venv
```

**Activate the virtual environment:**

- macOS / Linux:
  ```bash
  source .venv/bin/activate
  ```
- Windows (PowerShell):
  ```powershell
  .venv\Scripts\activate
  ```

**Install dependencies:**
```
uv pip install -r requirements.txt
```

---

## 4. Update the Database

> **Important:** Run this step before launching the app to ensure the latest exchange rates are loaded.

With the virtual environment still active, run:
```
python update_db.py
```

This fetches the latest FX rates from Yahoo Finance and updates the database. It may take a minute to complete.

---

## 5. Testing the Rebalance Function (Optional)

To test the rebalancing feature with fixed prices, open `pages/robo_advisor.py` and uncomment lines 158–164 (the hardcoded `current_price` DataFrame), then comment out line 157 (`current_price = fetch_price(...)`). This replaces the live price fetch with static test data so rebalancing can be triggered without waiting for market data.

---

## 6. Run the App

```
streamlit run app.py
```

A browser window will open automatically at `http://localhost:8501`. If it does not open, copy that address into your browser manually.

To stop the app, press `Ctrl + C` in the terminal.
