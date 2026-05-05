#!/usr/bin/env python3
from flask import Flask, jsonify, request, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

MOUNTAIN_TZ = pytz.timezone('America/Denver')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'network_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def calculate_summary(tests):
    """Calculate summary statistics from all tests"""
    total_tests = len(tests)
    high_latency = sum(1 for t in tests if t.get('status') == 'HIGH_LATENCY')
    failures = sum(1 for t in tests if t.get('status') == 'FAILED')
    google_packet_loss = sum(1 for t in tests if t.get('packet_loss', 0) > 0)
    cmts_packet_loss = sum(1 for t in tests if t.get('cmts_packet_loss', 0) > 0)
    
    # Calculate averages
    valid_pings = [t['ping'] for t in tests if t.get('ping') and t['ping'] > 0]
    avg_latency = sum(valid_pings) / len(valid_pings) if valid_pings else 0
    
    packet_losses = [t['packet_loss'] for t in tests if t.get('packet_loss') is not None]
    avg_packet_loss = sum(packet_losses) / len(packet_losses) if packet_losses else 0
    
    valid_cmts_pings = [t['cmts_ping'] for t in tests if t.get('cmts_ping') and t['cmts_ping'] > 0]
    avg_cmts_latency = sum(valid_cmts_pings) / len(valid_cmts_pings) if valid_cmts_pings else 0
    
    cmts_packet_losses = [t['cmts_packet_loss'] for t in tests if t.get('cmts_packet_loss') is not None]
    avg_cmts_packet_loss = sum(cmts_packet_losses) / len(cmts_packet_losses) if cmts_packet_losses else 0
    
    # Latency difference
    latency_diff = avg_cmts_latency - avg_latency if avg_cmts_latency and avg_latency else 0
    
    # Speed test averages
    valid_downloads = [t['download'] for t in tests if t.get('download') is not None and t['download'] > 0]
    avg_download = sum(valid_downloads) / len(valid_downloads) if valid_downloads else None
    
    valid_uploads = [t['upload'] for t in tests if t.get('upload') is not None and t['upload'] > 0]
    avg_upload = sum(valid_uploads) / len(valid_uploads) if valid_uploads else None
    
    return {
        'total_tests': total_tests,
        'high_latency': high_latency,
        'failures': failures,
        'google_packet_loss': google_packet_loss,
        'cmts_packet_loss': cmts_packet_loss,
        'avg_latency': round(avg_latency, 1),
        'avg_packet_loss': round(avg_packet_loss, 1),
        'avg_cmts_latency': round(avg_cmts_latency, 1),
        'avg_cmts_packet_loss': round(avg_cmts_packet_loss, 1),
        'latency_diff': round(latency_diff, 1),
        'avg_download': round(avg_download, 1) if avg_download else None,
        'avg_upload': round(avg_upload, 1) if avg_upload else None
    }

def decimate_tests(tests, target=2000):
    """Intelligently decimate test data while preserving outliers and time gaps"""
    if len(tests) <= target:
        return tests
    
    result = [tests[0]]  # Always keep first
    step = max(1, len(tests) // target)
    
    for i in range(1, len(tests) - 1, step):
        window_end = min(i + step, len(tests))
        window = tests[i:window_end]
        
        # Check for time gaps (missing data periods)
        if i > 0:
            prev_time = datetime.strptime(result[-1]['timestamp'], '%Y-%m-%d %H:%M:%S')
            curr_time = datetime.strptime(window[0]['timestamp'], '%Y-%m-%d %H:%M:%S')
            time_gap = (curr_time - prev_time).total_seconds()
            
            # If gap > 15 minutes, keep both boundary points to show the gap
            if time_gap > 900:
                result.append(window[0])
                if len(window) > 1:
                    result.append(window[-1])
                continue
        
        # Find outliers in window (packet loss, high latency, failures)
        outliers = [t for t in window if 
                   t.get('packet_loss', 0) > 0 or 
                   t.get('cmts_packet_loss', 0) > 0 or
                   (t.get('ping') and t['ping'] > 100) or
                   t.get('status') == 'FAILED' or
                   (t.get('download') is not None and t['download'] == 0)]
        
        if outliers:
            result.extend(outliers)  # Keep all outliers
        else:
            # Check variance in normal data
            pings = [t['ping'] for t in window if t.get('ping') and t['ping'] > 0]
            if len(pings) > 1:
                variance = max(pings) - min(pings)
                if variance > 20:
                    # High variance - keep min, middle, max
                    sorted_window = sorted(window, key=lambda t: t.get('ping', 0))
                    result.extend([sorted_window[0], sorted_window[len(sorted_window)//2], sorted_window[-1]])
                else:
                    # Low variance - keep middle point
                    result.append(window[len(window)//2])
            else:
                result.append(window[len(window)//2])
    
    result.append(tests[-1])  # Always keep last
    
    # Sort by timestamp and remove duplicates
    seen = set()
    unique_result = []
    for test in sorted(result, key=lambda t: t['timestamp']):
        if test['timestamp'] not in seen:
            seen.add(test['timestamp'])
            unique_result.append(test)
    
    return unique_result

@app.route('/')
@app.route('/network.html')
def dashboard():
    return send_file('network.html')


def get_summary_from_db(cur, cutoff=None):
    """Calculate summary statistics in SQL instead of fetching all rows"""
    where = "WHERE p.timestamp >= %s" if cutoff else ""
    params = (cutoff,) if cutoff else ()

    cur.execute(f"""
        WITH bucketed AS (
            SELECT DISTINCT ON (date_trunc('second', p.timestamp) - (EXTRACT(SECOND FROM p.timestamp)::int %% 10) * INTERVAL '1 second')
                   p.ping, p.packet_loss, p.status, c.ping as cmts_ping, c.packet_loss as cmts_packet_loss
            FROM ping_tests p
            LEFT JOIN cmts_tests c ON p.timestamp = c.timestamp
            {where}
            ORDER BY date_trunc('second', p.timestamp) - (EXTRACT(SECOND FROM p.timestamp)::int %% 10) * INTERVAL '1 second', p.timestamp
        )
        SELECT
            COUNT(*) as total_tests,
            SUM(CASE WHEN status = 'HIGH_LATENCY' THEN 1 ELSE 0 END) as high_latency,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failures,
            SUM(CASE WHEN packet_loss > 0 THEN 1 ELSE 0 END) as google_packet_loss,
            ROUND(AVG(CASE WHEN ping > 0 THEN ping END)::numeric, 1) as avg_latency,
            ROUND(AVG(packet_loss)::numeric, 1) as avg_packet_loss,
            SUM(CASE WHEN cmts_packet_loss > 0 THEN 1 ELSE 0 END) as cmts_packet_loss,
            ROUND(AVG(CASE WHEN cmts_ping > 0 THEN cmts_ping END)::numeric, 1) as avg_cmts_latency,
            ROUND(AVG(cmts_packet_loss)::numeric, 1) as avg_cmts_packet_loss
        FROM bucketed
    """, params)
    row = cur.fetchone()

    cur.execute(f"""
        SELECT ROUND(AVG(CASE WHEN download > 0 THEN download END)::numeric, 1) as avg_download,
               ROUND(AVG(CASE WHEN upload > 0 THEN upload END)::numeric, 1) as avg_upload
        FROM speed_tests {"WHERE timestamp >= %s" if cutoff else ""}
    """, params)
    speed = cur.fetchone()

    avg_latency = float(row['avg_latency']) if row['avg_latency'] else 0
    avg_cmts = float(row['avg_cmts_latency']) if row['avg_cmts_latency'] else 0

    return {
        'total_tests': row['total_tests'],
        'high_latency': row['high_latency'],
        'failures': row['failures'],
        'google_packet_loss': row['google_packet_loss'],
        'cmts_packet_loss': row['cmts_packet_loss'],
        'avg_latency': avg_latency,
        'avg_packet_loss': float(row['avg_packet_loss']) if row['avg_packet_loss'] else 0,
        'avg_cmts_latency': avg_cmts,
        'avg_cmts_packet_loss': float(row['avg_cmts_packet_loss']) if row['avg_cmts_packet_loss'] else 0,
        'latency_diff': round(avg_cmts - avg_latency, 1),
        'avg_download': float(speed['avg_download']) if speed['avg_download'] else None,
        'avg_upload': float(speed['avg_upload']) if speed['avg_upload'] else None
    }


def get_hourly_avg_from_db(cur, cutoff=None):
    """Calculate hourly packet loss averages in SQL"""
    where = "AND timestamp >= %s" if cutoff else ""
    params = (cutoff,) if cutoff else ()

    cur.execute(f"""
        SELECT EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Denver')::int as hour,
               AVG(packet_loss) as avg_loss
        FROM ping_tests
        WHERE TRUE {where}
        GROUP BY hour
    """, params)

    hourly = [0.0] * 24
    for row in cur.fetchall():
        hourly[row['hour']] = float(row['avg_loss']) if row['avg_loss'] else 0
    return hourly


@app.route('/api/network/data')
def get_data():
    minutes = request.args.get('minutes', type=int)
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cutoff = datetime.now() - timedelta(minutes=minutes) if minutes else None

    # For "All" queries, sample data in SQL to avoid fetching 500K+ rows
    # Use TABLESAMPLE for bulk, then UNION outliers to preserve them
    if cutoff:
        cur.execute(
            "SELECT timestamp, ping, packet_loss, status FROM ping_tests WHERE timestamp >= %s ORDER BY timestamp",
            (cutoff,)
        )
    else:
        # For "All" view, aggregate into 15-minute buckets with avg + max
        cur.execute("""
            SELECT date_trunc('hour', p.timestamp) + INTERVAL '15 min' * FLOOR(EXTRACT(MINUTE FROM p.timestamp) / 15) as timestamp,
                   AVG(p.ping) as ping, MAX(p.packet_loss) as packet_loss,
                   CASE WHEN MAX(CASE WHEN p.status = 'FAILED' THEN 1 ELSE 0 END) = 1 THEN 'FAILED'
                        WHEN MAX(CASE WHEN p.status = 'HIGH_LATENCY' THEN 1 ELSE 0 END) = 1 THEN 'HIGH_LATENCY'
                        WHEN MAX(CASE WHEN p.status = 'PACKET_LOSS' THEN 1 ELSE 0 END) = 1 THEN 'PACKET_LOSS'
                        ELSE 'OK' END as status
            FROM ping_tests p
            GROUP BY 1 ORDER BY 1
        """)
    
    ping_tests = cur.fetchall()
    ping_timestamps = {row['timestamp'] for row in ping_tests}
    
    # Get CMTS tests - only for timestamps we have ping data for
    if cutoff:
        cur.execute(
            "SELECT timestamp, ping, packet_loss, status FROM cmts_tests WHERE timestamp >= %s ORDER BY timestamp",
            (cutoff,)
        )
    else:
        cur.execute("""
            SELECT date_trunc('hour', c.timestamp) + INTERVAL '15 min' * FLOOR(EXTRACT(MINUTE FROM c.timestamp) / 15) as timestamp,
                   AVG(c.ping) as ping, MAX(c.packet_loss) as packet_loss,
                   CASE WHEN MAX(CASE WHEN c.status = 'FAILED' THEN 1 ELSE 0 END) = 1 THEN 'FAILED'
                        WHEN MAX(CASE WHEN c.status = 'HIGH_LATENCY' THEN 1 ELSE 0 END) = 1 THEN 'HIGH_LATENCY'
                        WHEN MAX(CASE WHEN c.status = 'PACKET_LOSS' THEN 1 ELSE 0 END) = 1 THEN 'PACKET_LOSS'
                        ELSE 'OK' END as status
            FROM cmts_tests c
            GROUP BY 1 ORDER BY 1
        """)
    
    cmts_tests = {row['timestamp']: row for row in cur.fetchall()}
    BUCKET_EXPR = "date_trunc('hour', timestamp) + INTERVAL '15 min' * FLOOR(EXTRACT(MINUTE FROM timestamp) / 15)"

    # Get channel codewords and find top 5 worst channels
    if cutoff:
        cur.execute(
            "SELECT channel_id, MAX(correctable) as max_correctable FROM channel_codewords WHERE timestamp >= %s GROUP BY channel_id ORDER BY max_correctable DESC LIMIT 5",
            (cutoff,)
        )
    else:
        cur.execute("SELECT channel_id, MAX(correctable) as max_correctable FROM channel_codewords GROUP BY channel_id ORDER BY max_correctable DESC LIMIT 5")
    
    top_channels = [row['channel_id'] for row in cur.fetchall()]
    
    # Get codeword data for top channels
    channel_data = {}
    if top_channels:
        if cutoff:
            cur.execute(
                "SELECT timestamp, channel_id, correctable, uncorrectable FROM channel_codewords WHERE channel_id = ANY(%s) AND timestamp >= %s ORDER BY timestamp",
                (top_channels, cutoff)
            )
        else:
            cur.execute(
                f"SELECT {BUCKET_EXPR} as timestamp, channel_id, MAX(correctable) as correctable, MAX(uncorrectable) as uncorrectable FROM channel_codewords WHERE channel_id = ANY(%s) GROUP BY 1, channel_id ORDER BY 1",
                (top_channels,)
            )
        
        for row in cur.fetchall():
            ts = row['timestamp']
            if ts not in channel_data:
                channel_data[ts] = {}
            channel_data[ts][row['channel_id']] = {
                'correctable': int(row['correctable']) if row['correctable'] else None,
                'uncorrectable': int(row['uncorrectable']) if row['uncorrectable'] else None
            }
    
    # Get speed tests
    if cutoff:
        cur.execute(
            "SELECT timestamp, download, upload FROM speed_tests WHERE timestamp >= %s ORDER BY timestamp",
            (cutoff,)
        )
    else:
        cur.execute("SELECT timestamp, download, upload FROM speed_tests ORDER BY timestamp")
    
    speed_test_rows = cur.fetchall()
    speed_tests_array = []
    for row in speed_test_rows:
        utc_time = row['timestamp'].replace(tzinfo=pytz.UTC)
        mt_time = utc_time.astimezone(MOUNTAIN_TZ)
        speed_tests_array.append({
            'timestamp': mt_time.strftime('%Y-%m-%d %H:%M:%S'),
            'download': row['download'],
            'upload': row['upload']
        })
    
    # Get modem signals
    if cutoff:
        cur.execute(
            "SELECT timestamp, downstream_avg_snr, downstream_min_snr, downstream_avg_power, downstream_max_power, upstream_avg_power, correctable_codewords, uncorrectable_codewords, worst_channel_id, worst_channel_correctable, worst_channel_uncorrectable FROM modem_signals WHERE timestamp >= %s ORDER BY timestamp",
            (cutoff,)
        )
    else:
        cur.execute(f"""
            SELECT {BUCKET_EXPR} as timestamp,
                   AVG(downstream_avg_snr) as downstream_avg_snr, MIN(downstream_min_snr) as downstream_min_snr,
                   AVG(downstream_avg_power) as downstream_avg_power, MAX(downstream_max_power) as downstream_max_power,
                   AVG(upstream_avg_power) as upstream_avg_power,
                   MAX(correctable_codewords) as correctable_codewords, MAX(uncorrectable_codewords) as uncorrectable_codewords,
                   NULL::int as worst_channel_id, NULL::numeric as worst_channel_correctable, NULL::numeric as worst_channel_uncorrectable
            FROM modem_signals GROUP BY 1 ORDER BY 1
        """)
    
    modem_signals = {row['timestamp']: row for row in cur.fetchall()}
    
    # Merge data
    tests = []
    for row in ping_tests:
        # Convert UTC timestamp to Mountain Time
        utc_time = row['timestamp'].replace(tzinfo=pytz.UTC)
        mt_time = utc_time.astimezone(MOUNTAIN_TZ)
        
        test = {
            'timestamp': mt_time.strftime('%Y-%m-%d %H:%M:%S'),
            'ping': row['ping'],
            'packet_loss': row['packet_loss'],
            'status': row['status']
        }
        if row['timestamp'] in cmts_tests:
            test['cmts_ping'] = cmts_tests[row['timestamp']]['ping']
            test['cmts_packet_loss'] = cmts_tests[row['timestamp']]['packet_loss']
        if row['timestamp'] in modem_signals:
            test['modem_ds_snr'] = modem_signals[row['timestamp']]['downstream_avg_snr']
            test['modem_ds_min_snr'] = modem_signals[row['timestamp']]['downstream_min_snr']
            test['modem_ds_power'] = modem_signals[row['timestamp']]['downstream_avg_power']
            test['modem_ds_max_power'] = modem_signals[row['timestamp']]['downstream_max_power']
            test['modem_us_power'] = modem_signals[row['timestamp']]['upstream_avg_power']
        if row['timestamp'] in channel_data:
            test['channels'] = channel_data[row['timestamp']]
        tests.append(test)
    
    # Get modem restart events
    if cutoff:
        cur.execute(
            "SELECT timestamp FROM modem_restarts WHERE timestamp >= %s ORDER BY timestamp",
            (cutoff,)
        )
    else:
        cur.execute("SELECT timestamp FROM modem_restarts ORDER BY timestamp")
    
    restarts = []
    for row in cur.fetchall():
        # Convert UTC timestamp to Mountain Time
        utc_time = row['timestamp'].replace(tzinfo=pytz.UTC)
        mt_time = utc_time.astimezone(MOUNTAIN_TZ)
        restarts.append(mt_time.strftime('%Y-%m-%d %H:%M:%S'))
    
    # Get latest uptime and timestamp
    cur.execute("SELECT timestamp, uptime_seconds FROM modem_signals WHERE uptime_seconds IS NOT NULL ORDER BY timestamp DESC LIMIT 1")
    uptime_row = cur.fetchone()
    uptime_seconds = uptime_row['uptime_seconds'] if uptime_row else None
    uptime_timestamp = uptime_row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if uptime_row else None
    
    # Get weather data for the same time range (excluding future forecast data)
    if cutoff:
        cur.execute(
            "SELECT timestamp, temperature, precipitation, weather_code FROM weather_data WHERE timestamp >= %s AND timestamp <= NOW() ORDER BY timestamp",
            (cutoff,)
        )
    else:
        cur.execute("SELECT timestamp, temperature, precipitation, weather_code FROM weather_data WHERE timestamp <= NOW() ORDER BY timestamp")
    
    weather_data = []
    for row in cur.fetchall():
        utc_time = row['timestamp'].replace(tzinfo=pytz.UTC)
        mt_time = utc_time.astimezone(MOUNTAIN_TZ)
        weather_data.append({
            'timestamp': mt_time.strftime('%Y-%m-%d %H:%M:%S'),
            'temperature': row['temperature'],
            'precipitation': row['precipitation'],
            'weather_code': row['weather_code']
        })
    
    # Get latest speed test regardless of time range
    cur.execute("SELECT timestamp, download, upload FROM speed_tests ORDER BY timestamp DESC LIMIT 1")
    latest_speed_row = cur.fetchone()
    latest_speed = None
    if latest_speed_row:
        utc_time = latest_speed_row['timestamp'].replace(tzinfo=pytz.UTC)
        mt_time = utc_time.astimezone(MOUNTAIN_TZ)
        latest_speed = {
            'timestamp': mt_time.strftime('%Y-%m-%d %H:%M:%S'),
            'download': latest_speed_row['download'],
            'upload': latest_speed_row['upload']
        }
    
    # Calculate summary and hourly stats in SQL (avoids fetching all rows)
    summary = get_summary_from_db(cur, cutoff)
    hourly_avg = get_hourly_avg_from_db(cur, cutoff)

    conn.close()
    
    # Decimate data server-side if needed
    if len(tests) > 6000:
        tests = decimate_tests(tests, target=2000)
    
    return jsonify({
        'tests': tests,
        'speed_tests': speed_tests_array,
        'summary': summary,
        'hourly_avg': hourly_avg,
        'top_channels': top_channels,
        'restarts': restarts,
        'uptime_seconds': uptime_seconds,
        'uptime_timestamp': uptime_timestamp,
        'weather': weather_data,
        'latest_speed': latest_speed,
        'node_id': os.getenv('NODE_ID', 'Unknown'),
        'ping_target': os.getenv('PING_TARGET', '8.8.8.8'),
        'ping_target_name': os.getenv('PING_TARGET_NAME', 'Google DNS'),
        'cmts_target': os.getenv('CMTS_TARGET')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
