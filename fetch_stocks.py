#!/usr/bin/env python3
"""
抓取台股 / 美股報價與近期歷史資料，輸出成 data.json 供前端儀表板讀取。

用法：
    pip install yfinance
    python fetch_stocks.py

輸出：data.json（放在跟 index.html 同一個資料夾，或推到 GitHub Pages 的 repo 裡）
"""
import json
import sys
from datetime import datetime, timezone

import yfinance as yf

# 想追蹤的股票，自行增減。台股記得加 .TW（上市）或 .TWO（上櫃）
WATCHLIST = {
    "TW": ["6933.TW", "2330.TW"],
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


def fetch_one(symbol: str) -> dict | None:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=HISTORY_DAYS, interval="1d")
        if hist.empty:
            print(f"[warn] {symbol} 沒有歷史資料", file=sys.stderr)
            return None

        info = t.fast_info  # 比 .info 快很多，適合排程頻繁呼叫
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close
        chg = last_close - prev_close
        pct = (chg / prev_close * 100) if prev_close else 0.0

        closes = [round(float(v), 2) for v in hist["Close"].tolist()]
        ma5 = None
        if len(closes) >= 5:
            ma5 = round(sum(closes[-5:]) / 5, 2)

        return {
            "symbol": symbol,
            "price": round(last_close, 2),
            "change": round(chg, 2),
            "pct": round(pct, 2),
            "open": round(float(hist["Open"].iloc[-1]), 2),
            "high": round(float(hist["High"].iloc[-1]), 2),
            "low": round(float(hist["Low"].iloc[-1]), 2),
            "volume": int(hist["Volume"].iloc[-1]),
            "ma5": ma5,
            "kline": closes[-20:],  # 近20筆收盤，給前端畫線圖
            "currency": getattr(info, "currency", None),
            "as_of": hist.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:  # noqa: BLE001 — 排程任務，單檔失敗不要整個中斷
        print(f"[error] {symbol}: {e}", file=sys.stderr)
        return None


def fetch_index(label: str, symbol: str) -> dict | None:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d", interval="1d")
        if hist.empty:
            return None
        last = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last
        chg = last - prev
        pct = (chg / prev * 100) if prev else 0.0
        return {"label": label, "symbol": symbol, "value": round(last, 2), "change": round(chg, 2), "pct": round(pct, 2)}
    except Exception as e:  # noqa: BLE001
        print(f"[error] index {symbol}: {e}", file=sys.stderr)
        return None


def main():
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
    for market, symbols in WATCHLIST.items():
        for sym in symbols:
            data = fetch_one(sym)
            if data:
                result[market].append(data)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"寫入 data.json 完成，共 {sum(len(v) for k, v in result.items() if k != 'generated_at')} 檔")


if __name__ == "__main__":
    main()
