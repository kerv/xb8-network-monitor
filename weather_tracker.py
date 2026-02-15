#!/usr/bin/env python3
import requests
import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import pytz

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'network_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

# Calgary coordinates
LATITUDE = 51.0447
LONGITUDE = -114.0719
MOUNTAIN_TZ = pytz.timezone('America/Denver')

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def fetch_historical_weather(start_date, end_date):
    """Fetch historical weather data from Open-Meteo API"""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        'latitude': LATITUDE,
        'longitude': LONGITUDE,
        'start_date': start_date,
        'end_date': end_date,
        'hourly': 'temperature_2m,precipitation,weather_code',
        'timezone': 'America/Denver'
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def fetch_current_weather():
    """Fetch current weather data from Open-Meteo API"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': LATITUDE,
        'longitude': LONGITUDE,
        'hourly': 'temperature_2m,precipitation,weather_code',
        'timezone': 'America/Denver',
        'past_days': 2,
        'forecast_days': 2
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def insert_weather_data(timestamp_str, temperature, precipitation, weather_code):
    """Insert weather data into database, converting MT to UTC"""
    # Parse as Mountain Time and convert to UTC
    mt_time = MOUNTAIN_TZ.localize(datetime.fromisoformat(timestamp_str))
    utc_time = mt_time.astimezone(pytz.UTC)
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO weather_data (timestamp, temperature, precipitation, weather_code)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (timestamp) DO UPDATE SET
            temperature = EXCLUDED.temperature,
            precipitation = EXCLUDED.precipitation,
            weather_code = EXCLUDED.weather_code
    """, (utc_time, temperature, precipitation, weather_code))
    conn.commit()
    conn.close()

def backfill_historical_data():
    """Backfill historical weather data from earliest network test"""
    conn = get_db()
    cur = conn.cursor()
    
    # Get earliest network test timestamp
    cur.execute("SELECT MIN(timestamp) FROM ping_tests")
    earliest_test = cur.fetchone()[0]
    
    # Get latest weather data timestamp
    cur.execute("SELECT MAX(timestamp) FROM weather_data")
    latest_weather = cur.fetchone()[0]
    
    conn.close()
    
    if not earliest_test:
        print("No network test data found")
        return
    
    start_date = earliest_test.date()
    # Only backfill up to 2 days ago (let forecast API handle recent data)
    end_date = (datetime.now() - timedelta(days=2)).date()
    
    if latest_weather:
        # Only fetch data after latest weather entry, but before the forecast API range
        latest_date = latest_weather.date()
        if latest_date >= end_date:
            print("Historical weather data is up to date")
            return
        start_date = max(start_date, (latest_weather + timedelta(hours=1)).date())
    
    if start_date >= end_date:
        print("Historical weather data is up to date")
        return
    
    print(f"Fetching weather data from {start_date} to {end_date}")
    
    # Fetch in chunks of 90 days (API limit)
    current_date = start_date
    while current_date < end_date:
        chunk_end = min(current_date + timedelta(days=89), end_date)
        
        print(f"Fetching {current_date} to {chunk_end}...")
        data = fetch_historical_weather(str(current_date), str(chunk_end))
        
        # Insert data
        hourly = data['hourly']
        for i, timestamp_str in enumerate(hourly['time']):
            temperature = hourly['temperature_2m'][i]
            precipitation = hourly['precipitation'][i]
            weather_code = hourly['weather_code'][i]
            
            insert_weather_data(timestamp_str, temperature, precipitation, weather_code)
        
        print(f"Inserted {len(hourly['time'])} weather records")
        current_date = chunk_end + timedelta(days=1)

def update_recent_weather():
    """Update recent weather data (last 24 hours)"""
    print("Updating recent weather data...")
    data = fetch_current_weather()
    
    hourly = data['hourly']
    count = 0
    for i, timestamp_str in enumerate(hourly['time']):
        temperature = hourly['temperature_2m'][i]
        precipitation = hourly['precipitation'][i]
        weather_code = hourly['weather_code'][i]
        
        insert_weather_data(timestamp_str, temperature, precipitation, weather_code)
        count += 1
    
    print(f"Updated {count} weather records")

if __name__ == "__main__":
    import sys
    import time
    
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        backfill_historical_data()
    else:
        while True:
            try:
                update_recent_weather()
            except Exception as e:
                print(f"Weather update error: {e}")
            time.sleep(3600)  # Update every hour
