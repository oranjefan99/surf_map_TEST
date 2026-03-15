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

# --- IMPROVED MAP INTERFACE ---

# 1. Initialize the Map with Usability Limits
m = folium.Map(
    location=[43.45, -3.6], 
    zoom_start=11, 
    min_zoom=9,           # State-of-the-art: Limited zoom out
    max_zoom=16,          # State-of-the-art: Limited zoom in
    tiles='openstreetmap', 
    control_scale=True    # State-of-the-art: Scale Bar
)

# 2. Add a Raster Layer (Satellite View)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', # Google Hybrid (Satellite + Labels)
    attr='Google',
    name='Satellite View',
    overlay=False,
    control=True
).add_to(m)

# 3. Define Color Map for Markers
color_map = {
    "beginner": "green",
    "intermediate": "beige",
    "advanced": "orange",
    "not recommended": "red"
}

# 4. Loop through data to create markers
for loc in data:
    # Webcam Database (Customize these URLs!)
    webcam_links = {
        "Somo Beach": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/santander/playa-de-somo.html",
        "Laredo Beach": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/laredo/playa-de-salve.html",
        "Berria Beach": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/santona/playa-de-berria.html",
        "El Sardinero": "https://www.skylinewebcams.com/en/webcam/espana/cantabria/santander/playa-del-sardinero.html"
    }
    # Default link if spot not in list
    cam_url = webcam_links.get(loc['name'], "https://www.surfline.com")

    # Styling the Popup with HTML/CSS for "Adequate Styling"
    html = f"""
    <div style="font-family: 'Helvetica', sans-serif; width: 200px; padding: 5px;">
        <h4 style="margin:0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #3498db;">{loc['name']}</h4>
        <div style="background-color: #f8f9fa; padding: 10px; border-radius: 8px; border-left: 5px solid {color_map.get(loc['level'])};">
            <b>Condition:</b> <span style="color: {color_map.get(loc['level'])}; text-transform: uppercase;">{loc['level']}</span><br>
            <b>Wave:</b> {loc['wave_height']:.2f}m @ {loc['wave_period']:.1f}s<br>
            <b>Wind:</b> {loc['wind_speed']:.1f} km/h
        </div>
        <br>
        <a href="{cam_url}" target="_blank" 
           style="display: block; text-align: center; background-color: #3498db; color: white; padding: 8px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 12px;">
           📺 VIEW LIVE WEBCAM
        </a>
    </div>
    """
    
    # Create Marker with FontAwesome icons for professional look
    folium.Marker(
        location=[loc['lat'], loc['lon']],
        popup=folium.Popup(html, max_width=250),
        tooltip=f"{loc['name']}: {loc['level'].title()}",
        icon=folium.Icon(color=color_map.get(loc['level']), icon="tint", prefix="fa")
    ).add_to(m)

# 5. Add Layer Control (Toggle between Street and Satellite)
folium.LayerControl(position='topright', collapsed=False).add_to(m)

# 6. Display the Map in Streamlit
st_folium(m, width="100%", height=600)

st.info("💡 Map updates automatically every hour. Data provided by Open-Meteo.")
