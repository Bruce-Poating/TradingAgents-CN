#!/usr/bin/env python3
"""Quick test: run TradingAgents analysis for 601318.SS using Xiaomi MiMo."""

import os
import sys

# Force config via env vars
os.environ["TRADINGAGENTS_LLM_PROVIDER"] = "openai_compatible"
os.environ["TRADINGAGENTS_DEEP_THINK_LLM"] = "mimo-v2.5-pro"
os.environ["TRADINGAGENTS_QUICK_THINK_LLM"] = "mimo-v2.5-pro"
os.environ["TRADINGAGENTS_LLM_BACKEND_URL"] = "https://token-plan-cn.xiaomimimo.com/v1"
os.environ["TRADINGAGENTS_OUTPUT_LANGUAGE"] = "Chinese"
os.environ["OPENAI_COMPATIBLE_API_KEY"] = "tp-ckzvjsoca3f61u1s502syeu1de6dchvdva7v942atzm7g6m0"

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()

print(f"Provider: {config['llm_provider']}")
print(f"Backend: {config['backend_url']}")
print(f"Language: {config['output_language']}")
print(f"Data vendors: {config['data_vendors']}")
print()

# Initialize
ta = TradingAgentsGraph(debug=True, config=config)

# Run analysis for 601318.SS (Ping An Insurance)
ticker = "601318.SS"
date = "2026-06-22"

print(f"=== Analyzing {ticker} on {date} ===")
print()

try:
    _, decision = ta.propagate(ticker, date)
    print()
    print("=" * 60)
    print("FINAL DECISION:")
    print("=" * 60)
    print(decision)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
