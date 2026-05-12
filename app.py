import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

st.set_page_config(page_title="BingX Hunter Pro", page_icon="🎯", layout="wide")

# ============================================================
# 1. КОНФИГУРАЦИЯ
# ============================================================
st.title("🎯 BingX Hunter Pro v3.0")
st.subheader("Лонг/Шорт сигналы • Real-time данные • Тех.анализ TradingView • Процент успеха")

# ============================================================
# 2. ФУНКЦИИ ЗАГРУЗКИ РЕАЛЬНЫХ ДАННЫХ
# ============================================================

@st.cache_data(ttl=20)
def get_bingx_futures_list():
    """
    Получает список ВСЕХ фьючерсных пар с BingX API (реальные данные).
    """
    try:
        url = "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            contracts = data.get("data", [])
            pairs = []
            for c in contracts:
                if c.get("quoteAsset") == "USDT" and c.get("status") == 1:  # Только активные USDT-пары
                    pairs.append({
                        "symbol": c["symbol"],  # Например: "DOGE-USDT"
                        "base": c.get("baseAsset", ""),
                        "leverage_max": int(c.get("maxLeverage", 125)),
                        "price_tick": float(c.get("pricePrecision", 4)),
                        "qty_tick": float(c.get("quantityPrecision", 0))
                    })
            return pairs
        return []
    except Exception as e:
        st.warning(f"BingX API недоступен: {e}")
        return []

@st.cache_data(ttl=15)
def get_bingx_24h_tickers():
    """
    Получает 24ч статистику (high, low, volume, change) по всем парам BingX.
    """
    try:
        url = "https://open-api.bingx.com/openApi/swap/v2/quote/ticker/24hr"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            tickers = {}
            for t in data.get("data", []):
                symbol = t.get("symbol", "")
                if "USDT" in symbol:
                    tickers[symbol] = {
                        "price": float(t.get("lastPrice", 0)),
                        "high_24h": float(t.get("highPrice", 0)),
                        "low_24h": float(t.get("lowPrice", 0)),
                        "volume_24h": float(t.get("volume", 0)),
                        "change_24h": float(t.get("priceChangePercent", 0)),
                    }
            return tickers
        return {}
    except:
        return {}

@st.cache_data(ttl=30)
def get_coingecko_meme_data():
    """
    CoinGecko — для имён, капитализации и категории (meme).
    """
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "category": "meme-token",
            "order": "volume_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h"
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        cg = {}
        for item in data:
            cg[item["symbol"].upper()] = {
                "name": item["name"],
                "market_cap": item.get("market_cap", 0),
            }
        return cg
    except:
        return {}

@st.cache_data(ttl=60)
def get_tradingview_technicals(symbols_list):
    """
    Получает сводку тех.анализа TradingView для списка символов.
    Использует бесплатный прокси-эндпоинт.
    Возвращает: {"BTCUSDT": {"summary": "STRONG_BUY", "oscillators": "BUY", "moving_averages": "STRONG_BUY"}}
    """
    tv_data = {}
    
    # TradingView сканирует по парам BINANCE, маппим
    for sym in symbols_list[:20]:  # Ограничим 20 запросами
        try:
            clean = sym.replace("-USDT", "USDT").replace("1000", "")
            url = f"https://scanner.tradingview.com/crypto/scan"
            body = {
                "symbols": {"tickers": [f"BINANCE:{clean}"], "query": {}},
                "columns": ["Recommend.All|1"]
            }
            resp = requests.post(url, json=body, timeout=5)
            data = resp.json()
            
            if data.get("data") and len(data["data"]) > 0:
                val = data["data"][0]["d"][0]
                # -1 = Strong Sell, -0.5 = Sell, 0 = Neutral, 0.5 = Buy, 1 = Strong Buy
                if val >= 0.8:
                    tv_data[sym] = {"signal": "🟢 STRONG BUY", "score": val}
                elif val >= 0.3:
                    tv_data[sym] = {"signal": "🟢 BUY", "score": val}
                elif val >= -0.3:
                    tv_data[sym] = {"signal": "🟡 NEUTRAL", "score": val}
                elif val >= -0.7:
                    tv_data[sym] = {"signal": "🔴 SELL", "score": val}
                else:
                    tv_data[sym] = {"signal": "🔴 STRONG SELL", "score": val}
        except:
            pass
    
    return tv_data

# ============================================================
# 3. ФУНКЦИИ АНАЛИЗА И РАСЧЁТА
# ============================================================

def calculate_trade(entry_price, leverage, target_profit_percent, side="LONG"):
    """
    Полный расчёт: вход, выход, стоп, ликвидация.
    """
    price_move = target_profit_percent / leverage
    
    if side == "LONG":
        exit_price = entry_price * (1 + price_move / 100)
        stop_move = (target_profit_percent * 0.3) / leverage  # Стоп = 30% от цели
        stop_price = entry_price * (1 - stop_move / 100)
        liq_move = 100 / leverage  # Примерная ликвидация при -100% маржи
        liq_price = entry_price * (1 - liq_move / 100)
    else:  # SHORT
        exit_price = entry_price * (1 - price_move / 100)
        stop_move = (target_profit_percent * 0.3) / leverage
        stop_price = entry_price * (1 + stop_move / 100)
        liq_move = 100 / leverage
        liq_price = entry_price * (1 + liq_move / 100)
    
    return exit_price, stop_price, liq_price, price_move

def calculate_success_probability(amplitude_24h, needed_move, tv_signal, volume_rank, change_24h):
    """
    Считает ПРОЦЕНТ УСПЕШНОСТИ на основе:
    - Амплитуды (40% веса)
    - Сигнала TradingView (30% веса)
    - Объёма (20% веса)
    - Тренда 24ч (10% веса)
    """
    score = 0
    
    # Амплитуда (0-40 баллов)
    amp_ratio = min(amplitude_24h / max(needed_move, 0.01), 3)
    score += min(amp_ratio * 13.33, 40)
    
    # TradingView сигнал (0-30 баллов)
    if "STRONG BUY" in tv_signal:
        score += 30
    elif "BUY" in tv_signal:
        score += 20
    elif "NEUTRAL" in tv_signal:
        score += 10
    else:
        score += 0
    
    # Объём (0-20 баллов) — ра��г среди найденных
    score += max(20 - volume_rank * 1.5, 0)
    
    # Тренд 24ч (0-10 баллов) — ищем разворот (-5..+10) или продолжение
    if 0 < change_24h < 30:
        score += 10  # Растёт, но не перегрета
    elif -10 < change_24h <= 0:
        score += 8   # Небольшая коррекция — хороший вход
    elif change_24h >= 30:
        score += 3   # Перегрета, риск
    else:
        score += 2   # Сильное падение, риск
    
    return min(round(score), 95)  # Максимум 95% (100% не бывает)

def get_success_label(prob):
    if prob >= 70:
        return f"🟢 HIGH ({prob}%)"
    elif prob >= 45:
        return f"🟡 MEDIUM ({prob}%)"
    else:
        return f"🔴 LOW ({prob}%)"

# ============================================================
# 4. ИНТЕРФЕЙС (SIDEBAR)
# ============================================================
with st.sidebar:
    st.header("⚙️ НАСТРОЙКИ")
    
    exchange = st.selectbox("🏪 Биржа", ["BingX", "Bybit", "MEXC", "OKX", "Gate.io"], index=0)
    
    st.divider()
    st.subheader("💰 ЦЕЛЬ ПО ПРИБЫЛИ")
    
    target_profit = st.number_input(
        "Прибыль со сделки (% к депозиту)",
        min_value=10, max_value=5000, value=100, step=10
    )
    
    leverage = st.selectbox(
        "⚡ Плечо",
        [1, 2, 3, 5, 10, 15, 20, 25, 50, 75, 100, 125],
        index=5
    )
    
    needed_move = target_profit / leverage
    
    st.divider()
    st.subheader("🎯 НАПРАВЛЕНИЕ")
    
    trade_side = st.radio("Тип сделки", ["📈 LONG (в рост)", "📉 SHORT (в падение)"], index=0)
    side_code = "LONG" if "LONG" in trade_side else "SHORT"
    
    st.divider()
    st.subheader("🔍 ФИЛЬТРЫ")
    
    min_volume = st.slider("Мин. объём торгов (24ч, $)", 10000, 100000000, 50000, 10000)
    min_success = st.slider("Мин. процент успеха (%)", 20, 90, 45, 5)
    
    only_bingx = st.checkbox("Только пары с BingX", value=True)
    only_tv_signal = st.checkbox("Только с сигналом TradingView", value=False)
    
    st.divider()
    
    if st.button("🔄 ОБНОВИТЬ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.caption(f"Цель: +{target_profit}% | Плечо: x{leverage}")
    st.caption(f"Нужное движение: {needed_move:.1f}%")
    st.caption("📡 BingX + TradingView + CoinGecko")

# ============================================================
# 5. ЗАГРУЗКА ДАННЫХ
# ============================================================
with st.spinner("📡 Загружаю данные с BingX, TradingView, CoinGecko..."):
    bingx_pairs = get_bingx_futures_list()
    bingx_tickers = get_bingx_24h_tickers()
    cg_data = get_coingecko_meme_data()
    timestamp = datetime.now()

if not bingx_tickers:
    st.error("❌ Не удалось загрузить данные BingX. Проверь подключение.")
    st.stop()

# ============================================================
# 6. ОБЪЕДИНЕНИЕ И ФИЛЬТРАЦИЯ
# ============================================================
merged = []

# Собираем символы для TradingView
all_symbols = list(bingx_tickers.keys())

# Получаем тех.анализ
tv_signals = get_tradingview_technicals(all_symbols) if not only_bingx or True else {}

for sym, ticker in bingx_tickers.items():
    base = sym.replace("-USDT", "")
    cg_info = cg_data.get(base, {})
    
    # Проверяем, мемкоин ли это (или показываем все, если фильтр выключен)
    is_meme = base in cg_data
    
    # Фильтр BingX
    if only_bingx:
        bingx_match = any(p["symbol"] == sym for p in bingx_pairs)
        if not bingx_match:
            continue
    
    # Минимальный объём
    if ticker["volume_24h"] < min_volume:
        continue
    
    # Амплитуда
    high = ticker["high_24h"]
    low = ticker["low_24h"]
    if low > 0:
        amplitude = ((high - low) / low) * 100
    else:
        amplitude = 0
    
    # TradingView сигнал
    tv = tv_signals.get(sym, {"signal": "⚪ NO DATA", "score": 0})
    
    if only_tv_signal and tv["signal"] == "⚪ NO DATA":
        continue
    
    merged.append({
        "symbol": sym,
        "base": base,
        "price": ticker["price"],
        "volume_24h": ticker["volume_24h"],
        "change_24h": ticker["change_24h"],
        "high_24h": high,
        "low_24h": low,
        "amplitude_24h": amplitude,
        "name": cg_info.get("name", base),
        "market_cap": cg_info.get("market_cap", 0),
        "tv_signal": tv["signal"],
        "tv_score": tv["score"],
        "is_meme": is_meme
    })

# Сортируем по объёму
merged.sort(key=lambda x: x["volume_24h"], reverse=True)

# ============================================================
# 7. РАСЧЁТЫ ДЛЯ КАЖДОЙ МОНЕТЫ
# ============================================================
results = []
for idx, coin in enumerate(merged[:50]):  # Топ-50
    entry = coin["price"]
    
    # Считаем лонг И шорт
    exit_l, stop_l, liq_l, move_l = calculate_trade(entry, leverage, target_profit, "LONG")
    exit_s, stop_s, liq_s, move_s = calculate_trade(entry, leverage, target_profit, "SHORT")
    
    # Процент успеха для выбранного направления
    prob_long = calculate_success_probability(
        coin["amplitude_24h"], needed_move,
        coin["tv_signal"], idx,
        coin["change_24h"]
    )
    prob_short = calculate_success_probability(
        coin["amplitude_24h"], needed_move,
        "STRONG SELL" if "BUY" not in coin["tv_signal"] else "NEUTRAL",
        idx,
        -coin["change_24h"]
    )
    
    # Для LONG: успех выше, если монета в восходящем тренде
    long_prob = prob_long
    short_prob = prob_short
    
    # Выбранное направление
    if side_code == "LONG":
        exit_price = exit_l
        stop_price = stop_l
        liq_price = liq_l
        current_prob = long_prob
    else:
        exit_price = exit_s
        stop_price = stop_s
        liq_price = liq_s
        current_prob = short_prob
    
    success_label = get_success_label(current_prob)
    
    # Фильтр по мин. проценту успеха
    if current_prob < min_success:
        continue
    
    price_fmt = ".8f" if entry < 0.01 else ".6f" if entry < 1 else ".4f"
    
    results.append({
        "Монета": f"${coin['base']}",
        "Название": coin["name"],
        "Цена": float(entry),
        "Цена строка": f"${entry:{price_fmt}}",
        "Объём 24ч": coin["volume_24h"],
        "Объём строка": f"${coin['volume_24h']:,.0f}",
        "Амплитуда 24ч": f"{coin['amplitude_24h']:.1f}%",
        "Изм. 24ч": f"{coin['change_24h']:+.1f}%",
        "TradingView": coin["tv_signal"],
        "🎯 Выход": f"${exit_price:{price_fmt}}",
        "🛑 Стоп": f"${stop_price:{price_fmt}}",
        "💀 Ликв.": f"${liq_price:{price_fmt}}",
        "⚡ Движ.": f"{move_l:.1f}%",
        "Успех LONG": f"🟢 {long_prob}%" if long_prob >= 70 else f"🟡 {long_prob}%" if long_prob >= 45 else f"🔴 {long_prob}%",
        "Успех SHORT": f"🟢 {short_prob}%" if short_prob >= 70 else f"🟡 {short_prob}%" if short_prob >= 45 else f"🔴 {short_prob}%",
        "Сигнал": success_label,
        "Прибыль": f"+{target_profit}%",
        "prob_long_raw": long_prob,
        "prob_short_raw": short_prob,
        "current_prob_raw": current_prob
    })

# ============================================================
# 8. ОТОБРАЖЕНИЕ
# ============================================================
st.divider()

# Верхняя панель
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("🎯 Цель", f"+{target_profit}%")
with col2:
    st.metric("⚡ Плечо", f"x{leverage}")
with col3:
    st.metric("📈 Нужное движение", f"{needed_move:.1f}%")
with col4:
    st.metric("📊 Направление", trade_side)
with col5:
    st.metric("💡 Найдено", len(results))

st.divider()

if not results:
    st.warning("❌ Нет монет с такими параметрами. Снизь фильтры или процент успеха.")
    st.stop()

st.success(f"✅ Загружено: {timestamp.strftime('%H:%M:%S')} | Данные: BingX API + TradingView + CoinGecko")

# Таблица
df = pd.DataFrame(results)

st.dataframe(
    df[[
        "Монета", "Цена строка", "Объём строка", "Амплитуда 24ч",
        "Изм. 24ч", "TradingView",
        "🎯 Выход", "🛑 Стоп", "💀 Ликв.",
        "Успех LONG", "Успех SHORT", "Прибыль"
    ]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Монета": st.column_config.TextColumn("Монета", width="small"),
        "TradingView": st.column_config.TextColumn("TV", width="small"),
        "Успех LONG": st.column_config.TextColumn("✅ LONG", width="small"),
        "Успех SHORT": st.column_config.TextColumn("❌ SHORT", width="small"),
    }
)

# ============================================================
# 9. ЛУЧШАЯ МОНЕТА
# ============================================================
st.divider()
st.subheader("🔥 ЛУЧШИЙ СИГНАЛ")

# Сортируем по проценту успеха выбранного направления
results.sort(key=lambda x: x["current_prob_raw"], reverse=True)
best = results[0]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🏆 Монета", f"{best['Монета']} ({best['Название']})")
with col2:
    st.metric("💵 Цена входа", best["Цена строка"])
with col3:
    st.metric("🎯 Цена выхода", best["🎯 Выход"])
with col4:
    st.metric(f"📊 Успех ({'LONG' if side_code == 'LONG' else 'SHORT'})", best["Сигнал"])

# План сделки
price_fmt = ".8f" if best["Цена"] < 0.01 else ".6f" if best["Цена"] < 1 else ".4f"

st.info(f"""
### 📋 План сделки ({side_code})

| Параметр | Значение |
|----------|----------|
| **Пара** | {best['Монета'].replace('$','')}/USDT на {exchange} |
| **Тип** | {trade_side} |
| **Плечо** | x{leverage} |
| **Цена входа** | {best['Цена строка']} |
| **Цена выхода (Тейк-профит)** | {best['🎯 Выход']} |
| **Цена стоп-лосса** | {best['🛑 Стоп']} |
| **Цена ликвидации** | {best['💀 Ликв.']} |
| **Нужное движение** | {best['⚡ Движ.']} |
| **Процент успеха** | {best['Сигнал']} |
| **Прибыль к депозиту** | **{best['Прибыль']}** |
| **Убыток при стопе** | -{target_profit * 0.3:.0f}% к депозиту |
""")

# Сравнение LONG vs SHORT
st.divider()
st.subheader("📊 Сравнение LONG vs SHORT (первые 10)")

chart_data = pd.DataFrame({
    "Монета": [r["Монета"] for r in results[:10]],
    "LONG %": [r["prob_long_raw"] for r in results[:10]],
    "SHORT %": [r["prob_short_raw"] for r in results[:10]],
})

st.bar_chart(
    chart_data.set_index("Монета")[["LONG %", "SHORT %"]],
    use_container_width=True,
    color=["#00ff88", "#ff4444"]
)

# Подвал с глоссарием
st.divider()
st.caption("### Как считается процент успеха:")
st.caption("- **40%** — амплитуда за 24ч (чем шире ходит, тем выше шанс)")
st.caption("- **30%** — сигнал TradingView (Strong Buy / Sell)")
st.caption("- **20%** — объём торгов (высокая ликвидность = меньше проскальзывание)")
st.caption("- **10%** — тренд за 24ч (разворот или продолжение)")
st.divider()
st.caption(f"📡 BingX API (реальные данные) + TradingView Scanner + CoinGecko | {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("⚠️ Данный инструмент — помощник, а не гарант. Всегда ставь стоп-лосс и соблюдай риск-менеджмент.")