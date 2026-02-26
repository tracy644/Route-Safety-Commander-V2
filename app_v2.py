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

def get_int(val):
    if val is None: return 0
    if isinstance(val, dict) and 'value' in val: val = val['value']
    nums = re.findall(r'\d+', str(val))
    return int(nums[0]) if nums else 0

def analyze_hour(row, location_name):
    risk_score = 0
    reasons = []
    
    temp = row.get('temperature', 32)
    short_forecast = row.get('shortForecast', '').lower()
    wind_speed = get_int(row.get('windSpeed', 0))
    wind_gust = get_int(row.get('windGust', 0))
    effective_wind = max(wind_speed, wind_gust)
    
    # 1. SNOW ACCUMULATION (V2 IMPROVEMENT)
    # NWS hourly often doesn't give precise inches in the shortForecast, 
    # but we check for 'heavy' keywords or low temps with precip.
    if "heavy snow" in short_forecast or "blizzard" in short_forecast:
        risk_score += 3
        reasons.append("Heavy Snow/Blizzard")
    elif "snow" in short_forecast:
        risk_score += 2
        reasons.append("Snowfall")

    # 2. VISIBILITY / FOG (V2 IMPROVEMENT)
    if "fog" in short_forecast or "haze" in short_forecast:
        risk_score += 1
        reasons.append("Low Visibility/Fog")
    
    # 3. WIND
    if effective_wind >= 50:
        risk_score += 3
        reasons.append(f"Severe Winds ({effective_wind} mph)")
    elif effective_wind >= 35:
        risk_score += 2
        reasons.append(f"High Winds ({effective_wind} mph)")
        
    # 4. ICY ROADS
    if temp <= 32 and ("rain" in short_forecast or "snow" in short_forecast):
        risk_score = max(risk_score, 2)
        reasons.append("Icy Road Risk")

    status = "🟢"
    if risk_score == 1: status = "🟡"
    if risk_score == 2: status = "🟠"
    if risk_score >= 3: status = "🔴"
    
    return status, risk_score, reasons

# --- UI ---
st.title("🚛 Route Safety Commander V2")
st.markdown("### *Weekly Strategic Planner*")

route_name = st.selectbox("Select Destination", list(ROUTES.keys()))
route_data = ROUTES[route_name]

# WEEKLY SNAPSHOT ENGINE
if st.button("🔄 Scan Entire Week"):
    st.subheader("📅 5-Day Driving Outlook")
    
    days_data = {}
    
    with st.spinner("Analyzing all route segments..."):
        for loc_name, url in route_data["urls"].items():
            periods = fetch_hourly_data(url)
            for p in periods:
                dt = parser.parse(p['startTime'])
                date_str = dt.strftime('%A, %b %d')
                hour = dt.hour
                
                if date_str not in days_data:
                    days_data[date_str] = {"max_risk": 0, "reasons": set()}
                
                # Only check relevant driving hours (7 AM to 7 PM)
                if 7 <= hour <= 19:
                    status, score, reasons = analyze_hour(p, loc_name)
                    if score > days_data[date_str]["max_risk"]:
                        days_data[date_str]["max_risk"] = score
                    if score > 0:
                        for r in reasons: days_data[date_str]["reasons"].add(f"{r} ({loc_name})")

    # Display result in a nice grid
    cols = st.columns(len(days_data.keys()))
    for i, date_key in enumerate(list(days_data.keys())[:5]):
        with cols[i]:
            risk = days_data[date_key]["max_risk"]
            icon = "🟢 GO" if risk == 0 else "🟡 CAUTION" if risk == 1 else "🟠 RISK" if risk == 2 else "🔴 NO GO"
            st.metric(date_key, icon)
            if days_data[date_key]["reasons"]:
                st.caption(", ".join(list(days_data[date_key]["reasons"])[:2]))

st.divider()
st.info(f"**Route Note:** {route_data['note']}")

# Original dropdown for detailed view
# (Keep the rest of your original detailed logic here...)
st.write("*(Use the original 'Plan For' dropdown below for hour-by-hour details)*")
