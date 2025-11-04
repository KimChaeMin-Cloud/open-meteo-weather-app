import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from dateutil import tz

st.set_page_config(page_title="🌍 Open-Meteo (No API Key)", layout="wide")
st.title("🌍 Open-Meteo — 현재 날씨 + 7일 예보 (회원가입/키 불필요)")

st.write("도시 이름으로 지오코딩(위·경도) → Open-Meteo로 현재 날씨와 7일 일별 예보를 보여줍니다.")

# ---- 입력 ----
col_city, col_days, col_unit = st.columns([2,1,1])
with col_city:
    city = st.text_input("도시 이름 (예: Seoul, Tokyo, New York)", value="Seoul")
with col_days:
    days = st.slider("예보 일수", 3, 14, 7)
with col_unit:
    temp_unit = st.selectbox("단위", ["celsius", "fahrenheit"], index=0)

# 한국 시간대 표기(원하면 'Asia/Seoul' 고정)
LOCAL_TZ = tz.gettz("Asia/Seoul")

def geocode_city(name: str):
    """Open-Meteo Geocoding API (무료, 무키)"""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": name, "count": 1, "language": "en", "format": "json"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "name": hit.get("name"),
        "country": hit.get("country"),
        "lat": hit.get("latitude"),
        "lon": hit.get("longitude"),
        "timezone": hit.get("timezone") or "auto"
    }

def fetch_weather(lat, lon, timezone="auto", unit="celsius", days=7):
    """Open-Meteo Forecast API (무료, 무키)"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
        "timezone": timezone,
        "forecast_days": days,
        "temperature_unit": unit,
        "windspeed_unit": "m/s",
        "precipitation_unit": "mm"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

if st.button("🔎 조회", type="primary"):
    if not city.strip():
        st.warning("도시 이름을 입력하세요.")
    else:
        try:
            g = geocode_city(city.strip())
            if not g:
                st.error("지오코딩 결과가 없습니다. 다른 도시명을 시도해보세요.")
            else:
                st.success(f"📍 {g['name']}, {g['country']}  (lat: {g['lat']}, lon: {g['lon']})")
                data = fetch_weather(g["lat"], g["lon"], timezone=g["timezone"], unit=temp_unit, days=days)

                # ---- 현재 날씨 카드 ----
                cur = data.get("current_weather", {})
                if cur:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("현재 기온", f"{cur.get('temperature','?')}°")
                    with col2:
                        st.metric("풍속", f"{cur.get('windspeed','?')} m/s")
                    with col3:
                        # time은 timezone 기준 ISO 문자열
                        t = cur.get("time")
                        if t:
                            try:
                                shown = datetime.fromisoformat(t).astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                shown = t
                            st.metric("관측시각", shown)

                # ---- 일별 예보 표/차트 ----
                daily = data.get("daily", {})
                if daily:
                    df_daily = pd.DataFrame(daily)
                    # 날짜를 인덱스로 정리
                    if "time" in df_daily.columns:
                        df_daily["date"] = pd.to_datetime(df_daily["time"]).dt.tz_localize(g["timezone"], nonexistent="NaT", ambiguous="NaT")
                        df_daily = df_daily.set_index("date")

                    st.subheader("🗓 7일 일별 예보")
                    show_cols = [c for c in ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "windspeed_10m_max"] if c in df_daily.columns]
                    st.dataframe(df_daily[show_cols], use_container_width=True)

                    st.markdown("#### 일최고/최저 기온")
                    chart_df = df_daily[["temperature_2m_max", "temperature_2m_min"]].rename(
                        columns={"temperature_2m_max":"최고", "temperature_2m_min":"최저"}
                    )
                    st.line_chart(chart_df)

                # ---- 시간별 예보 일부 ----
                hourly = data.get("hourly", {})
                if hourly:
                    df_hour = pd.DataFrame(hourly)
                    if "time" in df_hour.columns:
                        df_hour["time"] = pd.to_datetime(df_hour["time"])
                        df_hour = df_hour.set_index("time")
                    st.markdown("#### 다음 24시간 기온(시간별)")
                    st.line_chart(df_hour["temperature_2m"].iloc[:24])

        except requests.HTTPError as e:
            st.error(f"HTTP 오류: {e}")
        except Exception as e:
            st.error(f"오류 발생: {e}")