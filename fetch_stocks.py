#!/usr/bin/env python3
"""
抓取台股 / 美股報價與近期歷史資料，輸出成 data.json 供前端儀表板讀取。

用法：
    pip install yfinance
    python fetch_stocks.py

輸出：data.json（放在跟 index.html 同一個資料夾，或推到 GitHub Pages 的 repo 裡）
"""
from __future__ import annotations

import json
import math
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

# 想追蹤的股票，自行增減。台股記得加 .TW（上市）或 .TWO（上櫃）
WATCHLIST = {
    "TW": ["6933.TW", "2330.TW", "00685L.TW", "0050.TW", "0056.TW", "00631L.TW",
           "00403A.TW", "2454.TW", "00981A.TW", "00982A.TW", "00988A.TW",
           "0052.TW", "00830.TW", "00662.TW", "2449.TW", "3711.TW",
           "02001L.TW", "3653.TW", "00909.TW", "00878.TW", "00919.TW"],
    "US": ["NVDA", "AAPL"],
}

# 四大指數：台灣加權、道瓊工業、那斯達克、費城半導體
INDEXES = {
    "TAIEX": "^TWII",
    "DJI": "^DJI",
    "IXIC": "^IXIC",
    "SOX": "^SOX",
}

HISTORY_DAYS = "1mo"  # 抓近一個月日K，用來畫K線與算MA
REQUEST_DELAY_SEC = 0.6  # 每檔之間稍微停一下，降低被 Yahoo 限流的機率


def _safe_int(v, default=0) -> int:
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v, default=None):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return default
        return round(float(v), 2)
    except (TypeError, ValueError):
        return default


def fetch_one(symbol: str) -> Optional[dict]:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=HISTORY_DAYS, interval="1d")
        if hist is None or hist.empty:
            print(f"[warn] {symbol} 沒有歷史資料，略過", file=sys.stderr)
            return None

        last_close = _safe_float(hist["Close"].iloc[-1])
        if last_close is None:
            print(f"[warn] {symbol} 收盤價異常，略過", file=sys.stderr)
            return None
        prev_close = _safe_float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close
        prev_close = prev_close if prev_close else last_close
        chg = round(last_close - prev_close, 2)
        pct = round((chg / prev_close * 100) if prev_close else 0.0, 2)

        closes = [c for c in (_safe_float(v) for v in hist["Close"].tolist()) if c is not None]
        ma5 = round(sum(closes[-5:]) / 5, 2) if len(closes) >= 5 else None

        # currency 只是錦上添花的欄位，抓不到就算了，不要讓它影響整檔資料
        currency = None
        try:
            currency = getattr(t.fast_info, "currency", None)
        except Exception:
            pass

        return {
            "symbol": symbol,
            "price": last_close,
            "change": chg,
            "pct": pct,
            "open": _safe_float(hist["Open"].iloc[-1], last_close),
            "high": _safe_float(hist["High"].iloc[-1], last_close),
            "low": _safe_float(hist["Low"].iloc[-1], last_close),
            "volume": _safe_int(hist["Volume"].iloc[-1]),
            "ma5": ma5,
            "kline": closes[-20:],
            "currency": currency,
            "as_of": hist.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:  # noqa: BLE001 — 排程任務，單檔失敗絕不能讓整個腳本掛掉
        print(f"[error] {symbol}: {e}", file=sys.stderr)
        return None


def fetch_index(label: str, symbol: str) -> Optional[dict]:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d", interval="1d")
        if hist is None or hist.empty:
            return None
        last = _safe_float(hist["Close"].iloc[-1])
        if last is None:
            return None
        prev = _safe_float(hist["Close"].iloc[-2]) if len(hist) > 1 else last
        prev = prev if prev else last
        chg = round(last - prev, 2)
        pct = round((chg / prev * 100) if prev else 0.0, 2)
        return {"label": label, "symbol": symbol, "value": last, "change": chg, "pct": pct}
    except Exception as e:  # noqa: BLE001
        print(f"[error] index {symbol}: {e}", file=sys.stderr)
        return None


def main() -> int:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indexes": [],
        "TW": [],
        "US": [],
    }

    for label, symbol in INDEXES.items():
        idx = fetch_index(label, symbol)
        if idx:
            result["indexes"].append(idx)
        time.sleep(REQUEST_DELAY_SEC)

    for market, symbols in WATCHLIST.items():
        for sym in symbols:
            data = fetch_one(sym)
            if data:
                result[market].append(data)
            time.sleep(REQUEST_DELAY_SEC)

    # 就算部分失敗，也一定要把已經抓到的資料寫出去，不要讓整個排程「全部或沒有」
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total = len(result["indexes"]) + len(result["TW"]) + len(result["US"])
    print(f"寫入 data.json 完成，共 {total} 筆（含指數）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # 保底：就算真的出現預期外的例外，也印出完整 traceback 方便除錯，
        # 但仍回傳 0，避免整條 Action 因為單次排程異常就整個標紅、擋住之後的排程。
        traceback.print_exc()
        sys.exit(0)
