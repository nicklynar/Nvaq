import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Global Weather Dashboard", layout="wide")

# ---------- Helpers ----------

@st.cache_data(show_spinner=False, ttl=3600)
def geocode_name(q: str, count: int = 10):
    if not q:
        return []
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": q, "count": count, "language": "en", "format": "json"}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get("results", []) or []

def _build_param_list(selected_vars, mapping):
    return ",".join([mapping[v] for v in selected_vars])

def _split_ranges(start_d: date, end_d: date, forecast_past_days_max=92):
    """Return list of (endpoint, start, end) tuples to cover the requested range.
    Uses 'archive' for older dates and 'forecast' for recent dates, potentially splitting across both.
    """
    today = date.today()
    # Forecast endpoint can cover [today-forecast_past_days_max, today + 16] (future)
    forecast_earliest = today - timedelta(days=forecast_past_days_max)
    # Archive typically covers up to yesterday/today depending on processing; keep a 1-day buffer
    archive_latest = today - timedelta(days=1)

    ranges = []
    # Part 1: archive portion (strictly before forecast_earliest)
    if start_d <= archive_latest and start_d < forecast_earliest:
        r_start = start_d
        r_end = min(end_d, archive_latest, forecast_earliest - timedelta(days=1))
        if r_start <= r_end:
            ranges.append(("archive", r_start, r_end))

    # Part 2: forecast portion (anything overlapping [forecast_earliest, ...])
    f_start = max(start_d, forecast_earliest)
    f_end = end_d
    if f_start <= f_end:
        ranges.append(("forecast", f_start, f_end))

    return ranges

@st.cache_data(show_spinner=False, ttl=1800)
def fetch_hourly(lat, lon, start_d: date, end_d: date, hourly_vars, timezone="auto"):
    """Fetch hourly data across archive/forecast and concatenate."""
    pieces = []
    ranges = _split_ranges(start_d, end_d)
    for endpoint, s, e in ranges:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_vars),
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "timezone": timezone,
        }
        if endpoint == "archive":
            url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            url = "https://api.open-meteo.com/v1/forecast"
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        if "hourly" not in j or "time" not in j["hourly"]:
            # no data (e.g., outside coverage)
            continue
        df = pd.DataFrame(j["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        pieces.append(df)
    if not pieces:
        return pd.DataFrame()
    df_all = pd.concat(pieces).sort_index()
    # Deduplicate any overlapping hours
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    return df_all

@st.cache_data(show_spinner=False, ttl=1800)
def fetch_daily(lat, lon, start_d: date, end_d: date, daily_vars, timezone="auto"):
    pieces = []
    ranges = _split_ranges(start_d, end_d)
    for endpoint, s, e in ranges:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(daily_vars),
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "timezone": timezone,
        }
        url = "https://archive-api.open-meteo.com/v1/archive" if endpoint == "archive" else "https://api.open-meteo.com/v1/forecast"
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        if "daily" not in j or "time" not in j["daily"]:
            continue
        df = pd.DataFrame(j["daily"])
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        pieces.append(df)
    if not pieces:
        return pd.DataFrame()
    df_all = pd.concat(pieces).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    return df_all

def nice_loc_label(place):
    bits = [place.get("name")]
    admin = [place.get("admin1"), place.get("admin2")]
    admin = [a for a in admin if a]
    if admin:
        bits.append(", ".join(admin))
    country = place.get("country")
    if country:
        bits.append(country)
    return " · ".join([b for b in bits if b])

# ---------- UI ----------

st.title("🌍 Global Weather Dashboard")
st.caption("Powered by Open‑Meteo (free, no API key). Choose a location and date range to see real‑time and historical weather.")

with st.sidebar:
    st.header("🔎 Location")
    q = st.text_input("Search place name", placeholder="e.g., Sydney, London, New York, Tokyo")
    places = geocode_name(q) if q else []
    sel_place = None
    if places:
        labels = [nice_loc_label(p) for p in places]
        idx = st.selectbox("Matches", list(range(len(labels))), format_func=lambda i: labels[i], index=0)
        sel_place = places[idx]
    else:
        st.info("Type a city/town/landmark and pick a match above.")

    st.header("📅 Date Range")
    today = date.today()
    default_from = today - timedelta(days=7)
    start_d, end_d = st.date_input("Select range", value=(default_from, today), min_value=date(1950,1,1), max_value=today + timedelta(days=16))
    if isinstance(start_d, list) or isinstance(start_d, tuple):
        start_d, end_d = start_d[0], start_d[1]

    st.header("⚙️ Options")
    view_mode = st.radio("Resolution", ["Hourly", "Daily"], horizontal=True)
    show_vars = st.multiselect(
        "Variables",
        options=[
            "Temperature (°C)",
            "Relative Humidity (%)",
            "Precipitation (mm)",
            "Wind Speed (m/s)",
            "Wind Gusts (m/s)",
            "Surface Pressure (hPa)",
            "Cloud Cover (%)",
        ],
        default=["Temperature (°C)", "Precipitation (mm)", "Wind Speed (m/s)"],
    )

# Mappings to Open-Meteo variable names
HOURLY_MAP = {
    "Temperature (°C)": "temperature_2m",
    "Relative Humidity (%)": "relative_humidity_2m",
    "Precipitation (mm)": "precipitation",
    "Wind Speed (m/s)": "wind_speed_10m",
    "Wind Gusts (m/s)": "wind_gusts_10m",
    "Surface Pressure (hPa)": "pressure_msl",
    "Cloud Cover (%)": "cloudcover",
}

DAILY_MAP = {
    "Temperature (°C)": "temperature_2m_mean",
    "Relative Humidity (%)": "relative_humidity_2m_mean",
    "Precipitation (mm)": "precipitation_sum",
    "Wind Speed (m/s)": "wind_speed_10m_max",
    "Wind Gusts (m/s)": "wind_gusts_10m_max",
    "Surface Pressure (hPa)": "surface_pressure_mean",
    "Cloud Cover (%)": "cloud_cover_mean",
}

if sel_place is None:
    st.stop()

lat, lon = sel_place["latitude"], sel_place["longitude"]
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Latitude", f"{lat:.4f}")
with col2:
    st.metric("Longitude", f"{lon:.4f}")
with col3:
    st.metric("Elevation (m)", sel_place.get("elevation", "—"))

st.map(pd.DataFrame({"lat":[lat], "lon":[lon]}), size=50, zoom=8)

st.markdown("---")

# ---------- Fetch + Display ----------
if view_mode == "Hourly":
    vars_to_get = [HOURLY_MAP[v] for v in show_vars if v in HOURLY_MAP]
    if not vars_to_get:
        st.warning("Choose at least one variable.")
        st.stop()
    with st.spinner("Fetching hourly data..."):
        df = fetch_hourly(lat, lon, start_d, end_d, vars_to_get, timezone="auto")
else:
    vars_to_get = [DAILY_MAP[v] for v in show_vars if v in DAILY_MAP]
    if not vars_to_get:
        st.warning("Choose at least one variable.")
        st.stop()
    with st.spinner("Fetching daily data..."):
        df = fetch_daily(lat, lon, start_d, end_d, vars_to_get, timezone="auto")

if df.empty:
    st.error("No data returned for this range/location. Try adjusting the range or variables.")
    st.stop()

# Tidy for plotting
df_plot = df.reset_index().melt(id_vars="time", var_name="variable", value_name="value")

# Friendlier variable names
inv_map = {v:k for k,v in {**HOURLY_MAP, **DAILY_MAP}.items()}
df_plot["variable"] = df_plot["variable"].map(lambda x: inv_map.get(x, x))

# Charts
st.subheader("📈 Time Series")
for var in sorted(df_plot["variable"].unique()):
    sub = df_plot[df_plot["variable"] == var]
    fig = px.line(sub, x="time", y="value", title=var, labels={"time":"Time", "value": var})
    st.plotly_chart(fig, use_container_width=True)

# Table + Download
st.subheader("🧾 Data Table")
st.dataframe(df, use_container_width=True)
csv = df.to_csv().encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="weather_data.csv", mime="text/csv")

st.caption("Data: Open‑Meteo Forecast & Archive APIs. Some variables may be unavailable in certain regions or periods.")