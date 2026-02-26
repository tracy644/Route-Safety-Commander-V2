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
            "State Line": "47.690,-117.040",      # I-90 Entry to WA
            "Sunset Hill": "47.650,-117.450",     # Steep grade leaving Spokane
            "West Plains (DAA)": "47.630,-117.570" # Airway Heights Auction Area
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
    },
    "Lewiston, ID (US-95 South)": {
        "direction": "South",
        "note": "⚠️ Steep Grade: 2,000ft drop into Lewiston. Watch for rain/snow transition.",
        "outbound_hours": [8, 9, 10, 11, 12],
        "return_hours": [13, 14, 15, 16, 17],
        "stops_out": ["Mica Grade", "Harvard Hill", "Lewiston Grade"],
        "stops_ret": ["Lewiston Grade", "Harvard Hill", "Mica Grade"],
        "coords": {
            "Mica Grade": "47.591,-116.835",
            "Harvard Hill": "46.950,-116.660",
            "Lewiston Grade": "46.460,-116.980"
        },
        "urls": {
            "Mica Grade": "https://api.weather.gov/gridpoints/OTX/161,97/forecast/hourly",
            "Harvard Hill": "https://api.weather.gov/gridpoints/OTX/168,68/forecast/hourly",
            "Lewiston Grade": "https://api.weather.gov/gridpoints/OTX/162,38/forecast/hourly"
        }
    },
    "Colville, WA (US-395 North)": {
        "direction": "North",
        "note": "⚠️ Snow Belt: Chewelah area often holds snow when Spokane is raining.",
        "outbound_hours": [8, 9, 10, 11],
        "return_hours": [12, 13, 14, 15],
        "stops_out": ["Deer Park", "Chewelah", "Colville"],
        "stops_ret": ["Colville", "Chewelah", "Deer Park"],
        "coords": {
            "Deer Park": "47.950,-117.470", 
            "Chewelah": "48.270,-117.710",   
            "Colville": "48.540,-117.900"    
        },
        "urls": {
            "Deer Park": "https://api.weather.gov/gridpoints/OTX/136,110/forecast/hourly",
            "Chewelah": "https://api.weather.gov/gridpoints/OTX/130,123/forecast/hourly",
            "Colville": "https://api.weather.gov/gridpoints/OTX/124,133/forecast/hourly"
        }
    }
}

# --- LOGIC ENGINE ---
@st.cache_data(ttl=900) 
def fetch_hourly_data(url):
    try:
        headers = {'User-Agent': '(vandal-route-planner, contact@example.com)'}
        if "points" in url and "gridpoints" not in url:
            r_meta = requests.get(url, headers=headers, timeout=5)
            r_meta.raise_for_status()
            url = r_meta.json()['properties']['forecastHourly']
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

def calculate_wind_chill(temp_f, speed_mph):
    if temp_f is None or speed_mph is None: return temp_f
    if temp_f > 50 or speed_mph < 3: return temp_f
    return 35.74 + (0.6215 * temp_f) - (35.75 * math.pow(speed_mph, 0.16)) + (0.4275 * temp_f * math.pow(speed_mph, 0.16))

def analyze_hour(row, location_name, trip_direction="Out", overall_direction="East"):
    risk_score = 0
    alerts = []
    major_reasons = []
    
    temp = row.get('temperature', 32)
    short_forecast = row.get('shortForecast', '').lower()
    is_daytime = row.get('isDaytime', True)
    
    sustained = get_int(row.get('windSpeed', 0))
    gust = get_int(row.get('windGust', 0))
    effective_wind = max(sustained, gust)
    pop = get_int(row.get('probabilityOfPrecipitation', 0))
    
    # 1. Road Surface
    if "heavy snow" in short_forecast:
        risk_score += 3
        alerts.append("❄️ HEAVY SNOW")
        major_reasons.append("Heavy Snow")
    elif "snow" in short_forecast or "ice" in short_forecast:
        if temp <= 32:
            risk_score += 2
            alerts.append("❄️ Icy Roads")
            major_reasons.append("Icy Roads")
        else:
            risk_score += 1
            alerts.append("💧 Slush")
            major_reasons.append("Slush")
    elif "rain" in short_forecast:
        if temp <= 32:
            risk_score += 3
            alerts.append("🧊 FREEZING RAIN")
            major_reasons.append("FREEZING RAIN")
        elif temp <= 37:
            risk_score += 1
            alerts.append("🧊 Possible Black Ice")
            major_reasons.append("Black Ice Risk")
            
    # 2. Wind
    if effective_wind >= 50:
        risk_score += 3 
        alerts.append(f"💨 STORM GUSTS {effective_wind} MPH")
        major_reasons.append(f"Severe Winds ({effective_wind} mph)")
    elif effective_wind >= 40:
        risk_score += 2
        alerts.append(f"💨 GUSTS {effective_wind} MPH")
        major_reasons.append(f"High Winds ({effective_wind} mph)")
    elif effective_wind >= 30:
        risk_score += 1
        alerts.append(f"💨 Windy ({effective_wind})")
        major_reasons.append("Windy conditions")

    # 3. Visibility (V2 addition)
    if "fog" in short_forecast or "haze" in short_forecast:
        risk_score = max(risk_score, 1)
        alerts.append("🌫️ Low Visibility")
        major_reasons.append("Fog/Haze")

    # 4. Sun Glare
    try:
        hour_int = parser.parse(row['startTime']).hour
        if "sunny" in short_forecast or "clear" in short_forecast:
            if overall_direction in ["East", "West"]:
                if trip_direction == "Out" and 7 <= hour_int <= 10: alerts.append("😎 Sun Glare")
                if trip_direction == "Ret" and 15 <= hour_int <= 18: alerts.append("😎 Sun Glare")
    except: pass 

    status = "🟢"
    if risk_score == 1: status = "🟡"
    if risk_score == 2: status = "🟠"
    if risk_score >= 3: status = "🔴"
    
    return status, ", ".join(alerts), risk_score, effective_wind, pop, is_daytime, major_reasons

# --- UI START ---
st.title("🚛 Route Safety Commander V2")

# 1. SELECT ROUTE
route_name = st.selectbox("Select Destination", list(ROUTES.keys()))
route_data = ROUTES[route_name]

# --- V2 FEATURE: WEEKLY SCANNER ---
if st.button("🔄 Scan Entire Week (Strategy Mode)"):
    st.subheader("📅 5-Day Strategic Outlook")
    days_summary = {}
    with st.spinner("Analyzing weekly patterns..."):
        for loc_name, url in route_data["urls"].items():
            raw_data = fetch_hourly_data(url)
            for p in raw_data:
                dt = parser.parse(p['startTime'])
                date_str = dt.strftime('%A, %b %d')
                if date_str not in days_summary: days_summary[date_str] = {"risk": 0, "reasons": set()}
                if 7 <= dt.hour <= 19:
                    _, _, score, _, _, _, reasons = analyze_hour(p, loc_name, "Out", route_data.get("direction"))
                    if score > days_summary[date_str]["risk"]: days_summary[date_str]["risk"] = score
                    for r in reasons: days_summary[date_str]["reasons"].add(f"{r} ({loc_name})")
    
    cols = st.columns(min(5, len(days_summary)))
    for i, date_key in enumerate(list(days_summary.keys())[:5]):
        with cols[i]:
            r = days_summary[date_key]["risk"]
            label = "GO" if r == 0 else "CAUTION" if r == 1 else "RISK" if r == 2 else "NO GO"
            st.metric(date_key, label)
            if days_summary[date_key]["reasons"]:
                st.caption(", ".join(list(days_summary[date_key]["reasons"])[:2]))

st.divider()

# --- ORIGINAL FEATURE: DAILY DEEP-DIVE ---
st.markdown("### *Tactical Daily Deep-Dive*")

# Connection & Date Setup
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
    
    selected_date_str = st.selectbox("📅 Plan for (Hour-by-Hour):", unique_dates[:5])
    st.info(route_data["note"])

    # Processing Logic for Tables
    processed_data_out = {}
    processed_data_ret = {}
    official_alerts_found = []

    for name, url in route_data["urls"].items():
        # Check for Official NWS Alerts
        lat_lon = route_data["coords"].get(name)
        if lat_lon:
            active_alerts = fetch_active_alerts(lat_lon)
            for alert in active_alerts: official_alerts_found.append(f"**{name}:** {alert}")

        # Fetch Hourly pass data
        raw = fetch_hourly_data(url)
        day_rows_out = []
        day_rows_ret = []
        for hour in raw:
            dt = parser.parse(hour['startTime'])
            if dt.strftime('%A, %b %d') == selected_date_str:
                stat, alerts_text, score, wind, pop, daytime, _ = analyze_hour(hour, name, "Out", route_data.get("direction"))
                time_disp = dt.strftime('%I %p')
                time_disp = f"☀️ {time_disp}" if daytime else f"🌑 {time_disp}"
                
                row_data = {
                    "Hour": dt.hour, "Time": time_disp,
                    "Temp": f"{hour.get('temperature')}°",
                    "Precip %": f"{pop}%" if pop > 0 else "-",
                    "Wind": f"{wind} {hour.get('windDirection')}",
                    "Weather": add_weather_icon(hour.get('shortForecast')),
                    "Status": stat, "Alerts": alerts_text
                }
                if dt.hour in route_data["outbound_hours"]: day_rows_out.append(row_data)
                if dt.hour in route_data["return_hours"]: day_rows_ret.append(row_data)
        
        processed_data_out[name] = pd.DataFrame(day_rows_out)
        processed_data_ret[name] = pd.DataFrame(day_rows_ret)

    # TABS FOR TABLES
    tab_out, tab_ret, tab_alerts, tab_full = st.tabs(["🚀 Outbound", "↩️ Return", "🚨 Alerts", "📋 Details"])
    
    def render_trip_table(data_map, location_order):
        for name in location_order:
            if name in data_map and not data_map[name].empty:
                with st.expander(f"📍 {name}", expanded=True):
                    st.dataframe(data_map[name][['Time', 'Temp', 'Precip %', 'Wind', 'Weather', 'Status', 'Alerts']], hide_index=True, use_container_width=True)

    with tab_out:
        st.subheader(f"Outbound Trip: {selected_date_str}")
        render_trip_table(processed_data_out, route_data["stops_out"])

    with tab_ret:
        st.subheader(f"Return Trip: {selected_date_str}")
        render_trip_table(processed_data_ret, route_data["stops_ret"])

    with tab_alerts:
        st.subheader("Official NWS Warnings")
        if official_alerts_found:
            for a in set(official_alerts_found): st.error(a)
        else: st.success("No active NWS warnings.")

    with tab_full:
        st.write("Full 24-hour breakdown for a specific location.")
        loc_select = st.selectbox("Select Location", list(route_data["urls"].keys()))
        # Simple re-fetch for the full 24h of that day
        raw_full = fetch_hourly_data(route_data["urls"][loc_select])
        full_rows = []
        for hour in raw_full:
            dt = parser.parse(hour['startTime'])
            if dt.strftime('%A, %b %d') == selected_date_str:
                stat, alerts_text, _, wind, pop, daytime, _ = analyze_hour(hour, loc_select)
                full_rows.append({
                    "Time": dt.strftime('%I %p'), "Temp": f"{hour.get('temperature')}°",
                    "Precip %": f"{pop}%", "Wind": f"{wind}", 
                    "Weather": hour.get('shortForecast'), "Status": stat
                })
        st.dataframe(pd.DataFrame(full_rows), hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown("**Essential Links:** [Idaho 511](https://511.idaho.gov/) | [MDT Maps](https://www.mdt.mt.gov/travinfo/) | [WSDOT](https://wsdot.com/Travel/Real-time/Map/)")
