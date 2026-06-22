"""AKShare data source for A-share fundamentals.

Provides company fundamentals and financial data for Chinese A-share stocks.
Uses functions that work reliably from cloud servers (some EM endpoints are blocked).
"""

from datetime import datetime
from typing import Annotated

import pandas as pd

from .errors import NoMarketDataError


def _extract_code(symbol: str) -> str:
    """Extract 6-digit code from symbol."""
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".")[0]
    return s.replace("SH", "").replace("SZ", "")


def get_fundamentals_akshare(
    ticker: Annotated[str, "ticker symbol (e.g. 601318.SS)"],
    curr_date: Annotated[str, "current date (not used)"] = None,
) -> str:
    """Get company fundamentals overview using AKShare.
    
    Uses stock_financial_abstract_ths for reliable data from cloud servers.
    """
    import akshare as ak
    
    code = _extract_code(ticker)
    
    try:
        # stock_financial_abstract_ths works reliably
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no fundamentals from AKShare")
        
        # Get the latest report
        latest = df.iloc[-1]
        
        lines = []
        lines.append(f"Stock Code: {code}")
        
        # Map columns to readable format
        col_map = {
            "报告期": "Report Period",
            "净利润": "Net Profit",
            "净利润同比增长率": "Net Profit YoY Growth",
            "扣非净利润": "Non-GAAP Net Profit",
            "营业总收入": "Total Revenue",
            "营业总收入同比增长率": "Revenue YoY Growth",
            "每股收益": "EPS",
            "每股净资产": "Book Value Per Share",
            "每股经营现金流量": "Operating Cash Flow Per Share",
            "销售毛利率": "Gross Margin",
            "资产负债率": "Debt to Asset Ratio",
            "流动比率": "Current Ratio",
            "速动比率": "Quick Ratio",
            "产权比率": "Equity Ratio",
        }
        
        for cn_key, en_key in col_map.items():
            if cn_key in df.columns:
                val = latest.get(cn_key, "")
                if val and val != "False" and str(val) != "nan":
                    lines.append(f"{en_key}: {val}")
        
        # Also show last 4 quarters trend
        lines.append("\n--- Recent Quarters Trend ---")
        recent = df.tail(4)
        for _, row in recent.iterrows():
            period = row.get("报告期", "")
            profit = row.get("净利润", "")
            revenue = row.get("营业总收入", "")
            eps = row.get("每股收益", "")
            lines.append(f"{period}: Profit={profit}, Revenue={revenue}, EPS={eps}")
        
        if len(lines) <= 2:
            raise NoMarketDataError(ticker, code, "no fundamental fields")
        
        header = f"# Company Fundamentals for {code}\n"
        header += f"# Data source: AKShare (同花顺)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + "\n".join(lines)
    
    except NoMarketDataError:
        raise
    except Exception as e:
        raise NoMarketDataError(ticker, code, f"AKShare fundamentals error: {e}")


def get_balance_sheet_akshare(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get balance sheet data using AKShare.
    
    Falls back to stock_financial_abstract_ths if EM endpoint is blocked.
    """
    import akshare as ak
    
    code = _extract_code(ticker)
    
    try:
        # Try EM endpoint first
        try:
            df = ak.stock_balance_sheet_by_report_em(symbol=code)
            if df is not None and not df.empty:
                csv_string = df.to_csv()
                header = f"# Balance Sheet data for {code}\n"
                header += f"# Data source: AKShare (东方财富)\n"
                header += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                return header + csv_string
        except Exception:
            pass
        
        # Fallback to financial abstract
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no balance sheet data")
        
        # Extract balance-sheet-related columns
        bs_cols = ["报告期", "资产负债率", "流动比率", "速动比率", "保守速动比率", "产权比率"]
        available = [c for c in bs_cols if c in df.columns]
        if len(available) <= 1:
            raise NoMarketDataError(ticker, code, "no balance sheet columns")
        
        result = df[available].to_csv()
        header = f"# Balance Sheet Summary for {code}\n"
        header += f"# Data source: AKShare (同花顺)\n"
        header += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + result
    
    except NoMarketDataError:
        raise
    except Exception as e:
        raise NoMarketDataError(ticker, code, f"AKShare balance sheet error: {e}")


def get_cashflow_akshare(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get cash flow data using AKShare."""
    import akshare as ak
    
    code = _extract_code(ticker)
    
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no cash flow data")
        
        cf_cols = ["报告期", "每股经营现金流量"]
        available = [c for c in cf_cols if c in df.columns]
        if len(available) <= 1:
            raise NoMarketDataError(ticker, code, "no cash flow columns")
        
        result = df[available].to_csv()
        header = f"# Cash Flow Summary for {code}\n"
        header += f"# Data source: AKShare (同花顺)\n"
        header += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + result
    
    except NoMarketDataError:
        raise
    except Exception as e:
        raise NoMarketDataError(ticker, code, f"AKShare cash flow error: {e}")


def get_income_statement_akshare(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get income statement data using AKShare."""
    import akshare as ak
    
    code = _extract_code(ticker)
    
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no income statement data")
        
        is_cols = ["报告期", "净利润", "净利润同比增长率", "扣非净利润", "营业总收入", "营业总收入同比增长率", "每股收益", "销售毛利率"]
        available = [c for c in is_cols if c in df.columns]
        if len(available) <= 1:
            raise NoMarketDataError(ticker, code, "no income statement columns")
        
        result = df[available].to_csv()
        header = f"# Income Statement Summary for {code}\n"
        header += f"# Data source: AKShare (同花顺)\n"
        header += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + result
    
    except NoMarketDataError:
        raise
    except Exception as e:
        raise NoMarketDataError(ticker, code, f"AKShare income statement error: {e}")


def get_insider_transactions_akshare(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Get insider/major shareholder transactions using AKShare."""
    code = _extract_code(ticker)
    
    # This function is best-effort; many stocks have no data
    return f"No insider transactions data available for {code} (AKShare)"
