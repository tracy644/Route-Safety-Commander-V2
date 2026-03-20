import re
from dateutil import parser

import pandas as pd
import requests
import streamlit as st


# --- CONFIGURATION ---
st.set_page_config(page_title="Route Safety Commander V2", page_icon="🚛", layout="wide")

if "selected_day" not in st.session_state:
    st.session_state.selected_day = None


# --- ROUTE DATABASE ---
ROUTES = {
    "Helena, MT (I-90 East)": {
        "direction": "East",
        "note": "⚠️ Mountain route with major exposure zones. Final rating uses both outbound and return windows, and the worse direction wins.",
        "mode": "windowed",
        "stops_out": [
            "4th of July Pass",
            "Lookout Pass",
            "Missoula Flats",
            "McDonald Pass",
        ],
        "stops_ret": [
            "McDonald Pass",
            "Missoula Flats",
            "Lookout Pass",
            "4th of July Pass",
        ],
        "coords": {
            "4th of July Pass": "47.548,-116.503",
            "Lookout Pass": "47.456,-115.696",
            "Missoula Flats": "46.800,-113.500",
            "McDonald Pass": "46.586,-112.311",
        },
        "urls": {
            "4th of July Pass": "https://api.weather.gov/gridpoints/OTX/168,102/forecast/hourly",
            "Lookout Pass": "https://api.weather.gov/gridpoints/MSO/56,102/forecast/hourly",
            "McDonald Pass": "https://api.weather.gov/gridpoints/TFX/62,50/forecast/hourly",
        },
        # This segment covers the whole exposed corridor, not just one point.
        "segment_sources": {
            "Missoula Flats": [
                "https://api.weather.gov/gridpoints/MSO/46,95/forecast/hourly",   # Superior / St. Regis side
                "https://api.weather.gov/gridpoints/MSO/70,85/forecast/hourly",   # central corridor
                "https://api.weather.gov/gridpoints/MSO/86,76/forecast/hourly",   # Drummond / Garrison side
            ]
        },
        # Hours are local to each location's forecast timezone.
        "windows_out": {
            "4th of July Pass": (7, 8),
            "Lookout Pass": (8, 9),
            "Missoula Flats": (10, 12),
            "McDonald Pass": (11, 12),
        },
        "windows_ret": {
            "McDonald Pass": (12, 13),
            "Missoula Flats": (13, 15),
            "Lookout Pass": (14, 15),
            "4th of July Pass": (15, 16),
        },
    },
    "DAA Auction (Airway Heights, WA)": {
        "direction": "West",
        "note": "⚠️ West Plains Hazard: High wind and drifting snow common after Sunset Hill.",
        "mode": "hourly",
        "outbound_hours": [8, 9, 10, 11],
        "return_hours": [12, 13, 14, 15],
        "stops_out": ["State Line", "Sunset Hill", "West Plains (DAA)"],
        "stops_ret": ["West Plains (DAA)", "Sunset Hill", "State Line"],
        "coords": {
            "State Line": "47.690,-117.040",
            "Sunset Hill": "47.650,-117.450",
            "West Plains (DAA)": "47.630,-117.570",
        },
        "urls": {
            "State Line": "https://api.weather.gov/gridpoints/OTX/151,102/forecast/hourly",
            "Sunset Hill": "https://api.weather.gov/gridpoints/OTX/136,101/forecast/hourly",
            "West Plains (DAA)": "https://api.weather.gov/gridpoints/OTX/132,100/forecast/hourly",
        },
    },
    "Whitefish, MT (via St. Regis)": {
        "direction": "North",
        "note": "⚠️ Rural Route: Limited cell service in St. Regis Canyon.",
        "mode": "hourly",
        "outbound_hours": [7, 8, 9, 10, 11],
        "return_hours": [13, 14, 15, 16, 17],
        "stops_out": [
            "4th of July Pass",
            "Lookout Pass",
            "St. Regis Canyon",
            "Polson Hill",
            "Whitefish",
        ],
        "stops_ret": [
            "Whitefish",
            "Polson Hill",
            "St. Regis Canyon",
            "Lookout Pass",
            "4th of July Pass",
        ],
        "coords": {
            "4th of July Pass": "47.548,-116.503",
            "Lookout Pass": "47.456,-115.696",
            "St. Regis Canyon": "47.300,-115.100",
            "Polson Hill": "47.693,-114.163",
            "Whitefish": "48.411,-114.341",
        },
        "urls": {
            "4th of July Pass": "https://api.weather.gov/gridpoints/OTX/168,102/forecast/hourly",
            "Lookout Pass": "https://api.weather.gov/gridpoints/MSO/56,102/forecast/hourly",
            "St. Regis Canyon": "https://api.weather.gov/gridpoints/MSO/46,95/forecast/hourly",
            "Polson Hill": "https://api.weather.gov/gridpoints/MSO/77,118/forecast/hourly",
            "Whitefish": "https://api.weather.gov/gridpoints/MSO/73,139/forecast/hourly",
        },
    },
    "Pullman, WA (US-95 South)": {
        "direction": "South",
        "note": "⚠️ Wind Hazard: High risk of drifting snow on the Palouse (Moscow to Pullman).",
        "mode": "hourly",
        "outbound_hours": [9, 10, 11, 12],
        "return_hours": [12, 13, 14],
        "stops_out": ["Mica Grade", "Harvard Hill", "Moscow/Pullman"],
        "stops_ret": ["Moscow/Pullman", "Harvard Hill", "Mica Grade"],
        "coords": {
            "Mica Grade": "47.591,-116.835",
            "Harvard Hill": "46.950,-116.660",
            "Moscow/Pullman": "46.732,-117.000",
        },
        "urls": {
            "Mica Grade": "https://api.weather.gov/gridpoints/OTX/161,97/forecast/hourly",
            "Harvard Hill": "https://api.weather.gov/gridpoints/OTX/168,68/forecast/hourly",
            "Moscow/Pullman": "https://api.weather.gov/gridpoints/OTX/158,55/forecast/hourly",
        },
    },
    "Lewiston, ID (US-95 South)": {
        "direction": "South",
        "note": "⚠️ Steep Grade: 2,000ft drop into Lewiston. Watch for rain/snow transition.",
        "mode": "hourly",
        "outbound_hours": [8, 9, 10, 11, 12],
        "return_hours": [13, 14, 15, 16, 17],
        "stops_out": ["Mica Grade", "Harvard Hill", "Lewiston Grade"],
        "stops_ret": ["Lewiston Grade", "Harvard Hill", "Mica Grade"],
        "coords": {
            "Mica Grade": "47.591,-116.835",
            "Harvard Hill": "46.950,-116.660",
            "Lewiston Grade": "46.460,-116.980",
        },
        "urls": {
            "Mica Grade": "https://api.weather.gov/gridpoints/OTX/161,97/forecast/hourly",
            "Harvard Hill": "https://api.weather.gov/gridpoints/OTX/168,68/forecast/hourly",
            "Lewiston Grade": "https://api.weather.gov/gridpoints/OTX/162,38/forecast/hourly",
        },
    },
    "Colville, WA (US-395 North)": {
        "direction": "North",
        "note": "⚠️ Snow Belt: Chewelah area often holds snow when Spokane is raining.",
        "mode": "hourly",
        "outbound_hours": [8, 9, 10, 11],
        "return_hours": [12, 13, 14, 15],
        "stops_out": ["Deer Park", "Chewelah", "Colville"],
        "stops_ret": ["Colville", "Chewelah", "Deer Park"],
        "coords": {
            "Deer Park": "47.950,-117.470",
            "Chewelah": "48.270,-117.710",
            "Colville": "48.540,-117.900",
        },
        "urls": {
            "Deer Park": "https://api.weather.gov/gridpoints/OTX/136,110/forecast/hourly",
            "Chewelah": "https://api.weather.gov/gridpoints/OTX/130,123/forecast/hourly",
            "Colville": "https://api.weather.gov/gridpoints/OTX/124,133/forecast/hourly",
        },
    },
}


# --- DATA HELPERS ---
@st.cache_data(ttl=900)
def fetch_hourly_data(url: str):
    try:
        headers = {"User-Agent": "(vandal-route-planner, contact@example.com)"}

        if "points" in url and "gridpoints" not in url:
            r_meta = requests.get(url, headers=headers, timeout=5)
            r_meta.raise_for_status()
            url = r_meta.json()["properties"]["forecastHourly"]

        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        return r.json().get("properties", {}).get("periods", [])
    except Exception:
        return []


@st.cache_data(ttl=300)
def fetch_active_alerts(lat_lon_str: str):
    url = f"https://api.weather.gov/alerts/active?point={lat_lon_str}"
    try:
        headers = {"User-Agent": "(vandal-route-planner, contact@example.com)"}
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        alerts = []

        for feature in data.get("features", []):
            event = feature.get("properties", {}).get("event", "")
            if any(x in event for x in ["Winter", "Wind", "Ice", "Blizzard", "Snow", "Flood"]):
                alerts.append(event.upper())

        return list(set(alerts))
    except Exception:
        return []


def get_int(val):
    if val is None:
        return 0
    if isinstance(val, dict) and "value" in val:
        val = val["value"]
    nums = re.findall(r"\d+", str(val))
    return int(nums[0]) if nums else 0


def add_weather_icon(forecast_text: str):
    if not forecast_text:
        return ""

    text = forecast_text.lower()
    icon = ""

    if "snow" in text:
        icon = "🌨️"
    elif "rain" in text:
        icon = "🌧️"
    elif "shower" in text:
        icon = "🌦️"
    elif "cloud" in text:
        icon = "☁️"
    elif "clear" in text or "sunny" in text:
        icon = "☀️"
    elif "fog" in text:
        icon = "🌫️"
    elif "wind" in text:
        icon = "💨"

    return f"{icon} {forecast_text}"


def risk_label(risk_score: int):
    if risk_score == 0:
        return "GO"
    if risk_score == 1:
        return "CAUTION"
    if risk_score == 2:
        return "RISK"
    return "NO GO"


def get_label_block(risk_score: int):
    if risk_score == 0:
        return "🟢 GO"
    if risk_score == 1:
        return "🟡 CAUTION"
    if risk_score == 2:
        return "🟠 RISK"
    return "🔴 NO GO"


def analyze_hour(row, location_name, trip_direction="Out", overall_direction="East"):
    risk_score = 0
    alerts = []
    major_reasons = []

    temp = row.get("temperature", 32)
    short_forecast = row.get("shortForecast", "").lower()
    is_daytime = row.get("isDaytime", True)

    sustained = get_int(row.get("windSpeed", 0))
    gust = get_int(row.get("windGust", 0))
    effective_wind = max(sustained, gust)
    pop = get_int(row.get("probabilityOfPrecipitation", 0))

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
            major_reasons.append("Freezing Rain")
        elif temp <= 37:
            risk_score += 1
            alerts.append("🧊 Possible Black Ice")
            major_reasons.append("Black Ice Risk")

    if location_name == "McDonald Pass":
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
            major_reasons.append("Windy Conditions")
    elif location_name == "Missoula Flats":
        if effective_wind >= 45:
            risk_score += 3
            alerts.append(f"💨 OPEN-AREA GUSTS {effective_wind} MPH")
            major_reasons.append(f"Exposed Winds ({effective_wind} mph)")
        elif effective_wind >= 35:
            risk_score += 2
            alerts.append(f"💨 GUSTS {effective_wind} MPH")
            major_reasons.append(f"Strong Exposure Winds ({effective_wind} mph)")
        elif effective_wind >= 25:
            risk_score += 1
            alerts.append(f"💨 Breezy Exposure ({effective_wind})")
            major_reasons.append("Exposure Winds")
    else:
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
            major_reasons.append("Windy Conditions")

    if "fog" in short_forecast or "haze" in short_forecast:
        risk_score = max(risk_score, 1)
        alerts.append("🌫️ Low Visibility")
        major_reasons.append("Fog/Haze")

    try:
        hour_int = parser.parse(row["startTime"]).hour
        if "sunny" in short_forecast or "clear" in short_forecast:
            if overall_direction in ["East", "West"]:
                if trip_direction == "Out" and 7 <= hour_int <= 10:
                    alerts.append("😎 Sun Glare")
                if trip_direction == "Ret" and 15 <= hour_int <= 18:
                    alerts.append("😎 Sun Glare")
    except Exception:
        pass

    status = "🟢"
    if risk_score == 1:
        status = "🟡"
    elif risk_score == 2:
        status = "🟠"
    elif risk_score >= 3:
        status = "🔴"

    return status, risk_score, alerts, effective_wind, pop, is_daytime, major_reasons


def reason_text_from_reasons(reasons):
    if not reasons:
        return "General adverse conditions in the selected time window."
    return ", ".join(reasons[:2])


def build_hour_row(hour, status, alerts_list, wind, pop, daytime):
    dt = parser.parse(hour["startTime"])
    time_disp = dt.strftime("%I %p")
    time_disp = f"☀️ {time_disp}" if daytime else f"🌑 {time_disp}"

    return {
        "Hour": dt.hour,
        "Time": time_disp,
        "Status": status,
        "Temp": f"{hour.get('temperature')}°",
        "Precip %": f"{pop}%" if pop > 0 else "-",
        "Wind": f"{wind} {hour.get('windDirection')}",
        "Weather": add_weather_icon(hour.get("shortForecast")),
        "Alerts": ", ".join(alerts_list),
    }


def render_trip_table(data_map, location_order):
    for name in location_order:
        if name in data_map and not data_map[name].empty:
            with st.expander(f"📍 {name}", expanded=True):
                df = data_map[name][["Time", "Status", "Temp", "Precip %", "Wind", "Weather", "Alerts"]].copy()
                st.dataframe(df, hide_index=True, use_container_width=True)


def summarize_day_hourly(route_data, selected_date_str):
    days_summary = {selected_date_str: {"risk": 0, "reasons": set(), "worst_pass": None}}

    for loc_name, url in route_data["urls"].items():
        raw_data = fetch_hourly_data(url)

        for period in raw_data:
            dt = parser.parse(period["startTime"])
            date_str = dt.strftime("%A, %b %d")
            if date_str != selected_date_str:
                continue

            if 7 <= dt.hour <= 19:
                _, score, _, _, _, _, reasons = analyze_hour(
                    period, loc_name, "Out", route_data.get("direction")
                )

                if score > days_summary[date_str]["risk"]:
                    days_summary[date_str]["risk"] = score
                    days_summary[date_str]["worst_pass"] = loc_name

                for reason in reasons:
                    days_summary[date_str]["reasons"].add(f"{reason} ({loc_name})")

    return days_summary[selected_date_str]


def get_stop_sources(route_data, stop_name):
    if stop_name in route_data.get("segment_sources", {}):
        return route_data["segment_sources"][stop_name]
    return [route_data["urls"][stop_name]]


def summarize_day_windowed(route_data, selected_date_str):
    direction_results = {}
    final_rows = {}

    for direction_key, stops_key, windows_key, trip_label in [
        ("outbound", "stops_out", "windows_out", "Out"),
        ("return", "stops_ret", "windows_ret", "Ret"),
    ]:
        stops = route_data[stops_key]
        windows = route_data[windows_key]
        segment_tables = {}
        worst_score = -1
        worst_segment = None
        worst_reasons = []
        worst_status = "🟢"

        for stop in stops:
            source_urls = get_stop_sources(route_data, stop)
            start_hour, end_hour = windows[stop]
            matching_rows = []
            segment_worst_score = -1
            segment_worst_reasons = []
            segment_worst_status = "🟢"

            for url in source_urls:
                raw = fetch_hourly_data(url)

                for hour in raw:
                    dt = parser.parse(hour["startTime"])
                    if dt.strftime("%A, %b %d") != selected_date_str:
                        continue

                    if start_hour <= dt.hour <= end_hour:
                        status, score, alerts_list, wind, pop, daytime, reasons = analyze_hour(
                            hour, stop, trip_label, route_data.get("direction")
                        )
                        matching_rows.append(build_hour_row(hour, status, alerts_list, wind, pop, daytime))

                        if score > segment_worst_score:
                            segment_worst_score = score
                            segment_worst_reasons = reasons
                            segment_worst_status = status

            if matching_rows:
                df = pd.DataFrame(matching_rows)
                df = df.sort_values(by=["Hour", "Time"]).drop_duplicates(
                    subset=["Time", "Status", "Temp", "Precip %", "Wind", "Weather", "Alerts"]
                )
                segment_tables[stop] = df
            else:
                segment_tables[stop] = pd.DataFrame()

            if segment_worst_score > worst_score:
                worst_score = segment_worst_score
                worst_segment = stop
                worst_reasons = segment_worst_reasons
                worst_status = segment_worst_status

        direction_results[direction_key] = {
            "score": max(worst_score, 0),
            "segment": worst_segment,
            "reasons": worst_reasons,
            "status": worst_status,
            "tables": segment_tables,
        }

    if direction_results["outbound"]["score"] >= direction_results["return"]["score"]:
        final_direction = "Outbound"
        final = direction_results["outbound"]
    else:
        final_direction = "Return"
        final = direction_results["return"]

    final_rows["outbound_tables"] = direction_results["outbound"]["tables"]
    final_rows["return_tables"] = direction_results["return"]["tables"]

    return {
        "final_score": final["score"],
        "final_label": risk_label(final["score"]),
        "final_status": final["status"],
        "driven_by": final_direction,
        "worst_segment": final["segment"],
        "why": reason_text_from_reasons(final["reasons"]),
        "outbound_score": direction_results["outbound"]["score"],
        "return_score": direction_results["return"]["score"],
        "outbound_tables": final_rows["outbound_tables"],
        "return_tables": final_rows["return_tables"],
    }


# --- UI START ---
st.title("🚛 Route Safety Commander V2")

route_name = st.selectbox("Select Destination", list(ROUTES.keys()))
route_data = ROUTES[route_name]

st.markdown("### Strategic Overview")

if st.button("🔄 Scan Entire Week (Strategy Mode)"):
    st.session_state.selected_day = None
    st.session_state[f"scan_route_{route_name}"] = True

scan_key = f"scan_route_{route_name}"
if scan_key not in st.session_state:
    st.session_state[scan_key] = False

if st.session_state[scan_key]:
    st.subheader("📅 Route Outlook")

    ref_url = list(route_data["urls"].values())[0]
    ref_data = fetch_hourly_data(ref_url)
    days_available = []

    if ref_data:
        seen_dates = set()
        for period in ref_data:
            dt = parser.parse(period["startTime"])
            date_str = dt.strftime("%A, %b %d")
            if date_str not in seen_dates:
                seen_dates.add(date_str)
                days_available.append(date_str)

    date_keys = days_available[:10]

    # Vertical rendering keeps the order correct on phones.
    for date_key in date_keys:
        if route_data.get("mode") == "windowed":
            summary = summarize_day_windowed(route_data, date_key)
            risk = summary["final_score"]
            label = summary["final_label"]
            worst_pass = summary["worst_segment"]
            reasons_text = summary["why"]
            driver = summary["driven_by"]
        else:
            summary = summarize_day_hourly(route_data, date_key)
            risk = summary["risk"]
            label = risk_label(risk)
            worst_pass = summary["worst_pass"]
            reasons = list(summary["reasons"])[:2]
            reasons_text = ", ".join(reasons) if reasons else ""
            driver = "Outbound"

        with st.container():
            if st.button(f"{date_key} — {label}", key=f"{route_name}_{date_key}"):
                st.session_state.selected_day = date_key
            st.caption(get_label_block(risk))
            if worst_pass:
                st.caption(f"Worst segment: {worst_pass}")
            if driver:
                st.caption(f"Driven by: {driver}")
            if reasons_text:
                st.caption(reasons_text)
            st.markdown("---")

st.divider()

st.markdown("### Tactical Daily Deep-Dive")

ref_url = list(route_data["urls"].values())[0]
ref_data = fetch_hourly_data(ref_url)

if ref_data:
    unique_dates = []
    seen_dates = set()

    for period in ref_data:
        dt = parser.parse(period["startTime"])
        date_str = dt.strftime("%A, %b %d")
        if date_str not in seen_dates:
            seen_dates.add(date_str)
            unique_dates.append(date_str)

    date_options = unique_dates[:10]

    if st.session_state.selected_day in date_options:
        selected_date_str = st.selectbox(
            "📅 Plan for (Hour-by-Hour):",
            date_options,
            index=date_options.index(st.session_state.selected_day),
        )
    else:
        selected_date_str = st.selectbox("📅 Plan for (Hour-by-Hour):", date_options)

    st.session_state.selected_day = selected_date_str

    st.subheader(f"📍 Selected Day: {selected_date_str}")
    st.info(route_data["note"])

    official_alerts_found = []
    for name in route_data["coords"].keys():
        lat_lon = route_data["coords"].get(name)
        if lat_lon:
            active_alerts = fetch_active_alerts(lat_lon)
            for alert in active_alerts:
                official_alerts_found.append(f"**{name}:** {alert}")

    if route_data.get("mode") == "windowed":
        summary = summarize_day_windowed(route_data, selected_date_str)

        st.markdown("### Final Route Call")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Final Rating", summary["final_label"])
        with c2:
            st.metric("Driven By", summary["driven_by"])
        with c3:
            st.metric("Worst Segment", summary["worst_segment"] or "-")
        with c4:
            st.metric("Out / Ret", f"{risk_label(summary['outbound_score'])} / {risk_label(summary['return_score'])}")

        st.warning(
            f"{summary['final_status']} {summary['final_label']} — "
            f"{summary['driven_by']} is worse. "
            f"Worst segment: {summary['worst_segment']}. "
            f"Why: {summary['why']}."
        )

        processed_data_out = summary["outbound_tables"]
        processed_data_ret = summary["return_tables"]

    else:
        processed_data_out = {}
        processed_data_ret = {}

        for name, url in route_data["urls"].items():
            raw = fetch_hourly_data(url)
            day_rows_out = []
            day_rows_ret = []

            for hour in raw:
                dt = parser.parse(hour["startTime"])
                if dt.strftime("%A, %b %d") == selected_date_str:
                    stat, score, alerts_list, wind, pop, daytime, _ = analyze_hour(
                        hour, name, "Out", route_data.get("direction")
                    )
                    row_data = build_hour_row(hour, stat, alerts_list, wind, pop, daytime)

                    if dt.hour in route_data["outbound_hours"]:
                        day_rows_out.append(row_data)
                    if dt.hour in route_data["return_hours"]:
                        day_rows_ret.append(row_data)

            processed_data_out[name] = pd.DataFrame(day_rows_out)
            processed_data_ret[name] = pd.DataFrame(day_rows_ret)

    tab_out, tab_ret, tab_alerts, tab_full = st.tabs(
        ["🚀 Outbound", "↩️ Return", "🚨 Alerts", "📋 Details"]
    )

    with tab_out:
        st.subheader(f"Outbound Trip: {selected_date_str}")
        render_trip_table(processed_data_out, route_data["stops_out"])

    with tab_ret:
        st.subheader(f"Return Trip: {selected_date_str}")
        render_trip_table(processed_data_ret, route_data["stops_ret"])

    with tab_alerts:
        st.subheader("Official NWS Warnings")
        if official_alerts_found:
            for alert in sorted(set(official_alerts_found)):
                st.error(alert)
        else:
            st.success("No active NWS warnings.")

    with tab_full:
        st.write("Full 24-hour breakdown for a specific location.")
        loc_select = st.selectbox("Select Location", list(route_data["coords"].keys()))

        raw_full = []
        for url in get_stop_sources(route_data, loc_select):
            raw_full.extend(fetch_hourly_data(url))

        full_rows = []
        for hour in raw_full:
            dt = parser.parse(hour["startTime"])
            if dt.strftime("%A, %b %d") == selected_date_str:
                stat, _, alerts_list, wind, pop, daytime, _ = analyze_hour(hour, loc_select)
                full_rows.append(
                    {
                        "Time": dt.strftime("%I %p"),
                        "Status": stat,
                        "Temp": f"{hour.get('temperature')}°",
                        "Precip %": f"{pop}%",
                        "Wind": f"{wind}",
                        "Weather": hour.get("shortForecast"),
                        "Alerts": ", ".join(alerts_list),
                    }
                )

        if full_rows:
            full_df = pd.DataFrame(full_rows).drop_duplicates()
            st.dataframe(full_df, hide_index=True, use_container_width=True)
        else:
            st.info("No hourly data returned for that location and day.")
else:
    st.error("No forecast data was returned for this route right now.")

st.markdown("---")
st.markdown(
    "**Essential Links:** "
    "[Idaho 511](https://511.idaho.gov/) | "
    "[MDT Maps](https://www.mdt.mt.gov/travinfo/) | "
    "[WSDOT](https://wsdot.com/Travel/Real-time/Map/)"
)
