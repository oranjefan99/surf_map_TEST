import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
from datetime import datetime
from zoneinfo import ZoneInfo

# --- PAGE CONFIG ---
st.set_page_config(page_title="Cantabria Surf Scout", layout="wide")

# --- DATA FETCHING (CACHED FOR 1 HOUR) ---
@st.cache_data(ttl=3600)
def get_surf_conditions():
    # Setup API client
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Spot Data (Name, Lat, Lon)
    locations = [
        ("Laredo Beach", 43.4189, -3.4362),
        ("El Puerto", 43.4152, -3.4204),
        ("Berria Beach", 43.4663, -3.4657),
        ("Somo Beach", 43.4595, -3.7325),
        ("El Sardinero", 43.4750, -3.7850)
    ]

    url_marine = "https://marine-api.open-meteo.com/v1/marine"
    url_weather = "https://api.open-meteo.com/v1/forecast"
    
    results = []
    
    for name, lat, lon in locations:
        # Get Marine Data
        m_params = {"latitude": lat, "longitude": lon, "hourly": ["wave_height", "wave_direction", "wave_period"], "timezone": "Europe/Berlin", "forecast_days": 1}
        m_resp = openmeteo.weather_api(url_marine, params=m_params)[0]
        
        # Get Weather Data (Wind)
        w_params = {"latitude": lat, "longitude": lon, "hourly": ["wind_speed_10m", "wind_direction_10m"], "timezone": "Europe/Berlin", "forecast_days": 1}
        w_resp = openmeteo.weather_api(url_weather, params=w_params)[0]

        # Use the current hour to get real-time data
        current_hour = datetime.now(ZoneInfo("Europe/Berlin")).hour
        
        # Extract variables
        wh = float(m_resp.Hourly().Variables(0).ValuesAsNumpy()[current_hour])
        wd = float(m_resp.Hourly().Variables(1).ValuesAsNumpy()[current_hour])
        wp = float(m_resp.Hourly().Variables(2).ValuesAsNumpy()[current_hour])
        ws = float(w_resp.Hourly().Variables(0).ValuesAsNumpy()[current_hour])
        wdir = float(w_resp.Hourly().Variables(1).ValuesAsNumpy()[current_hour])

        # Classification Logic
        if wh >= 0.5 and wh < 1.5: level = "beginner"
        elif wh >= 1.5 and wh < 2.2: level = "intermediate"
        elif wh >= 2.2: level = "advanced"
        else: level = "not recommended"

        results.append({
            "name": name, "lat": lat, "lon": lon,
            "wave_height": wh, "wave_direction": wd, "wave_period": wp,
            "wind_speed": ws, "wind_direction": wdir, "level": level
        })
    return results

# --- APP INTERFACE ---
st.title("🏄‍♂️ Surf's up... or down?")
st.subheader("A Skill-Based Forecast for Cantabria Beginners")

# Fetch data
data = get_surf_conditions()

# --- FINAL STATE-OF-THE-ART MAP ---

# 1. Initialize Map with STRICTER Zoom Constraints
# Tip: If zoom limits feel 'loose', ensure your zoom_start is between them.
m = folium.Map(
    location=[43.45, -3.6], 
    zoom_start=11, 
    min_zoom=10,           # Strictly limits how far you can pull away
    max_zoom=16,           # Strictly limits how close you can get
    tiles='openstreetmap', 
    control_scale=True,
    zoom_control=True
)

# Add Satellite Layer
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google',
    name='Satellite View',
    overlay=False,
    control=True
).add_to(m)

for loc in data:
    # Webcam links
    webcam_links = {
        "Somo Beach": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/santander/playa-de-somo.html",
        "Laredo Beach": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/laredo/playa-de-salve.html",
        "Berria Beach": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/santona/playa-de-berria.html",
        "El Sardinero": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/santander/playa-del-sardinero.html"
    }
    cam_url = webcam_links.get(loc['name'], "https://www.surfline.com")

    # LOGIC: Creating the rotating arrows
    # We use CSS transform: rotate() to point the arrow in the direction the wind/swell is GOING.
    # Note: API gives 'From' direction, so we add 180 to show where it's 'Going'.
    swell_dir = loc['wave_direction'] + 180
    wind_dir = loc['wind_direction'] + 180

    html = f"""
    <div style="font-family: 'Helvetica', sans-serif; width: 220px; padding: 5px;">
        <h4 style="margin:0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #3498db;">{loc['name']}</h4>
        
        <div style="background-color: #f8f9fa; padding: 10px; border-radius: 8px; border-left: 5px solid {color_map.get(loc['level'])};">
            <b>Condition:</b> <span style="color: {color_map.get(loc['level'])};"><b>{loc['level'].upper()}</b></span><br>
            <hr style="margin: 5px 0;">
            
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span><b>Wave:</b> {loc['wave_height']:.2f}m</span>
                <span style="display: inline-block; transform: rotate({swell_dir}deg); font-size: 20px;">➔</span>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span><b>Wind:</b> {loc['wind_speed']:.1f} km/h</span>
                <span style="display: inline-block; transform: rotate({wind_dir}deg); font-size: 20px; color: #7f8c8d;">➔</span>
            </div>
            
            <p style="font-size: 10px; margin: 5px 0 0 0; color: #95a5a6;">Arrows point in the direction of travel.</p>
        </div>
        <br>
        <a href="{cam_url}" target="_blank" 
           style="display: block; text-align: center; background-color: #3498db; color: white; padding: 8px; text-decoration: none; border-radius: 5px; font-weight: bold;">
           📺 VIEW LIVE WEBCAM
        </a>
    </div>
    """
    
    folium.Marker(
        location=[loc['lat'], loc['lon']],
        popup=folium.Popup(html, max_width=260),
        tooltip=f"{loc['name']}: {loc['level'].title()}",
        icon=folium.Icon(color=color_map.get(loc['level']), icon="tint", prefix="fa")
    ).add_to(m)

folium.LayerControl(position='topright', collapsed=False).add_to(m)

# 3. DISPLAY - Adding use_container_width helps Streamlit respect the map's internal constraints
st_folium(m, width=None, height=600, use_container_width=True)
