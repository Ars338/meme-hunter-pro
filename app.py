import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time

st.set_page_config(page_title="BingX Hunter Pro", page_icon="🎯", layout="wide")

st.title("🎯 BingX Hunter Pro")
st.subheader("Поиск мемкоинов с реальными данными и точным расчётом входа/выхода")

# ---------- Функция для загрузки реальных данных с CoinGecko ----------
@st.cache_data(ttl=30)  # Кешируем на 30 секунд
def fetch_real_meme_coins():
    """
    Загружает реальные мемкоины с CoinGecko API.
    Бесплатно, без ключа.
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme-token",  # Только мемкоины
        "order": "volume_desc",     # Сортируем по объёму
        "per_page": 100,            # 100 монет
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        coins = []
        for item in data:
            coins.append({
                "symbol": item["symbol"].upper(),
                "name": item["name"],
                "price": item["current_price"],
                "volume_24h": item["total_volume"],
                "change_24h": item.get("price_change_percentage_24h", 0),
                "market_cap": item["market_cap"],
                "high_24h": item["high_24h"],
                "low_24h": item["low_24h"]
            })
        
        return coins
    except Exception as e:
        st.error(f"Ошибка загрузки CoinGecko: {e}")
        return []

# ---------- Функция для поиска мемкоинов на BingX ----------
@st.cache_data(ttl=30)
def fetch_bingx_meme_list():
    """
    Пытается получить список мемкоинов, доступных на BingX.
    Если не получается - используем весь список с CoinGecko.
    """
    try:
        # Пробуем API BingX для получения списка торговых пар
        url = "https://open-api.bingx.com/openApi/spot/v1/common/symbols"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            symbols = data.get("data", {}).get("symbols", [])
            # Фильтруем только USDT пары
            bingx_coins = [s["symbol"].replace("-USDT", "").upper() for s in symbols if "USDT" in s["symbol"]]
            return bingx_coins
    except:
        pass
    
    # Если BingX API недоступен - возвращаем None (будем показывать все)
    return None

# ---------- Функция расчёта ----------
def calculate_trade(entry_price, leverage, target_profit_percent):
    """
    Считает цену выхода и стоп-лосс.
    """
    price_move_percent = target_profit_percent / leverage
    exit_price_long = entry_price * (1 + price_move_percent / 100)
    exit_price_short = entry_price * (1 - price_move_percent / 100)
    
    # Стоп-лосс: 50% от целевого профита
    stop_loss_percent = target_profit_percent * 0.5
    stop_move = stop_loss_percent / leverage
    stop_price_long = entry_price * (1 - stop_move / 100)
    stop_price_short = entry_price * (1 + stop_move / 100)
    
    return exit_price_long, exit_price_short, price_move_percent, stop_price_long, stop_price_short

# ---------- Боковая панель ----------
with st.sidebar:
    st.header("⚙️ Твои настройки")
    
    exchange = st.selectbox(
        "🏪 Биржа",
        ["BingX", "Bybit", "MEXC", "OKX", "Gate.io"],
        index=0
    )
    
    st.divider()
    st.subheader("💰 Цель по прибыли")
    
    target_profit = st.number_input(
        "Прибыль со сделки (% к депозиту)",
        min_value=10,
        max_value=2000,
        value=100,
        step=10
    )
    
    leverage = st.selectbox(
        "⚡ Плечо",
        [1, 2, 3, 5, 10, 20, 25, 50, 75, 100, 125],
        index=5
    )
    
    st.divider()
    st.subheader("🔍 Фильтры")
    
    min_volume = st.slider(
        "Мин. объём торгов (24ч, $)",
        10000, 5000000, 100000, 10000
    )
    
    max_change = st.slider(
        "Макс. изменение за 24ч (%)",
        0, 2000, 500, 50,
        help="Отсеивает монеты, которые уже сделали слишком большой рост"
    )
    
    show_bingx_only = st.checkbox("Только монеты с BingX", value=True, help="Показывает монеты, которые точно есть на BingX")
    
    st.divider()
    
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()
    
    st.caption(f"🎯 Цель: +{target_profit}% | Плечо: x{leverage}")
    st.caption(f"💡 Нужное движение цены: {target_profit / leverage:.1f}%")
    st.caption("📡 Данные: CoinGecko API")

# ---------- Основной экран ----------
st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🎯 Целевая прибыль", f"+{target_profit}% к депозиту")
with col2:
    st.metric("⚡ Плечо", f"x{leverage}")
with col3:
    move_needed = target_profit / leverage
    st.metric("📈 Нужное движение цены", f"{move_needed:.1f}%")

st.divider()

# Загружаем данные
with st.spinner("📡 Загружаю реальные данные с CoinGecko..."):
    all_coins = fetch_real_meme_coins()
    bingx_list = fetch_bingx_meme_list() if show_bingx_only else None
    timestamp = datetime.now()

if not all_coins:
    st.error("Не удалось загрузить данные. Попробуй обновить.")
    st.stop()

# Фильтруем
filtered = []
for coin in all_coins:
    volume_ok = coin["volume_24h"] and coin["volume_24h"] >= min_volume
    change_ok = abs(coin["change_24h"]) <= max_change if coin["change_24h"] else True
    bingx_ok = (bingx_list is None) or (coin["symbol"] in bingx_list)
    price_ok = coin["price"] and coin["price"] > 0
    
    if volume_ok and change_ok and bingx_ok and price_ok:
        filtered.append(coin)

# Сортируем по объёму
filtered.sort(key=lambda x: x["volume_24h"] or 0, reverse=True)
filtered = filtered[:30]  # Топ-30

if not filtered:
    st.warning("Монет с такими фильтрами не найдено. Увеличь макс. изменение или снизь мин. объём.")
    st.stop()

st.success(f"✅ Найдено {len(filtered)} монет | Обновлено: {timestamp.strftime('%H:%M:%S')}")

# Таблица с расчётами
results = []
for coin in filtered:
    entry = coin["price"]
    exit_long, exit_short, move_pct, stop_long, stop_short = calculate_trade(entry, leverage, target_profit)
    
    results.append({
        "Монета": f"${coin['symbol']}",
        "Название": coin["name"],
        "Цена сейчас": f"${entry:.8f}" if entry < 0.01 else f"${entry:.6f}" if entry < 1 else f"${entry:.4f}",
        "Объём 24ч": f"${coin['volume_24h']:,.0f}",
        "Изменение 24ч": f"{coin['change_24h']:+.1f}%",
        "🎯 Выход ЛОНГ": f"${exit_long:.8f}" if exit_long < 0.01 else f"${exit_long:.6f}",
        "🛑 Стоп ЛОНГ": f"${stop_long:.8f}" if stop_long < 0.01 else f"${stop_long:.6f}",
        "📊 Движение": f"{move_pct:.1f}%",
        "💰 Прибыль": f"+{target_profit}%"
    })

df = pd.DataFrame(results)

# Стилизуем таблицу
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Монета": st.column_config.TextColumn(width="small"),
        "🎯 Выход ЛОНГ": st.column_config.TextColumn(width="small"),
        "💰 Прибыль": st.column_config.TextColumn(width="small"),
    }
)

# Лучшая монета (с наилучшим соотношением объём/изменение)
st.divider()
st.subheader("🔥 ЛУЧШАЯ МОНЕТА ПОД ТВОЮ ЦЕЛЬ")

# Ищем монету с хорошим объёмом и умеренным изменением (не перегрета)
best_coin = None
for coin in filtered:
    if coin["change_24h"] and abs(coin["change_24h"]) < 50 and coin["volume_24h"] > min_volume * 2:
        best_coin = coin
        break

if not best_coin:
    best_coin = filtered[0]  # Если нет идеальной - берём первую

entry_best = best_coin["price"]
exit_best, _, move_best, stop_best, _ = calculate_trade(entry_best, leverage, target_profit)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🏆 Монета", f"${best_coin['symbol']} ({best_coin['name']})")
with col2:
    st.metric("💵 Цена входа", f"${entry_best:.8f}" if entry_best < 0.01 else f"${entry_best:.6f}")
with col3:
    st.metric("🎯 Цена выхода", f"${exit_best:.8f}" if exit_best < 0.01 else f"${exit_best:.6f}")
with col4:
    st.metric("📈 Твоя прибыль", f"+{target_profit}% к депозиту")

st.info(f"""
📋 **План сделки на {exchange}:**

| Параметр | Значение |
|----------|----------|
| Пара | {best_coin['symbol']}/USDT |
| Плечо | x{leverage} |
| Цена входа | ${entry_best:.8f} |
| Цена выхода (тейк-профит) | ${exit_best:.8f} |
| Цена стоп-лосса | ${stop_best:.8f} |
| Движение цены для цели | {move_best:.1f}% |
| Прибыль к депозиту | +{target_profit}% |
| Убыток при стопе | -{target_profit * 0.5:.0f}% к депозиту |
""")

# График волатильности
st.divider()
st.subheader("📊 Волатильность найденных монет")

chart_data = pd.DataFrame({
    "Монета": [f"${c['symbol']}" for c in filtered[:10]],
    "Изменение за 24ч (%)": [c["change_24h"] for c in filtered[:10]],
    "Объём (млн $)": [c["volume_24h"] / 1_000_000 for c in filtered[:10]]
})

col_chart1, col_chart2 = st.columns(2)
with col_chart1:
    st.bar_chart(chart_data.set_index("Монета")["Изменение за 24ч (%)"], use_container_width=True)
with col_chart2:
    st.bar_chart(chart_data.set_index("Монета")["Объём (млн $)"], use_container_width=True)

# Подвал
st.divider()
st.caption(f"📡 Данные: CoinGecko API (реальные) | Обновлено: {timestamp.strftime('%H:%M:%S')} | Обновится через 30 сек")
st.caption(f"🎯 Цель: +{target_profit}% к депозиту | Плечо: x{leverage} | Нужное движение цены: {target_profit / leverage:.1f}%")
st.caption("⚠️ Только для анализа. Не финансовая рекомендация.")