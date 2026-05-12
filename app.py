import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
import random

st.set_page_config(page_title="BingX Hunter Pro", page_icon="🎯", layout="wide")

# ============================================================
# 1. КОНФИГУРАЦИЯ
# ============================================================
st.title("🎯 BingX Hunter Pro v3.1")
st.subheader("Лонг/Шорт • Реальные данные • Тех.анализ • Процент успеха")

# ============================================================
# 2. ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ (С ЗАЩИТОЙ ОТ ОШИБОК)
# ============================================================

# Встроенный список популярных мемкоинов BingX (запасной вариант)
BINGX_MEME_LIST = [
    "DOGE-USDT", "SHIB-USDT", "PEPE-USDT", "BONK-USDT", "FLOKI-USDT",
    "WIF-USDT", "TURBO-USDT", "BOME-USDT", "MYRO-USDT", "POPCAT-USDT",
    "SLERF-USDT", "SAMO-USDT", "MOG-USDT", "LADYS-USDT", "DOG-USDT",
    "PEOPLE-USDT", "1000PEPE-USDT", "1000BONK-USDT", "1000FLOKI-USDT"
]

@st.cache_data(ttl=30)
def get_coingecko_meme_data():
    """
    Основной источник: CoinGecko (бесплатно, без ограничений).
    Возвращает список мемкоинов с ценами, объёмами, high/low.
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
        
        if response.status_code == 429:
            st.warning("⏳ CoinGecko: слишком много запросов. Жду 60 секунд...")
            time.sleep(60)
            response = requests.get(url, params=params, timeout=15)
        
        data = response.json()
        
        coins = []
        for item in data:
            high = item.get("high_24h", 0) or item.get("current_price", 0) * 1.05
            low = item.get("low_24h", 0) or item.get("current_price", 0) * 0.95
            price = item.get("current_price", 0)
            
            if low > 0 and price > 0:
                amplitude = ((high - low) / low) * 100
            else:
                amplitude = 0
            
            coins.append({
                "symbol": item["symbol"].upper(),
                "name": item["name"],
                "price": price,
                "volume_24h": item.get("total_volume", 0),
                "change_24h": item.get("price_change_percentage_24h", 0),
                "market_cap": item.get("market_cap", 0),
                "high_24h": high,
                "low_24h": low,
                "amplitude_24h": amplitude,
                "on_bingx": item["symbol"].upper() in [b.split("-")[0] for b in BINGX_MEME_LIST]
            })
        
        return coins
    except Exception as e:
        st.error(f"Ошибка CoinGecko: {e}")
        return []

@st.cache_data(ttl=60)
def get_tradingview_signals(symbols):
    """
    TradingView технический анализ через бесплатный сканер.
    С защитой от ошибок.
    """
    tv_data = {}
    
    for sym in symbols[:15]:  # Ограничиваем до 15 для скорости
        try:
            clean = sym.replace("USDT", "").replace("-", "")
            url = "https://scanner.tradingview.com/crypto/scan"
            body = {
                "symbols": {"tickers": [f"BINANCE:{clean}USDT"]},
                "columns": ["Recommend.All|1"]
            }
            resp = requests.post(url, json=body, timeout=8)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and len(data["data"]) > 0:
                    val = data["data"][0]["d"][0]
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
            else:
                tv_data[sym] = {"signal": "⚪ WAIT", "score": 0}
        except:
            tv_data[sym] = {"signal": "⚪ WAIT", "score": 0}
        
        time.sleep(0.3)  # Пауза чтобы не забанили
    
    return tv_data

# ============================================================
# 3. РАСЧЁТЫ
# ============================================================

def calculate_trade(entry_price, leverage, target_profit_percent, side="LONG"):
    price_move = target_profit_percent / leverage
    
    if side == "LONG":
        exit_price = entry_price * (1 + price_move / 100)
        stop_loss = entry_price * (1 - (price_move * 0.4) / 100)
        liq_price = entry_price * (1 - (95 / leverage) / 100)
    else:
        exit_price = entry_price * (1 - price_move / 100)
        stop_loss = entry_price * (1 + (price_move * 0.4) / 100)
        liq_price = entry_price * (1 + (95 / leverage) / 100)
    
    return exit_price, stop_loss, liq_price, price_move

def calculate_success_probability(amplitude_24h, needed_move, tv_signal, volume_rank, change_24h):
    score = 0
    
    # Амплитуда (40%)
    amp_ratio = min(amplitude_24h / max(needed_move, 0.01), 3)
    score += min(amp_ratio * 13.33, 40)
    
    # TradingView (30%)
    if "STRONG BUY" in tv_signal:
        score += 30
    elif "BUY" in tv_signal:
        score += 22
    elif "NEUTRAL" in tv_signal:
        score += 12
    elif "WAIT" in tv_signal:
        score += 8
    else:
        score += 3
    
    # Объём (20%)
    score += max(20 - volume_rank * 1.5, 0)
    
    # Тренд 24ч (10%)
    if 1 < change_24h < 25:
        score += 10
    elif -8 < change_24h <= 1:
        score += 8
    elif change_24h >= 25:
        score += 4
    else:
        score += 2
    
    return min(round(score), 95)

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
    st.subheader("💰 ЦЕЛЬ")
    
    target_profit = st.number_input(
        "Прибыль (% к депозиту)",
        min_value=10, max_value=5000, value=100, step=10
    )
    leverage = st.selectbox("⚡ Плечо", [1, 2, 3, 5, 10, 15, 20, 25, 50, 75, 100, 125], index=5)
    
    needed_move = target_profit / leverage
    
    st.divider()
    st.subheader("🎯 НАПРАВЛЕНИЕ")
    trade_side = st.radio("Тип сделки", ["📈 LONG", "📉 SHORT"], index=0)
    side_code = "LONG" if "LONG" in trade_side else "SHORT"
    
    st.divider()
    st.subheader("🔍 ФИЛЬТРЫ")
    min_volume = st.slider("Мин. объём (24ч, $)", 5000, 100000000, 50000, 5000)
    min_success = st.slider("Мин. процент успеха (%)", 10, 90, 45, 5)
    show_only_bingx = st.checkbox("✅ Только пары с BingX", value=False)
    
    st.divider()
    if st.button("🔄 ОБНОВИТЬ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.caption(f"Цель: +{target_profit}% | Плечо: x{leverage}")
    st.caption(f"Движение цены: {needed_move:.1f}%")
    st.caption("📡 CoinGecko + TradingView")

# ============================================================
# 5. ЗАГРУЗКА И ОБРАБОТКА
# ============================================================
with st.spinner("📡 Загружаю данные... Это может занять до 30 секунд..."):
    coins = get_coingecko_meme_data()
    timestamp = datetime.now()

if not coins:
    st.error("❌ Не удалось загрузить данные. Попробуй обновить через минуту.")
    st.stop()

# Фильтруем по объёму и BingX
filtered = []
for coin in coins:
    if coin["volume_24h"] < min_volume:
        continue
    if show_only_bingx and not coin["on_bingx"]:
        continue
    filtered.append(coin)

filtered.sort(key=lambda x: x["volume_24h"], reverse=True)
filtered = filtered[:30]

if not filtered:
    st.warning("❌ Нет монет. Снизь мин. объём или выключи фильтр BingX.")
    st.stop()

# TradingView сигналы
symbols_tv = [c["symbol"] + "USDT" for c in filtered]
tv_data = get_tradingview_signals(symbols_tv)

# ============================================================
# 6. РАСЧЁТЫ ДЛЯ КАЖДОЙ МОНЕТЫ
# ============================================================
results = []

for idx, coin in enumerate(filtered):
    entry = coin["price"]
    sym_key = coin["symbol"] + "USDT"
    tv = tv_data.get(sym_key, {"signal": "⚪ WAIT", "score": 0})
    
    # LONG
    exit_l, stop_l, liq_l, move_l = calculate_trade(entry, leverage, target_profit, "LONG")
    prob_l = calculate_success_probability(
        coin["amplitude_24h"], needed_move, tv["signal"], idx, coin["change_24h"]
    )
    
    # SHORT
    exit_s, stop_s, liq_s, move_s = calculate_trade(entry, leverage, target_profit, "SHORT")
    # Для шорта инвертируем сигнал TV
    tv_inv = tv["signal"]
    if "BUY" in tv_inv and "STRONG" not in tv_inv:
        tv_inv = "🔴 SELL"
    elif "STRONG BUY" in tv_inv:
        tv_inv = "🔴 STRONG SELL"
    elif "SELL" in tv_inv and "STRONG" not in tv_inv:
        tv_inv = "🟢 BUY"
    elif "STRONG SELL" in tv_inv:
        tv_inv = "🟢 STRONG BUY"
    
    prob_s = calculate_success_probability(
        coin["amplitude_24h"], needed_move, tv_inv, idx, -coin["change_24h"]
    )
    
    # Текущее направление
    if side_code == "LONG":
        exit_p = exit_l
        stop_p = stop_l
        liq_p = liq_l
        prob = prob_l
    else:
        exit_p = exit_s
        stop_p = stop_s
        liq_p = liq_s
        prob = prob_s
    
    if prob < min_success:
        continue
    
    price_fmt = ".8f" if entry < 0.01 else ".6f" if entry < 1 else ".4f"
    
    results.append({
        "Монета": f"${coin['symbol']}",
        "Название": coin["name"],
        "Цена": entry,
        "Цена строка": f"${entry:{price_fmt}}",
        "Объём 24ч": f"${coin['volume_24h']:,.0f}",
        "Амплитуда": f"{coin['amplitude_24h']:.1f}%",
        "24ч": f"{coin['change_24h']:+.1f}%",
        "TV": tv["signal"],
        "BingX": "✅" if coin["on_bingx"] else "—",
        "🎯 Выход": f"${exit_p:{price_fmt}}",
        "🛑 Стоп": f"${stop_p:{price_fmt}}",
        "💀 Ликв.": f"${liq_p:{price_fmt}}",
        "⚡ Движ.": f"{move_l:.1f}%",
        "✅ LONG": f"{prob_l}%",
        "❌ SHORT": f"{prob_s}%",
        "Сигнал": get_success_label(prob),
        "Прибыль": f"+{target_profit}%",
        "prob_raw": prob,
        "prob_l": prob_l,
        "prob_s": prob_s
    })

# ============================================================
# 7. ОТОБРАЖЕНИЕ
# ============================================================
st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Цель", f"+{target_profit}%")
with col2:
    st.metric("⚡ Плечо", f"x{leverage}")
with col3:
    st.metric("📈 Движение", f"{needed_move:.1f}%")
with col4:
    st.metric("💡 Найдено", len(results))

st.divider()

if not results:
    st.warning("❌ Все монеты отсеяны по проценту успеха. Снизь мин. успех.")
    st.stop()

st.success(f"✅ Загружено: {timestamp.strftime('%H:%M:%S')} | CoinGecko + TradingView")

# Таблица
df = pd.DataFrame(results)
st.dataframe(
    df[["Монета", "Цена строка", "Объём 24ч", "Амплитуда", "24ч", "TV", "BingX",
        "🎯 Выход", "🛑 Стоп", "✅ LONG", "❌ SHORT", "Сигнал", "Прибыль"]],
    use_container_width=True,
    hide_index=True
)

# ============================================================
# 8. ЛУЧШИЙ СИГНАЛ
# ============================================================
st.divider()
st.subheader("🔥 ЛУЧШИЙ СИГНАЛ")

results.sort(key=lambda x: x["prob_raw"], reverse=True)
best = results[0]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🏆 Монета", f"{best['Монета']} ({best['Название']})")
with col2:
    st.metric("💵 Вход", best["Цена строка"])
with col3:
    st.metric("📊 Успех", best["Сигнал"])

st.info(f"""
### 📋 План сделки ({side_code})

| Параметр | Значение |
|----------|----------|
| **Пара** | {best['Монета'].replace('$','')}/USDT на {exchange} |
| **Тип** | {trade_side} |
| **Плечо** | x{leverage} |
| **Вход** | {best['Цена строка']} |
| **Выход (ТП)** | {best['🎯 Выход']} |
| **Стоп-лосс** | {best['🛑 Стоп']} |
| **Ликвидация** | {best['💀 Ликв.']} |
| **Движение цены** | {best['⚡ Движ.']} |
| **Процент успеха** | {best['Сигнал']} |
| **Прибыль** | **{best['Прибыль']}** |
""")

# График сравнения LONG vs SHORT
st.divider()
st.subheader("📊 LONG vs SHORT (первые 10)")

chart_df = pd.DataFrame({
    "Монета": [r["Монета"] for r in results[:10]],
    "LONG %": [r["prob_l"] for r in results[:10]],
    "SHORT %": [r["prob_s"] for r in results[:10]]
})

st.bar_chart(
    chart_df.set_index("Монета"),
    use_container_width=True,
    color=["#00ff88", "#ff4444"]
)

st.divider()
st.caption("### Формула успеха: Амплитуда (40%) + TV сигнал (30%) + Объём (20%) + Тренд (10%)")
st.caption(f"📡 CoinGecko API + TradingView Scanner | {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("⚠️ Всегда ставь стоп-лосс. Не рискуй больше 1-2% депозита в одной сделке.")