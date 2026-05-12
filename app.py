import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time

st.set_page_config(page_title="BingX Hunter Pro", page_icon="🎯", layout="wide")

st.title("🎯 BingX Hunter Pro v3.3")
st.subheader("Лонг/Шорт • Реальные данные • Процент успеха")

# ============================================================
# РЕЗЕРВНЫЕ ДАННЫЕ
# ============================================================
FALLBACK_COINS = [
    {"symbol": "DOGE", "name": "Dogecoin", "price": 0.12, "volume_24h": 450000000, "change_24h": 2.1, "high_24h": 0.125, "low_24h": 0.115},
    {"symbol": "SHIB", "name": "Shiba Inu", "price": 0.000023, "volume_24h": 210000000, "change_24h": -1.5, "high_24h": 0.000025, "low_24h": 0.000021},
    {"symbol": "PEPE", "name": "Pepe", "price": 0.0000078, "volume_24h": 180000000, "change_24h": 8.3, "high_24h": 0.0000085, "low_24h": 0.0000072},
    {"symbol": "BONK", "name": "Bonk", "price": 0.000021, "volume_24h": 95000000, "change_24h": 12.7, "high_24h": 0.000023, "low_24h": 0.000018},
    {"symbol": "FLOKI", "name": "Floki", "price": 0.00017, "volume_24h": 78000000, "change_24h": -3.2, "high_24h": 0.00019, "low_24h": 0.00016},
    {"symbol": "WIF", "name": "dogwifhat", "price": 2.45, "volume_24h": 120000000, "change_24h": -5.8, "high_24h": 2.70, "low_24h": 2.30},
    {"symbol": "TURBO", "name": "Turbo", "price": 0.0062, "volume_24h": 45000000, "change_24h": 22.1, "high_24h": 0.0071, "low_24h": 0.0051},
    {"symbol": "BOME", "name": "BOOK OF MEME", "price": 0.0092, "volume_24h": 65000000, "change_24h": 15.4, "high_24h": 0.0105, "low_24h": 0.0080},
    {"symbol": "POPCAT", "name": "Popcat", "price": 1.35, "volume_24h": 38000000, "change_24h": -2.3, "high_24h": 1.50, "low_24h": 1.28},
    {"symbol": "MOG", "name": "Mog Coin", "price": 0.0000013, "volume_24h": 32000000, "change_24h": 45.6, "high_24h": 0.0000016, "low_24h": 0.0000009},
    {"symbol": "MYRO", "name": "Myro", "price": 0.095, "volume_24h": 15000000, "change_24h": 3.2, "high_24h": 0.105, "low_24h": 0.088},
    {"symbol": "SLERF", "name": "Slerf", "price": 0.38, "volume_24h": 22000000, "change_24h": -11.2, "high_24h": 0.44, "low_24h": 0.36},
    {"symbol": "SAMO", "name": "Samoyedcoin", "price": 0.0085, "volume_24h": 8500000, "change_24h": 4.8, "high_24h": 0.0092, "low_24h": 0.0080},
    {"symbol": "LADYS", "name": "Milady Meme Coin", "price": 0.00000012, "volume_24h": 28000000, "change_24h": 67.3, "high_24h": 0.00000015, "low_24h": 0.00000008},
    {"symbol": "DOG", "name": "DOG•GO•TO•THE•MOON", "price": 0.0048, "volume_24h": 42000000, "change_24h": 9.1, "high_24h": 0.0053, "low_24h": 0.0044},
]

# ============================================================
# ФУНКЦИЯ ЗАГРУЗКИ
# ============================================================
@st.cache_data(ttl=60)
def load_coin_data():
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
        response = requests.get(url, params=params, timeout=20)
        data = response.json()
        
        if not isinstance(data, list) or len(data) == 0:
            return FALLBACK_COINS, False
        
        coins = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                symbol = str(item.get("symbol", "")).upper()
                name = str(item.get("name", symbol))
                price = float(item.get("current_price", 0))
                volume = float(item.get("total_volume", 0))
                change = float(item.get("price_change_percentage_24h", 0) or 0)
                high = float(item.get("high_24h", 0) or price * 1.05)
                low = float(item.get("low_24h", 0) or price * 0.95)
                
                if price <= 0:
                    continue
                
                amplitude = ((high - low) / low) * 100 if low > 0 else 0
                
                coins.append({
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "volume_24h": volume,
                    "change_24h": change,
                    "high_24h": high,
                    "low_24h": low,
                    "amplitude_24h": amplitude,
                })
            except:
                continue
        
        if len(coins) == 0:
            return FALLBACK_COINS, False
        
        return coins, True
    
    except Exception:
        return FALLBACK_COINS, False

# ============================================================
# РАСЧЁТЫ
# ============================================================
def calculate_trade(entry_price, leverage, target_profit, side):
    price_move = target_profit / leverage
    
    if side == "LONG":
        exit_price = entry_price * (1 + price_move / 100)
        stop_loss = entry_price * (1 - (price_move * 0.4) / 100)
        liq_price = entry_price * (1 - (95 / leverage) / 100)
    else:
        exit_price = entry_price * (1 - price_move / 100)
        stop_loss = entry_price * (1 + (price_move * 0.4) / 100)
        liq_price = entry_price * (1 + (95 / leverage) / 100)
    
    return exit_price, stop_loss, liq_price, price_move

def calculate_success(amplitude, needed_move, volume_rank, change_24h, side):
    score = 0
    
    # Амплитуда (50%)
    amp_ratio = min(amplitude / max(needed_move, 0.1), 3)
    score += min(amp_ratio * 16.6, 50)
    
    # Объём (30%)
    score += max(30 - volume_rank * 2.5, 0)
    
    # Тренд (20%)
    change = change_24h if change_24h is not None else 0
    
    if side == "LONG":
        if 2 < change < 25:
            score += 20
        elif -5 < change <= 2:
            score += 14
        elif change >= 25:
            score += 6
        else:
            score += 4
    else:
        if -25 < change < -2:
            score += 20
        elif -2 <= change < 5:
            score += 14
        elif change <= -25:
            score += 6
        else:
            score += 4
    
    return min(round(score), 92)

def get_label(prob):
    if prob >= 65:
        return f"🟢 HIGH ({prob}%)"
    elif prob >= 40:
        return f"🟡 MEDIUM ({prob}%)"
    else:
        return f"🔴 LOW ({prob}%)"

# ============================================================
# ИНТЕРФЕЙС
# ============================================================
with st.sidebar:
    st.header("⚙️ НАСТРОЙКИ")
    
    exchange = st.selectbox("🏪 Биржа", ["BingX", "Bybit", "MEXC", "OKX", "Gate.io"], index=0)
    
    st.divider()
    st.subheader("💰 ЦЕЛЬ")
    target_profit = st.number_input("Прибыль (% к депозиту)", 10, 5000, 100, 10)
    leverage = st.selectbox("Плечо", [1, 2, 3, 5, 10, 15, 20, 25, 50, 75, 100, 125], index=5)
    needed_move = target_profit / leverage
    
    st.divider()
    st.subheader("🎯 НАПРАВЛЕНИЕ")
    trade_side = st.radio("Тип", ["📈 LONG", "📉 SHORT"], index=0)
    side_code = "LONG" if "LONG" in trade_side else "SHORT"
    
    st.divider()
    st.subheader("🔍 ФИЛЬТРЫ")
    min_volume = st.slider("Мин. объём ($)", 5000, 200000000, 50000, 5000)
    min_success = st.slider("Мин. успех (%)", 10, 85, 40, 5)
    
    st.divider()
    if st.button("🔄 ОБНОВИТЬ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.caption(f"Цель: +{target_profit}% | Плечо: x{leverage} | Движение: {needed_move:.1f}%")

# ============================================================
# ЗАГРУЗКА
# ============================================================
with st.spinner("📡 Загружаю данные..."):
    coins, live = load_coin_data()
    timestamp = datetime.now()

if not coins:
    st.error("❌ Нет данных.")
    st.stop()

# Фильтрация
filtered = [c for c in coins if c["volume_24h"] >= min_volume]
filtered.sort(key=lambda x: x["volume_24h"], reverse=True)

st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📡 Статус", "🟢 Live" if live else "🟡 Кеш")
col2.metric("🎯 Цель", f"+{target_profit}%")
col3.metric("⚡ Плечо", f"x{leverage}")
col4.metric("📈 Движение", f"{needed_move:.1f}%")

st.divider()

# ============================================================
# РАСЧЁТ
# ============================================================
results = []

for idx, coin in enumerate(filtered[:20]):
    entry = coin["price"]
    exit_p, stop_p, liq_p, move_p = calculate_trade(entry, leverage, target_profit, side_code)
    
    # Считаем успех для LONG и SHORT отдельно
    prob_l = calculate_success(coin["amplitude_24h"], needed_move, idx, coin["change_24h"], "LONG")
    prob_s = calculate_success(coin["amplitude_24h"], needed_move, idx, coin["change_24h"], "SHORT")
    
    # Берём нужное направление
    prob = prob_l if side_code == "LONG" else prob_s
    
    if prob < min_success:
        continue
    
    fmt = ".8f" if entry < 0.01 else ".6f" if entry < 1 else ".4f"
    
    results.append({
        "Монета": f"${coin['symbol']}",
        "Цена": f"${entry:{fmt}}",
        "Объём": f"${coin['volume_24h']:,.0f}",
        "Ампл.": f"{coin['amplitude_24h']:.1f}%",
        "24ч": f"{coin['change_24h']:+.1f}%",
        "🎯 Выход": f"${exit_p:{fmt}}",
        "🛑 Стоп": f"${stop_p:{fmt}}",
        "⚡ Движ.": f"{move_p:.1f}%",
        "✅ LONG": f"{prob_l}%",
        "❌ SHORT": f"{prob_s}%",
        "Сигнал": get_label(prob),
        "Прибыль": f"+{target_profit}%",
        "prob": prob
    })

if not results:
    st.warning(f"❌ Все монеты отсеяны. Снизь мин. успех (сейчас {min_success}%).")
    st.stop()

st.success(f"✅ Найдено: {len(results)} | {timestamp.strftime('%H:%M:%S')}")

df = pd.DataFrame(results)
st.dataframe(
    df[["Монета", "Цена", "Объём", "Ампл.", "24ч", "🎯 Выход", "🛑 Стоп", "✅ LONG", "❌ SHORT", "Сигнал"]],
    use_container_width=True, hide_index=True
)

# ============================================================
# ЛУЧШИЙ СИГНАЛ
# ============================================================
st.divider()
st.subheader("🔥 ЛУЧШИЙ СИГНАЛ")

results.sort(key=lambda x: x["prob"], reverse=True)
best = results[0]

col1, col2, col3 = st.columns(3)
col1.metric("🏆", best["Монета"])
col2.metric("💵 Вход", best["Цена"])
col3.metric("📊 Успех", best["Сигнал"])

st.info(f"""
### 📋 План ({side_code})
| Параметр | Значение |
|----------|----------|
| Пара | {best['Монета'].replace('$','')}/USDT ({exchange}) |
| Плечо | x{leverage} |
| Вход | {best['Цена']} |
| Выход (ТП) | {best['🎯 Выход']} |
| Стоп-лосс | {best['🛑 Стоп']} |
| Движение | {best['⚡ Движ.']} |
| Прибыль | **{best['Прибыль']}** |
""")

st.divider()
st.caption(f"⚙️ Формула: Амплитуда (50%) + Объём (30%) + Тренд (20%) | {'Live' if live else 'Кеш'} | {timestamp}")
st.caption("⚠️ Всегда ставь стоп-лосс. Не рискуй больше 2% депозита.")