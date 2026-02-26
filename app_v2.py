import streamlit as st
import requests
import pandas as pd
from dateutil import parser
from datetime import datetime, timedelta
import math
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Route Safety Commander V2", page_icon="🚛", layout="wide")

# --- ROUTE DATABASE ---
ROUTES = {
    "Helena, MT (I-90 East)": {
        "direction": "East",
        "note": "⚠️ Mountain Passes: McDonald Pass gusts often exceed 60 mph.",
        "outbound_hours": [7, 8, 9, 10, 11, 12],
        "return_hours": [12, 13, 14, 15, 16, 17, 18, 19],
        "stops_out": ["4th of July Pass", "Lookout Pass", "Missoula Valley", "McDonald Pass"],
        "stops_ret": ["McDonald Pass", "Missoula Valley", "Lookout Pass", "4th of July Pass"],
        "coords": {
            "4th of July Pass": "47.548,-116.503",
            "Lookout Pass": "47.456,-115.696",
            "Missoula Valley": "46.916,-114.090",
            "McDonald Pass": "46.586,-112.311"
        },
        "urls": {
            "4th of July Pass": "https://api.weather.gov/gridpoints/OTX/168,102/forecast/hourly",
            "Lookout Pass": "https://api.weather.gov/gridpoints/MSO/56,102/forecast/hourly",
            "Missoula Valley": "https://api.weather.gov/gridpoints/MSO/86,76/forecast/hourly",
            "McDonald Pass": "https://api.weather.gov/gridpoints/TFX/62,50/forecast/hourly"
        }
    },
    "DAA Auction (Airway Heights, WA)": {
        "direction": "West",
        "note": "⚠️ West Plains Hazard: High wind and drifting snow common after Sunset Hill.",
        "outbound_hours": [8, 9, 10, 11],
        "return_hours": [12, 13, 14, 15],
        "stops_out": ["State Line", "Sunset Hill", "West Plains (DAA)"],
        "stops_ret": ["West Plains (DAA)", "Sunset Hill", "State Line"],
        "coords": {
            "State Line": "47.690,-117.040",
            "Sunset Hill": "47.650,-117.450",
            "West Plains (DAA)": "47.630,-117.570"
        },
        "urls": {
            "State Line": "https://api.weather.gov/gridpoints/OTX/151,102/forecast/hourly",
            "Sunset Hill": "https://api.weather.gov/gridpoints/OTX/136,101/forecast/hourly",
            "West Plains (DAA)": "https://api.weather.gov/gridpoints/OTX/132,100/forecast/hourly"
        }
    },
    "Whitefish, MT (via St. Regis)": {
        "direction": "North",
        "note": "⚠️ Rural Route: Limited cell service in St. Regis Canyon.",
        "outbound_hours": [7, 8, 9, 10, 11],
        "return_hours": [13, 14, 15, 16, 17],
        "stops_out": ["4th of July Pass", "Lookout Pass", "St. Regis Canyon", "Polson Hill", "Whitefish"],
        "stops_ret": ["Whitefish", "Polson Hill", "St. Regis Canyon", "Lookout Pass", "4th of July Pass"],
        "coords": {
            "4th of July Pass": "47.548,-116.503",
            "Lookout Pass": "47.456,-115.696",
            "St. Regis Canyon": "47.300,-115.100", 
            "Polson Hill": "47.693,-114.163",     
            "Whitefish": "48.411,-114.341"
        },
        "urls": {
            "4th of July Pass": "https://api.weather.gov/gridpoints/OTX/168,102/forecast/hourly",
            "Lookout Pass": "https://api.weather.gov/gridpoints/MSO/56,102/forecast/hourly",
            "St. Regis Canyon": "https://api.weather.gov/gridpoints/MSO/46,95/forecast/hourly",
            "Polson Hill": "https://api.weather.gov/gridpoints/MSO/77,118/forecast/hourly",
            "Whitefish": "https://api.weather.gov/gridpoints/MSO/73,139/forecast/hourly"
        }
    },
    "Pullman, WA (US-95 South)": {
        "direction": "South",
        "note": "⚠️ Wind Hazard: High risk of drifting snow on the Palouse (Moscow to Pullman).",
        "outbound_hours": [9, 10, 11, 12],
        "return_hours": [12, 13, 14],
        "stops_out": ["Mica Grade", "Harvard Hill", "Moscow/Pullman"],
        "stops_ret": ["Moscow/Pullman", "Harvard Hill", "Mica Grade"],
        "coords": {
            "Mica Grade": "47.591,-116.835",     
            "Harvard Hill": "46.950,-116.660",   
            "Moscow/Pullman": "46.732,-117.000"  
        },
        "urls": {
            "Mica Grade": "https://api.weather.gov/gridpoints/OTX/161,97/forecast/hourly",
            "Harvard Hill": "https://api.weather.gov/gridpoints/OTX/168,68/forecast/hourly",
            "Moscow/Pullman": "https://api.weather.gov/gridpoints/OTX/158,55/forecast/hourly"
        }
    }
}

# --- LOGIC ENGINE ---
@st.cache_data(ttl=900) 
def fetch_hourly_data(url):
    try:
        headers = {'User-Agent': '(vandal-route-planner, contact@example.com)'}
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        return r.json().get('properties', {}).get('periods', [])
    except:
        return []

@st.cache_data(ttl=300)
def fetch_active_alerts(lat_lon_str):
    url = f"https://api.weather.gov/alerts/active?point={lat_lon_str}"
    try:
        headers = {'User-Agent': '(vandal-route-planner, contact@example.com)'}
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        alerts = []
        for f in data.get('features', []):
            event = f.get('properties', {}).get('event', '')
            if any(x in event for x in ["Winter", "Wind", "Ice", "Blizzard", "Snow", "Flood"]):
                alerts.append(event.upper())
        return list(set(alerts))
    except:
        return []

def get_int(val):
    if val is None: return 0
    if isinstance(val, dict) and 'value' in val: val = val['value']
    nums = re.findall(r'\d+', str(val))
    return int(nums[0]) if nums else 0

def add_weather_icon(forecast_text):
    if not forecast_text: return ""
    text = forecast_text.lower()
    icon = ""
    if "snow" in text: icon = "🌨️"
    elif "rain" in text: icon = "🌧️"
    elif "shower" in text: icon = "🌦️"
    elif "cloud" in text: icon = "☁️"
    elif "clear" in text or "sunny" in text: icon = "☀️"
    elif "fog" in text: icon = "🌫️"
    elif "wind" in text: icon = "💨"
    return f"{icon} {forecast_text}"

def analyze_hour(row, location_name):
    risk_score = 0
    reasons = []
    
    temp = row.get('temperature', 32)
    short_forecast = row.get('shortForecast', '').lower()
    wind_speed = get_int(row.get('windSpeed', 0))
    wind_gust = get_int(row.get('windGust', 0))
    effective_wind = max(wind_speed, wind_gust)
    pop = get_int(row.get('probabilityOfPrecipitation', 0))
    
    # 1. Snow
    if "heavy snow" in short_forecast or "blizzard" in short_forecast:
        risk_score += 3
        reasons.append("❄️ HEAVY SNOW")
    elif "snow" in short_forecast:
        risk_score += 2
        reasons.append("❄️ Snowfall")

    # 2. Visibility
    if "fog" in short_forecast or "haze" in short_forecast:
        risk_score += 1
        reasons.append("🌫️ Low Visibility")
    
    # 3. Wind
    if effective_wind >= 50:
        risk_score += 3
        reasons.append(f"💨 STORM GUSTS {effective_wind} MPH")
    elif effective_wind >= 35:
        risk_score += 2
        reasons.append(f"💨 High Winds {effective_wind} MPH")
        
    # 4. Icy Roads
    if temp <= 32 and ("rain" in short_forecast or "snow" in short_forecast):
        risk_score = max(risk_score, 2)
        reasons.append("🧊 Icy Roads")
    elif temp <= 37 and "rain" in short_forecast:
        risk_score = max(risk_score, 1)
        reasons.append("🧊 Black Ice Risk")

    status = "🟢"
    if risk_score == 1: status = "🟡"
    if risk_score == 2: status = "🟠"
    if risk_score >= 3: status = "🔴"
    
    return status, risk_score, reasons, effective_wind, pop

# --- UI START ---
st.title("🚛 Route Safety Commander V2")
st.markdown("### *Strategic Weekly Outlook*")

# 1. SELECT ROUTE
route_name = st.selectbox("Select Destination", list(ROUTES.keys()))
route_data = ROUTES[route_name]

# --- SECTION A: STRATEGIC PLANNER ---
if st.button("🔄 Scan Entire Week (Compare Days)"):
    st.subheader("📅 5-Day Driving Forecast Comparison")
    days_data = {}
    with st.spinner("Analyzing all route segments..."):
        for loc_name, url in route_data["urls"].items():
            periods = fetch_hourly_data(url)
            for p in periods:
                dt = parser.parse(p['startTime'])
                date_str = dt.strftime('%A, %b %d')
                if date_str not in days_data:
                    days_data[date_str] = {"max_risk": 0, "reasons": set()}
                if 7 <= dt.hour <= 19:
                    _, score, reasons, _, _ = analyze_hour(p, loc_name)
                    if score > days_data[date_str]["max_risk"]:
                        days_data[date_str]["max_risk"] = score
                    if score > 0:
                        for r in reasons: days_data[date_str]["reasons"].add(f"{r} ({loc_name})")

    cols = st.columns(min(5, len(days_data)))
    for i, date_key in enumerate(list(days_data.keys())[:5]):
        with cols[i]:
            risk = days_data[date_key]["max_risk"]
            color = "green" if risk == 0 else "orange" if risk == 1 else "red"
            st.metric(date_key, "GO" if risk == 0 else "CAUTION" if risk == 1 else "HIGH RISK")
            if days_data[date_key]["reasons"]:
                st.caption(", ".join(list(days_data[date_key]["reasons"])[:2]))

st.divider()

# --- SECTION B: TACTICAL DETAILS ---
st.markdown("### *Tactical Daily Deep-Dive*")
ref_url = list(route_data["urls"].values())[0]
ref_data = fetch_hourly_data(ref_url)

if ref_data:
    unique_dates = []
    seen_dates = set()
    for p in ref_data:
        dt = parser.parse(p['startTime'])
        date_str = dt.strftime('%A, %b %d')
        if date_str not in seen_dates:
            seen_dates.add(date_str)
            unique_dates.append(date_str)
    
    selected_date_str = st.selectbox("📅 Pick a day for full details:", unique_dates[:5])
    st.info(route_data["note"])

    # Processing for selected day
    processed_data_out = {}
    processed_data_ret = {}
    official_alerts_found = []

    for name, url in route_data["urls"].items():
        # Alerts
        lat_lon = route_data["coords"].get(name)
        if lat_lon:
            active_alerts = fetch_active_alerts(lat_lon)
            for alert in active_alerts: official_alerts_found.append(f"**{name}:** {alert}")

        # Hourly Details
        raw = fetch_hourly_data(url)
        day_rows_out = []
        day_rows_ret = []
        for hour in raw:
            dt = parser.parse(hour['startTime'])
            if dt.strftime('%A, %b %d') == selected_date_str:
                stat, score, reasons, wind, pop = analyze_hour(hour, name)
                time_display = dt.strftime('%I %p')
                time_display = f"☀️ {time_display}" if hour.get('isDaytime') else f"🌑 {time_display}"
                
                row_data = {
                    "Hour": dt.hour, "Time": time_display,
                    "Temp": f"{hour.get('temperature')}°",
                    "Precip %": f"{pop}%" if pop > 0 else "-",
                    "Wind": f"{wind} {hour.get('windDirection')}",
                    "Weather": add_weather_icon(hour.get('shortForecast')),
                    "Status": stat, "Alerts": ", ".join(reasons)
                }
                if dt.hour in route_data["outbound_hours"]: day_rows_out.append(row_data)
                if dt.hour in route_data["return_hours"]: day_rows_ret.append(row_data)
        
        processed_data_out[name] = pd.DataFrame(day_rows_out)
        processed_data_ret[name] = pd.DataFrame(day_rows_ret)

    # TABS
    tab_out, tab_ret, tab_alerts = st.tabs(["🚀 Outbound Details", "↩️ Return Details", "🚨 Official Alerts"])
    
    def render_tables(data_map, locations):
        for name in locations:
            if name in data_map and not data_map[name].empty:
                with st.expander(f"📍 {name}", expanded=True):
                    st.dataframe(data_map[name][['Time', 'Temp', 'Precip %', 'Wind', 'Weather', 'Status', 'Alerts']], hide_index=True, use_container_width=True)

    with tab_out: render_tables(processed_data_out, route_data["stops_out"])
    with tab_ret: render_tables(processed_data_ret, route_data["stops_ret"])
    with tab_alerts:
        if official_alerts_found:
            for a in set(official_alerts_found): st.error(a)
        else: st.success("No active NWS warnings for this day.")

st.markdown("---")
st.markdown("**Essential Links:** [Idaho 511](https://511.idaho.gov/) | [MDT Maps](https://www.mdt.mt.gov/travinfo/) | [WSDOT](https://wsdot.com/Travel/Real-time/Map/)")
