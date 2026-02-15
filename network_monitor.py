#!/usr/bin/env python3
import subprocess
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytz
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MOUNTAIN_TZ = pytz.timezone('America/Denver')

# Configuration
SPEED_TEST_INTERVAL = int(os.getenv('SPEED_TEST_INTERVAL', 3600))  # Default 1 hour

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'network_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

def ping_test(target='8.8.8.8'):
    try:
        result = subprocess.run(['ping', '-c', '5', '-W', '2', target], 
                              capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            avg_ping = None
            packet_loss = 100.0
            for line in lines:
                if 'rtt min/avg/max' in line:
                    avg_ping = float(line.split('/')[4])
                if 'packet loss' in line:
                    packet_loss = float(line.split('%')[0].split()[-1])
            return avg_ping if avg_ping else 0, packet_loss
        return None, 100.0
    except:
        return None, 100.0

def speed_test():
    try:
        result = subprocess.run(['speedtest', '--accept-license', '--accept-gdpr', '--format=json', '--server-id=4207'], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            download = data['download']['bandwidth'] / 125000
            upload = data['upload']['bandwidth'] / 125000
            return download, upload
        return None, None
    except:
        return None, None

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def insert_ping(timestamp, ping, packet_loss, status):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ping_tests (timestamp, ping, packet_loss, status) VALUES (%s, %s, %s, %s)",
        (timestamp, ping, packet_loss, status)
    )
    conn.commit()
    conn.close()

def insert_modem_signal(timestamp, downstream_avg_snr, downstream_min_snr, downstream_avg_power, downstream_max_power, upstream_avg_power, correctable=None, uncorrectable=None, worst_ch_id=None, worst_ch_corr=None, worst_ch_uncorr=None, channel_data=None, uptime_seconds=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO modem_signals (timestamp, downstream_avg_snr, downstream_min_snr, downstream_avg_power, downstream_max_power, upstream_avg_power, correctable_codewords, uncorrectable_codewords, worst_channel_id, worst_channel_correctable, worst_channel_uncorrectable, uptime_seconds) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (timestamp, downstream_avg_snr, downstream_min_snr, downstream_avg_power, downstream_max_power, upstream_avg_power, correctable, uncorrectable, worst_ch_id, worst_ch_corr, worst_ch_uncorr, uptime_seconds)
    )
    
    # Detect restart: if uptime decreased or is very small compared to time since last reading
    if uptime_seconds is not None:
        cur.execute("SELECT timestamp, uptime_seconds FROM modem_signals WHERE uptime_seconds IS NOT NULL ORDER BY timestamp DESC LIMIT 1 OFFSET 1")
        prev = cur.fetchone()
        if prev:
            prev_timestamp, prev_uptime = prev
            # Make prev_timestamp timezone-aware if it isn't
            if prev_timestamp.tzinfo is None:
                prev_timestamp = MOUNTAIN_TZ.localize(prev_timestamp)
            time_diff = (timestamp - prev_timestamp).total_seconds()
            # If uptime went backwards or didn't increase proportionally, it's a restart
            if uptime_seconds < prev_uptime or (uptime_seconds - prev_uptime) < (time_diff * 0.5):
                # Calculate approximate restart time
                restart_time = timestamp - timedelta(seconds=uptime_seconds)
                cur.execute(
                    "INSERT INTO modem_restarts (timestamp, detected_at, uptime_seconds) VALUES (%s, %s, %s)",
                    (restart_time, timestamp, uptime_seconds)
                )
                print(f"Modem restart detected! Restarted at ~{restart_time}, uptime now: {uptime_seconds}s")
    
    # Insert per-channel data
    if channel_data:
        for ch_id, corr, uncorr in channel_data:
            cur.execute(
                "INSERT INTO channel_codewords (timestamp, channel_id, correctable, uncorrectable) VALUES (%s, %s, %s, %s)",
                (timestamp, ch_id, corr, uncorr)
            )
    
    conn.commit()
    conn.close()

def get_modem_signals():
    """Scrape modem signal data from XB8"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        
        session = requests.Session()
        
        # Login
        login_data = {
            'username': os.getenv('ROUTER_USERNAME', 'admin'), 
            'password': os.getenv('ROUTER_PASSWORD')
        }
        router_url = os.getenv('ROUTER_URL', 'http://192.168.1.1')
        session.post(f'{router_url}/check.jst', data=login_data, timeout=10)
        
        # Get page
        page = session.get(f'{router_url}/network_setup.jst', timeout=10)
        
        soup = BeautifulSoup(page.text, 'html.parser')
        text = soup.get_text()
        lines = text.split('\n')
        
        data = {}
        
        # Parse downstream
        for i, line in enumerate(lines):
            if 'Channel Bonding Value' in line and i > 0 and 'Downstream' in lines[i-1]:
                for j in range(i, min(i+30, len(lines))):
                    if lines[j].strip() == 'SNR' and j+1 < len(lines):
                        snrs = re.findall(r'([\d.]+)\s*dB', lines[j+1])
                        if snrs:
                            data['downstream_avg_snr'] = round(sum(map(float, snrs)) / len(snrs), 1)
                            data['downstream_min_snr'] = round(min(map(float, snrs)), 1)
                    if lines[j].strip() == 'Power Level' and j+1 < len(lines):
                        powers = re.findall(r'([\d.]+)\s*dBmV', lines[j+1])
                        if powers:
                            data['downstream_avg_power'] = round(sum(map(float, powers)) / len(powers), 1)
                            data['downstream_max_power'] = round(max(map(float, powers)), 1)
                break
        
        # Parse upstream
        for i, line in enumerate(lines):
            if 'Channel Bonding Value' in line and i > 0 and 'Upstream' in lines[i-1]:
                for j in range(i, min(i+30, len(lines))):
                    if lines[j].strip() == 'Power Level' and j+1 < len(lines):
                        powers = re.findall(r'([\d.]+)\s*dBmV', lines[j+1])
                        if powers:
                            data['upstream_avg_power'] = round(sum(map(float, powers)) / len(powers), 1)
                        break
                break
        
        # Parse codeword errors using regex on raw HTML (more reliable than BeautifulSoup)
        # Find CM Error Codewords table
        codewords_start = page.text.find('CM Error Codewords')
        channel_ids = []
        correctable_values = []
        uncorrectable_values = []
        
        if codewords_start > 0:
            table_section = page.text[codewords_start:codewords_start+10000]
            
            # Extract Channel IDs
            ch_match = re.search(r'Channel ID</td>(.*?)</tr>', table_section, re.DOTALL)
            if ch_match:
                channel_ids = re.findall(r'<div class="netWidth">(\d+)</div>', ch_match.group(1))
            
            # Extract Correctable Codewords
            corr_match = re.search(r'Correctable Codewords</td>(.*?)</tr>', table_section, re.DOTALL)
            if corr_match:
                correctable_values = re.findall(r'<div class="netWidth">(\d+)</div>', corr_match.group(1))
            
            # Extract Uncorrectable Codewords
            uncorr_match = re.search(r'Uncorrectable Codewords</td>(.*?)</tr>', table_section, re.DOTALL)
            if uncorr_match:
                uncorrectable_values = re.findall(r'<div class="netWidth">(\d+)</div>', uncorr_match.group(1))
        
        # Build channel data from parsed values
        if channel_ids and correctable_values and uncorrectable_values:
            total_corr = 0
            total_uncorr = 0
            channel_data = []
            max_corr = 0
            worst_ch_id = None
            worst_ch_corr = 0
            worst_ch_uncorr = 0
            
            for i in range(min(len(channel_ids), len(correctable_values), len(uncorrectable_values))):
                ch_id_int = int(channel_ids[i])
                corr_int = int(correctable_values[i])
                uncorr_int = int(uncorrectable_values[i])
                
                total_corr += corr_int
                total_uncorr += uncorr_int
                channel_data.append((ch_id_int, corr_int, uncorr_int))
                
                if corr_int > max_corr:
                    max_corr = corr_int
                    worst_ch_id = ch_id_int
                    worst_ch_corr = corr_int
                    worst_ch_uncorr = uncorr_int
            
            data['correctable_codewords'] = total_corr
            data['uncorrectable_codewords'] = total_uncorr
            data['channel_data'] = channel_data
            data['worst_channel_id'] = worst_ch_id
            data['worst_channel_correctable'] = worst_ch_corr
            data['worst_channel_uncorrectable'] = worst_ch_uncorr
        
        # Extract System Uptime
        uptime_match = re.search(r'System Uptime:</span>\s*<span[^>]*>\s*(\d+)\s*days?\s*(\d+)h:\s*(\d+)m:\s*(\d+)s', page.text, re.IGNORECASE)
        if uptime_match:
            days = int(uptime_match.group(1))
            hours = int(uptime_match.group(2))
            minutes = int(uptime_match.group(3))
            seconds = int(uptime_match.group(4))
            data['uptime_seconds'] = days * 86400 + hours * 3600 + minutes * 60 + seconds
        
        return data
    except Exception as e:
        print(f"Error getting modem signals: {e}")
        return None

def insert_cmts_ping(timestamp, ping, packet_loss, status):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cmts_tests (timestamp, ping, packet_loss, status) VALUES (%s, %s, %s, %s)",
        (timestamp, ping, packet_loss, status)
    )
    conn.commit()
    conn.close()

def insert_speed(timestamp, download, upload):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO speed_tests (timestamp, download, upload) VALUES (%s, %s, %s)",
        (timestamp, download, upload)
    )
    conn.commit()
    conn.close()

def load_data():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all ping tests
    cur.execute("SELECT timestamp, ping, packet_loss, status FROM ping_tests ORDER BY timestamp")
    ping_tests = cur.fetchall()
    
    # Get all speed tests
    cur.execute("SELECT timestamp, download, upload FROM speed_tests ORDER BY timestamp")
    speed_tests = {row['timestamp']: row for row in cur.fetchall()}
    
    conn.close()
    
    # Merge data
    tests = []
    for row in ping_tests:
        test = {
            'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'ping': row['ping'],
            'packet_loss': row['packet_loss'],
            'status': row['status']
        }
        if row['timestamp'] in speed_tests:
            test['download'] = speed_tests[row['timestamp']]['download']
            test['upload'] = speed_tests[row['timestamp']]['upload']
        tests.append(test)
    
    return {"tests": tests}

def load_data_unlocked():
    return load_data()

def save_data_unlocked(data):
    pass  # No longer needed with postgres

def speed_test_async(timestamp):
    """Run speed test in background and update database"""
    try:
        print(f"[{timestamp}] Running speed test in background...")
        download, upload = speed_test()
        
        if download:
            insert_speed(timestamp, download, upload)
            print(f"[{timestamp}] Speed test: ↓ {download:.1f} Mbps | ↑ {upload:.1f} Mbps")
        else:
            insert_speed(timestamp, 0, 0)
            print(f"[{timestamp}] Speed test FAILED")
        
        # No need to regenerate HTML - using static HTML with API
    except Exception as e:
        print(f"[{timestamp}] Speed test thread error: {e}")

def main():
    print("Network monitor started")
    
    # Track last modem scrape time
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(timestamp), '1970-01-01') FROM modem_signals")
    last_scrape = cur.fetchone()[0]
    conn.close()
    
    if isinstance(last_scrape, str):
        last_modem_scrape = datetime.strptime(last_scrape, '%Y-%m-%d %H:%M:%S').replace(tzinfo=MOUNTAIN_TZ)
    else:
        last_modem_scrape = last_scrape.replace(tzinfo=pytz.UTC).astimezone(MOUNTAIN_TZ) if last_scrape.year > 1970 else datetime.now(MOUNTAIN_TZ) - timedelta(minutes=10)
    
    print(f"Last modem scrape: {last_modem_scrape}")
    
    # Track last speed test time separately
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(timestamp), '1970-01-01') FROM speed_tests")
    last_speed_test = cur.fetchone()[0]
    conn.close()
    
    if isinstance(last_speed_test, str):
        last_speed_test_time = datetime.strptime(last_speed_test, '%Y-%m-%d %H:%M:%S').replace(tzinfo=MOUNTAIN_TZ)
    else:
        last_speed_test_time = last_speed_test.replace(tzinfo=pytz.UTC).astimezone(MOUNTAIN_TZ) if last_speed_test.year > 1970 else datetime.now(MOUNTAIN_TZ) - timedelta(minutes=20)
    
    while True:
        timestamp_dt = datetime.now(MOUNTAIN_TZ)
        timestamp = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Ping primary target
        ping_target = os.getenv('PING_TARGET', '8.8.8.8')
        ping, packet_loss = ping_test(ping_target)
        status = "OK"
        if ping is None:
            status = "FAILED"
        elif ping > 100:
            status = "HIGH_LATENCY"
        elif packet_loss > 0:
            status = "PACKET_LOSS"
        insert_ping(timestamp_dt, ping, packet_loss, status)
        
        # Ping CMTS (first hop)
        cmts_target = os.getenv('CMTS_TARGET')
        cmts_ping, cmts_packet_loss = ping_test(cmts_target)
        cmts_status = "OK"
        if cmts_ping is None:
            cmts_status = "FAILED"
        elif cmts_ping > 100:
            cmts_status = "HIGH_LATENCY"
        elif cmts_packet_loss > 0:
            cmts_status = "PACKET_LOSS"
        insert_cmts_ping(timestamp_dt, cmts_ping, cmts_packet_loss, cmts_status)
        
        # Speed test every SPEED_TEST_INTERVAL seconds, modem signals every 5 minutes
        time_since_last_scrape = (timestamp_dt - last_modem_scrape).total_seconds()
        time_since_last_speed_test = (timestamp_dt - last_speed_test_time).total_seconds()
        
        if time_since_last_speed_test >= SPEED_TEST_INTERVAL:
            # Start speed test in background thread
            print(f"[{timestamp}] Triggering speed test (last test was {time_since_last_speed_test:.0f}s ago)")
            thread = threading.Thread(target=speed_test_async, args=(timestamp_dt,))
            thread.daemon = True
            thread.start()
            last_speed_test_time = timestamp_dt
        
        if time_since_last_scrape >= 300:  # 5 minutes = 300 seconds
            # Get modem signals
            modem_data = get_modem_signals()
            if modem_data:
                insert_modem_signal(
                    timestamp_dt,
                    modem_data.get('downstream_avg_snr'),
                    modem_data.get('downstream_min_snr'),
                    modem_data.get('downstream_avg_power'),
                    modem_data.get('downstream_max_power'),
                    modem_data.get('upstream_avg_power'),
                    modem_data.get('correctable_codewords'),
                    modem_data.get('uncorrectable_codewords'),
                    modem_data.get('worst_channel_id'),
                    modem_data.get('worst_channel_correctable'),
                    modem_data.get('worst_channel_uncorrectable'),
                    modem_data.get('channel_data'),
                    modem_data.get('uptime_seconds')
                )
                uptime_str = f" | Uptime: {modem_data.get('uptime_seconds')}s" if modem_data.get('uptime_seconds') else ""
                print(f"[{timestamp}] Modem: DS SNR={modem_data.get('downstream_avg_snr')}dB US Pwr={modem_data.get('upstream_avg_power')}dBmV{uptime_str} | Total Errors: C={modem_data.get('correctable_codewords')} U={modem_data.get('uncorrectable_codewords')} | Worst Ch{modem_data.get('worst_channel_id')}: C={modem_data.get('worst_channel_correctable')} U={modem_data.get('worst_channel_uncorrectable')} | Saved {len(modem_data.get('channel_data', []))} channels")
            
            last_modem_scrape = timestamp_dt
        
        print(f"[{timestamp}] Google: {ping}ms/{packet_loss}% | CMTS: {cmts_ping}ms/{cmts_packet_loss}% | Status: {status}")
        
        # No sleep - ping test itself provides the delay

if __name__ == "__main__":
    main()
