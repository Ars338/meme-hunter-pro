import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="BingX Hunter Pro", page_icon="🎯", layout="wide")

st.title("🎯 BingX Hunter Pro")
st.subheader("Поиск мемкоинов с проверкой реалистичности движения")

# ---------- Загрузка данных с CoinGecko ----------
@st.cache_data(ttl=30)
def fetch_real_meme_coins():
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
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        coins = []
        for item in data:
            # Проверяем, что все нужные поля есть
            high = item.get("high_24h", 0)
            low = item.get("low_24h", 0)
            
            # Считаем амплитуду (реальный размах движения за 24ч)
            if high and low and low > 0:
                amplitude = ((high - low) / low) * 100
            else:
                amplitude = 0
            
            coins.append({
                "symbol": item["symbol"].upper(),
                "name": item["name"],
                "price": item["current_price"],
                "volume_24h": item["total_volume"],
                "change_24h": item.get("price_change_percentage_24h", 0),
                "market_cap": item["market_cap"],
                "high_24h": high,
                "low_24h": low,
                "amplitude_24h": amplitude  # На сколько % двигалась за 24ч
            })
        
        return coins
    except Exception as e:
        st.error(f"Ошибка загрузки CoinGecko: {e}")
        return []

# ---------- Расчёт ----------
def calculate_trade(entry_price, leverage, target_profit_percent):
    price_move_percent = target_profit_percent / leverage
    exit_price_long = entry_price * (1 + price_move_percent / 100)
    exit_price_short = entry_price * (1 - price_move_percent / 100)
    
    stop_loss_percent = target_profit_percent * 0.5
    stop_move = stop_loss_percent / leverage
    stop_price_long = entry_price * (1 - stop_move / 100)
    stop_price_short = entry_price * (1 + stop_move / 100)
    
    return exit_price_long, exit_price_short, price_move_percent, stop_price_long, stop_price_short

def get_chance_level(amplitude, needed_move):
    """
    Оценивает шанс, что монета сделает нужное движение.
    Если амплитуда за 24ч >= нужного движения — HIGH.
    """
    if amplitude <= 0:
        return "⚪ N/A", 0
    ratio = amplitude / needed_move
    if ratio >= 1.5:
        return "🟢 HIGH", ratio
    elif ratio >= 0.8:
        return "🟡 MEDIUM", ratio
    else:
        return "🔴 LOW", ratio

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
    
    # Нужное движение цены
    needed_move = target_profit / leverage
    
    st.divider()
    st.subheader("🔍 Фильтры реалистичности")
    
    min_volume = st.slider(
        "Мин. объём торгов (24ч, $)",
        10000, 5000000, 50000, 10000
    )
    
    max_change = st.slider(
        "Макс. изменение за 24ч (%)",
        0, 2000, 500, 50,
        help="Отсеивает монеты, которые уже улетели"
    )
    
    # НОВЫЙ ФИЛЬТР: минимальная амплитуда
    min_amplitude = st.slider(
        "Мин. амплитуда за 24ч (%)",
        0, 100, int(needed_move * 0.7), 1,
        help=f"Показывает монеты, которые ходили минимум на это значение. Для твоей цели ({needed_move:.1f}%) рекомендую ≥ {needed_move:.1f}%"
    )
    
    only_realistic = st.checkbox(
        "✅ Только реалистичные (шанс HIGH/MEDIUM)",
        value=True,
        help="Скрывает монеты, которые не дадут нужное движение"
    )
    
    st.divider()
    
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()
    
    st.caption(f"🎯 Цель: +{target_profit}% | Плечо: x{leverage}")
    st.caption(f"📈 Нужное движение цены: {needed_move:.1f}%")
    st.caption("📡 Данные: CoinGecko API")

# ---------- Основной экран ----------
st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Цель", f"+{target_profit}% к депозиту")
with col2:
    st.metric("⚡ Плечо", f"x{leverage}")
with col3:
    st.metric("📈 Нужное движение", f"{needed_move:.1f}%")
with col4:
    st.metric("📐 Мин. амплитуда", f"{min_amplitude:.1f}%")

st.divider()

# Загружаем
with st.spinner("📡 Загружаю реальные данные с CoinGecko..."):
    all_coins = fetch_real_meme_coins()
    timestamp = datetime.now()

if not all_coins:
    st.error("Не удалось загрузить данные. Попробуй обновить.")
    st.stop()

# Фильтруем с проверкой амплитуды
filtered = []
dropped_low_amplitude = 0

for coin in all_coins:
    volume_ok = coin["volume_24h"] and coin["volume_24h"] >= min_volume
    change_ok = abs(coin["change_24h"]) <= max_change if coin["change_24h"] else True
    price_ok = coin["price"] and coin["price"] > 0
    amplitude_ok = coin["amplitude_24h"] >= min_amplitude
    
    if not amplitude_ok:
        dropped_low_amplitude += 1
    
    if volume_ok and change_ok and price_ok and amplitude_ok:
        filtered.append(coin)

# Сортируем: сначала с лучшим шансом
filtered.sort(key=lambda x: x["amplitude_24h"], reverse=True)
filtered = filtered[:30]

if not filtered:
    st.warning(f"""
    ❌ Нет монет с такими параметрами.
    Причина: {dropped_low_amplitude} монет отсеяны по амплитуде (< {min_amplitude}%).
    Попробуй: снизить мин. амплитуду или убрать галочку "Только реалистичные".
    """)
    st.stop()

st.success(f"✅ Найдено {len(filtered)} монет | Отсеяно по амплитуде: {dropped_low_amplitude} | Обновлено: {timestamp.strftime('%H:%M:%S')}")

# Таблица с шансами
results = []
for coin in filtered:
    entry = coin["price"]
    exit_long, _, move_pct, stop_long, _ = calculate_trade(entry, leverage, target_profit)
    chance_label, ratio = get_chance_level(coin["amplitude_24h"], needed_move)
    
    # Фильтр "только реалистичные"
    if only_realistic and chance_label == "🔴 LOW":
        continue
    
    results.append({
        "Монета": f"${coin['symbol']}",
        "Цена сейчас": f"${entry:.6f}" if entry < 1 else f"${entry:.4f}",
        "Объём 24ч": f"${coin['volume_24h']:,.0f}",
        "Амплитуда 24ч": f"{coin['amplitude_24h']:.1f}%",
        "Изменение 24ч": f"{coin['change_24h']:+.1f}%",
        "🎯 Цена выхода": f"${exit_long:.6f}" if exit_long < 1 else f"${exit_long:.4f}",
        "🛑 Стоп-лосс": f"${stop_long:.6f}" if stop_long < 1 else f"${stop_long:.4f}",
        "Нужное движение": f"{move_pct:.1f}%",
        "ШАНС": chance_label,
        "Прибыль": f"+{target_profit}%"
    })

if not results:
    st.warning("Все найденные монеты имеют низкий шанс. Сними галочку 'Только реалистичные' или уменьши амплитуду.")
    st.stop()

df = pd.DataFrame(results)

# Показываем таблицу с цветами
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "ШАНС": st.column_config.TextColumn(width="small"),
        "Амплитуда 24ч": st.column_config.TextColumn(width="small"),
        "Прибыль": st.column_config.TextColumn(width="small"),
    }
)

# Лучшая монета (с наивысшим шансом)
st.divider()
st.subheader("🔥 ЛУЧШАЯ МОНЕТА С РЕАЛЬНЫМ ШАНСОМ")

# Берём монету с максимальной амплитудой
best_coin = filtered[0]
for coin in filtered:
    if coin["amplitude_24h"] > best_coin["amplitude_24h"]:
        best_coin = coin

entry_best = best_coin["price"]
exit_best, _, move_best, stop_best, _ = calculate_trade(entry_best, leverage, target_profit)
chance_best, ratio_best = get_chance_level(best_coin["amplitude_24h"], needed_move)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🏆 Монета", f"${best_coin['symbol']} ({best_coin['name']})")
with col2:
    st.metric("💵 Цена входа", f"${entry_best:.6f}" if entry_best < 1 else f"${entry_best:.4f}")
with col3:
    st.metric("🎯 Цена выхода", f"${exit_best:.6f}" if exit_best < 1 else f"${exit_best:.4f}")
with col4:
    st.metric("🎲 Шанс", chance_best)

st.info(f"""
📋 **План сделки на {exchange}:**

| Параметр | Значение |
|----------|----------|
| Пара | {best_coin['symbol']}/USDT |
| Плечо | x{leverage} |
| Цена входа | ${entry_best:.8f} |
| Цена выхода (ТП) | ${exit_best:.8f} |
| Цена стоп-лосса | ${stop_best:.8f} |
| Движение для цели | {move_best:.1f}% |
| **Амплитуда за 24ч** | **{best_coin['amplitude_24h']:.1f}%** (запас x{ratio_best:.1f}) |
| Шанс реализовать | {chance_best} |
| Прибыль к депозиту | +{target_profit}% |
| Убыток при стопе | -{target_profit * 0.5:.0f}% к депозиту |
""")

# Статистика по шансам
st.divider()
st.subheader("📊 Распределение шансов")

high_count = sum(1 for _, _, chance, _, _ in [() for _ in results] if "HIGH" in str(results))
real_results = []
for coin in filtered:
    chance_label, _ = get_chance_level(coin["amplitude_24h"], needed_move)
    real_results.append(chance_label)

high_count = real_results.count("🟢 HIGH")
medium_count = real_results.count("🟡 MEDIUM")
low_count = real_results.count("🔴 LOW")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🟢 HIGH (уверенно)", high_count)
with col2:
    st.metric("🟡 MEDIUM (на грани)", medium_count)
with col3:
    st.metric("🔴 LOW (маловероятно)", low_count)

# Подвал
st.divider()
st.caption(f"📡 Данные: CoinGecko API | Обновлено: {timestamp.strftime('%H:%M:%S')}")
st.caption(f"🎯 Цель: +{target_profit}% | Плечо: x{leverage} | Нужное движение: {needed_move:.1f}%")
st.caption(f"📐 Мин. амплитуда: {min_amplitude:.1f}% | Монет с низкой амплитудой отсеяно: {dropped_low_amplitude}")
st.caption("⚠️ Шанс основан на 24ч амплитуде. Не гарантия. Всегда ставь стоп-лосс.")