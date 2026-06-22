"""TDX (通达信) data source for A-share stocks.

Uses the local TDX API server for real-time quotes and K-line data.
Prices are returned in yuan (the TDX API returns prices in li, /1000).
"""

from datetime import datetime
from typing import Annotated

import pandas as pd
import requests

from .errors import NoMarketDataError

import os
TDX_BASE_URL = os.getenv("TDX_API_URL", "http://100.66.66.66:8877")


def _convert_symbol_to_tdx(symbol: str) -> str:
    """Convert Yahoo-style symbol to TDX format.
    
    601318.SS -> SH601318
    000001.SZ -> SZ000001
    """
    symbol = symbol.strip().upper()
    if "." in symbol:
        code, suffix = symbol.split(".", 1)
        if suffix in ("SS", "SH"):
            return f"SH{code}"
        elif suffix == "SZ":
            return f"SZ{code}"
    # No suffix - auto-detect
    code = symbol.replace("SH", "").replace("SZ", "")
    if code.startswith("6") or code.startswith("9"):
        return f"SH{code}"
    return f"SZ{code}"


def _is_a_share(symbol: str) -> bool:
    """Check if symbol is an A-share stock."""
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".")[-1] in ("SS", "SH", "SZ")
    code = s.replace("SH", "").replace("SZ", "")
    return code.isdigit() and len(code) == 6


def _fetch_kline(tdx_code: str, count: int = 500) -> list:
    """Fetch K-line data from TDX API.
    
    Returns list of dicts with keys: Time, Open, High, Low, Close, Volume.
    Prices are already converted to yuan.
    """
    try:
        resp = requests.get(
            f"{TDX_BASE_URL}/api/kline",
            params={"code": tdx_code, "type": "day", "count": count},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise NoMarketDataError(tdx_code, tdx_code, f"TDX API error: {e}")
    
    if not data or "data" not in data:
        raise NoMarketDataError(tdx_code, tdx_code, "no K-line data returned")
    
    # Response format: {"code": 0, "data": {"Count": N, "List": [...]}}
    inner = data["data"]
    if isinstance(inner, dict):
        klines = inner.get("List", [])
    elif isinstance(inner, list):
        klines = inner
    else:
        raise NoMarketDataError(tdx_code, tdx_code, "unexpected kline format")
    
    if not klines:
        raise NoMarketDataError(tdx_code, tdx_code, "empty K-line data")
    
    return klines


def get_stock_data_tdx(
    symbol: Annotated[str, "ticker symbol (e.g. 601318.SS or SH601318)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Get OHLCV stock data from TDX API.
    
    Returns CSV string in the same format as yfinance for compatibility.
    """
    tdx_code = _convert_symbol_to_tdx(symbol)
    klines = _fetch_kline(tdx_code, count=500)
    
    # Parse into DataFrame - TDX prices are in li (1/1000 yuan)
    rows = []
    for k in klines:
        time_str = k.get("Time", "")
        if not time_str:
            continue
        rows.append({
            "Date": pd.to_datetime(time_str),
            "Open": round(k.get("Open", 0) / 1000, 2),
            "High": round(k.get("High", 0) / 1000, 2),
            "Low": round(k.get("Low", 0) / 1000, 2),
            "Close": round(k.get("Close", 0) / 1000, 2),
            "Volume": k.get("Volume", 0),
        })
    
    if not rows:
        raise NoMarketDataError(symbol, tdx_code, "no parseable kline data")
    
    df = pd.DataFrame(rows).set_index("Date")
    
    # Strip timezone info for consistent comparison
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
    
    if df.empty:
        raise NoMarketDataError(
            symbol, tdx_code, f"no data between {start_date} and {end_date}"
        )
    
    df["Adj Close"] = df["Close"]
    csv_string = df.to_csv()
    
    header = f"# Stock data for {tdx_code} (from {symbol}) from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data source: TDX API\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    return header + csv_string


def get_stock_stats_indicators_tdx(
    symbol: Annotated[str, "ticker symbol"],
    indicator: Annotated[str, "technical indicator"],
    curr_date: Annotated[str, "current date YYYY-mm-dd"],
    look_back_days: Annotated[int, "days to look back"],
) -> str:
    """Get technical indicators using TDX data + stockstats calculation."""
    from stockstats import wrap
    
    end_date = curr_date
    curr_date_dt = pd.to_datetime(curr_date)
    tdx_code = _convert_symbol_to_tdx(symbol)
    klines = _fetch_kline(tdx_code, count=500)
    
    # Build DataFrame
    rows = []
    for k in klines:
        time_str = k.get("Time", "")
        if not time_str:
            continue
        rows.append({
            "Date": pd.to_datetime(time_str),
            "Open": round(k.get("Open", 0) / 1000, 2),
            "High": round(k.get("High", 0) / 1000, 2),
            "Low": round(k.get("Low", 0) / 1000, 2),
            "Close": round(k.get("Close", 0) / 1000, 2),
            "Volume": k.get("Volume", 0),
        })
    
    if not rows:
        raise NoMarketDataError(symbol, tdx_code, "no data for indicator calc")
    
    df = pd.DataFrame(rows).set_index("Date")
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    try:
        ss = wrap(df)
        ss[indicator]  # trigger calculation
        
        before = curr_date_dt - pd.Timedelta(days=look_back_days)
        result = ""
        current = curr_date_dt
        while current >= before:
            date_str = current.strftime("%Y-%m-%d")
            matches = ss[ss.index.strftime("%Y-%m-%d") == date_str]
            if not matches.empty:
                val = matches[indicator].iloc[0]
                result += f"{date_str}: {val if not pd.isna(val) else 'N/A'}\n"
            else:
                result += f"{date_str}: N/A (not a trading day)\n"
            current -= pd.Timedelta(days=1)
        
        INDICATOR_DESCRIPTIONS = {
            "close_50_sma": "50 SMA: Medium-term trend indicator",
            "close_200_sma": "200 SMA: Long-term trend benchmark",
            "close_10_ema": "10 EMA: Responsive short-term average",
            "macd": "MACD: Momentum via EMA differences",
            "macds": "MACD Signal: EMA smoothing of MACD line",
            "macdh": "MACD Histogram: Gap between MACD and signal",
            "rsi": "RSI: Momentum for overbought/oversold",
            "boll": "Bollinger Middle: 20 SMA basis",
            "boll_ub": "Bollinger Upper Band",
            "boll_lb": "Bollinger Lower Band",
            "atr": "ATR: Average True Range volatility",
            "vwma": "VWMA: Volume-weighted moving average",
            "mfi": "MFI: Money Flow Index",
        }
        
        desc = INDICATOR_DESCRIPTIONS.get(indicator, f"{indicator} indicator")
        before_str = before.strftime("%Y-%m-%d")
        return f"## {indicator} values from {before_str} to {end_date}:\n\n{result}\n\n{desc}"
    
    except NoMarketDataError:
        raise
    except Exception as e:
        raise NoMarketDataError(symbol, tdx_code, f"indicator calc error: {e}")


def get_quote_tdx(symbol: Annotated[str, "ticker symbol"]) -> str:
    """Get real-time quote from TDX API."""
    tdx_code = _convert_symbol_to_tdx(symbol)
    
    try:
        resp = requests.get(
            f"{TDX_BASE_URL}/api/quote",
            params={"code": tdx_code},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise NoMarketDataError(symbol, tdx_code, f"TDX quote error: {e}")
    
    if not data or "data" not in data:
        raise NoMarketDataError(symbol, tdx_code, "empty quote")
    
    # Extract quote from response
    quote_data = data["data"]
    if isinstance(quote_data, list) and len(quote_data) > 0:
        quote = quote_data[0]
    elif isinstance(quote_data, dict):
        quote = quote_data
    else:
        raise NoMarketDataError(symbol, tdx_code, "unexpected quote format")
    
    k = quote.get("K", {})
    last_price = k.get("Last", quote.get("Last", 0))
    if isinstance(last_price, (int, float)) and last_price > 100:
        last_price = round(last_price / 1000, 2)
    
    result = f"# Real-time Quote for {tdx_code}\n"
    result += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    result += f"Code: {quote.get('Code', tdx_code)}\n"
    result += f"Last Price: {last_price}\n"
    result += f"Total Hand: {quote.get('TotalHand', 'N/A')}\n"
    
    return result
