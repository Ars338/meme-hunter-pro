import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Meme Hunter Pro", page_icon="🔫", layout="wide")

st.title("🔫 Meme Hunter Pro")
st.subheader("Мульти-факторный анализатор мемкоинов")

# Выбор блокчейна
chain = st.selectbox("Выбери блокчейн", ["solana", "bsc", "ethereum", "base"])
min_liq = st.slider("Минимальная ликвидность ($)", 1000, 100000, 10000, 1000)

if st.button("🔍 ИСКАТЬ МОНЕТУ", type="primary"):
    
    # Запрос к DexScreener
    url = f"https://api.dexscreener.com/latest/dex/search?q={chain}"
    
    with st.spinner("Сканирую биржи..."):
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            pairs = data.get('pairs', [])
            
            # Фильтрация
            filtered = [p for p in pairs[:30] if p.get('liquidity', {}).get('usd', 0) > min_liq]
            
            if not filtered:
                st.warning("Ничего не найдено. Снизь требования к ликвидности.")
            else:
                p = filtered[0]
                token = p.get('baseToken', {}).get('symbol', 'N/A')
                price = p.get('priceUsd', 0)
                liquidity = p.get('liquidity', {}).get('usd', 0)
                change = p.get('priceChange', {}).get('h24', 0)
                dex = p.get('dexId', 'N/A')
                
                # Три колонки
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("💰 Цена", f"${float(price):.8f}")
                    st.metric("💧 Ликвидность", f"${liquidity:,.0f}")
                    st.metric("🏪 Биржа", dex.upper())
                
                with col2:
                    st.metric("📈 Изменение 24ч", f"{change:.2f}%")
                    
                    # Имитация RSI
                    rsi = np.random.randint(25, 75)
                    color = "🟢" if rsi < 40 else "🔴" if rsi > 65 else "🟡"
                    st.metric("📐 RSI (14)", f"{color} {rsi}")
                    
                    # Имитация CVD
                    cvd = np.random.choice(["ВВЕРХ", "ВНИЗ"])
                    st.metric("📊 CVD тренд", cvd)
                
                with col3:
                    # Сигнал
                    if rsi < 40 and cvd == "ВВЕРХ":
                        signal = "✅ СИЛЬНЫЙ ВХОД"
                        st.success(f"### {signal}")
                        st.write("**Цена входа:** рынок")
                        st.write("**Стоп:** -3%")
                        st.write("**Тейк:** +40-200%")
                    elif rsi > 65 and cvd == "ВНИЗ":
                        st.error("### 🚫 НЕ ВХОДИТЬ")
                    else:
                        st.warning("### ⏳ ЖДАТЬ")
                
                # Социальный фон
                st.subheader("🌐 Социальный фон (заглушка)")
                social_data = {
                    'Telegram': ['320', 'Бычий'],
                    'Twitter': ['180', 'Бычий'],
                    'Reddit': ['45', 'Нейтральный'],
                    '4chan': ['89', 'Бычий'],
                    'Discord': ['210', 'Бычий'],
                    'BitcoinTalk': ['23', 'Медвежий']
                }
                st.dataframe(pd.DataFrame.from_dict(social_data, orient='index', columns=['Упоминаний', 'Настроение']))
                
        except Exception as e:
            st.error(f"Ошибка: {e}")

st.divider()
st.caption("Meme Hunter Pro v0.1 | Только для демо | Не финансовый совет")