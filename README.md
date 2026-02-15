# Network Monitor

Real-time network monitoring dashboard for cable modem connections. Tracks latency, packet loss, modem signal quality, and per-channel codeword errors.

**Compatibility**: May work with Comcast Xfinity and other cable ISPs using DOCSIS modems with web interfaces.

## Features

- **Ping Monitoring**: Continuous ping tests to Google DNS and CMTS (first hop)
- **Speed Tests**: Periodic bandwidth testing (every 5 minutes)
- **Modem Signals**: DS/US power levels, SNR tracking with 24-hour averages
- **Channel Analysis**: Per-channel codeword error tracking
- **Modem Restart Detection**: Automatic detection via uptime monitoring
- **Smart Decimation**: Efficient rendering of large datasets while preserving outliers
- **Hourly Heatmap**: Visualize packet loss patterns by hour of day
- **Auto-refresh Dashboard**: Real-time updates with configurable time ranges

## Quick Start

### Prerequisites

- Docker and Docker Compose
- PostgreSQL database (external or existing container)
- Cable modem with web interface access

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd network-monitor
```

2. **Configure environment variables**

Copy the example file and edit with your settings:
```bash
cp .env.example .env
nano .env
```

Required environment variables:

```bash
# Router/Modem Configuration
ROUTER_URL=http://192.168.1.1          # Your cable modem's web interface URL
ROUTER_USERNAME=admin                   # Modem admin username
ROUTER_PASSWORD=your_password           # Modem admin password

# Database Configuration (External PostgreSQL)
DB_HOST=localhost                       # PostgreSQL host (use localhost if on same machine)
DB_PORT=5432                           # PostgreSQL port
DB_NAME=network_monitor                # Database name
DB_USER=postgres                       # Database user
DB_PASSWORD=your_db_password           # Database password

# Monitoring Configuration
NODE_ID=MyNode                         # Identifier for this monitoring node
PING_TARGET=8.8.8.8                   # Target for ping tests (default: Google DNS)
PING_TARGET_NAME=Google DNS           # Display name for ping target
CMTS_TARGET=                          # REQUIRED: Your ISP's CMTS/first hop IP address (find with: traceroute 8.8.8.8)
```

3. **Set up PostgreSQL database**

If you don't have an existing PostgreSQL database, create one:

```bash
# Connect to your PostgreSQL instance
psql -U postgres -h localhost

# Create database
CREATE DATABASE network_monitor;

# Import schema
\c network_monitor
\i schema.sql
```

Or if using Docker for PostgreSQL:
```bash
docker exec -i your-postgres-container psql -U postgres -d network_monitor < schema.sql
```

4. **Build and start the container**

```bash
docker compose up -d --build
```

5. **Verify it's running**

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f monitor

# Test the dashboard
curl http://localhost:5000/network.html
```

## Accessing the Dashboard

The dashboard is available at:
- **Local**: http://localhost:5000/network.html
- **API**: http://localhost:5000/api/network/data

### Reverse Proxy Setup (Caddy)

To expose the dashboard publicly, add to your Caddyfile:

```
yourdomain.com {
    reverse_proxy /network.html 192.168.1.100:5000
    reverse_proxy /api/network/* 192.168.1.100:5000
}
```

Replace `192.168.1.100` with your Docker host's IP address.

Reload Caddy:
```bash
sudo systemctl reload caddy
```

## Management

### View Logs
```bash
docker compose logs -f monitor
```

### Restart Container
```bash
docker compose restart
```

### Stop Container
```bash
docker compose down
```

### Rebuild After Code Changes
```bash
docker compose up -d --build
```

### Update Configuration
1. Edit `.env` file
2. Restart container: `docker compose restart`

## Architecture

- **network_monitor.py**: Background service that scrapes modem data and runs ping tests every 10 seconds
- **network_api.py**: Flask API serving data and dashboard HTML
- **dashboard.html**: Interactive web dashboard with Chart.js visualizations
- **PostgreSQL**: External database for time-series data storage

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ROUTER_URL` | Yes | - | Cable modem web interface URL |
| `ROUTER_USERNAME` | Yes | - | Modem admin username |
| `ROUTER_PASSWORD` | Yes | - | Modem admin password |
| `DB_HOST` | Yes | - | PostgreSQL host address |
| `DB_PORT` | No | 5432 | PostgreSQL port |
| `DB_NAME` | Yes | - | Database name |
| `DB_USER` | Yes | - | Database username |
| `DB_PASSWORD` | Yes | - | Database password |
| `NODE_ID` | No | Unknown | Identifier for this monitoring node |
| `PING_TARGET` | No | 8.8.8.8 | Target IP for ping tests |
| `PING_TARGET_NAME` | No | Google DNS | Display name for ping target |
| `CMTS_TARGET` | Yes | - | ISP's CMTS/first hop IP address |

## Troubleshooting

### Container won't start
```bash
docker compose logs monitor
```

### Database connection issues
- Verify PostgreSQL is running and accessible
- Check `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` in `.env`
- Ensure database `network_monitor` exists
- Verify schema is imported: `psql -U postgres -d network_monitor -c "\dt"`

### Ping tests failing
- Container needs host network access to ping external IPs
- Verify `PING_TARGET` and `CMTS_TARGET` are correct
- Check logs: `docker compose logs -f monitor | grep -i ping`

### Speed tests returning 0/0
- Speedtest-cli requires license acceptance (handled automatically)
- Check logs: `docker compose logs -f monitor | grep -i speed`
- Verify internet connectivity from container

### Modem scraping fails
- Verify `ROUTER_URL`, `ROUTER_USERNAME`, `ROUTER_PASSWORD` are correct
- Check if modem web interface is accessible: `curl -u user:pass http://192.168.1.1`
- Some modems may have different page structures

## Data Retention

The system stores all historical data indefinitely. For long-term deployments, consider implementing data retention policies:

```sql
-- Example: Delete data older than 90 days
DELETE FROM ping_tests WHERE timestamp < NOW() - INTERVAL '90 days';
DELETE FROM cmts_tests WHERE timestamp < NOW() - INTERVAL '90 days';
DELETE FROM speed_tests WHERE timestamp < NOW() - INTERVAL '90 days';
DELETE FROM modem_signals WHERE timestamp < NOW() - INTERVAL '90 days';
DELETE FROM channel_codewords WHERE timestamp < NOW() - INTERVAL '90 days';
```

## License

MIT License - See LICENSE file for details
