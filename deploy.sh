#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DEPLOY_PATH="${DASHBOARD_DEPLOY_PATH:-/var/www/html/network.html}"

echo "Deploying network monitor dashboard..."

# Copy dashboard to deployment location
cp network.html "$DEPLOY_PATH"

echo "✓ Dashboard deployed to $DEPLOY_PATH"

# Restart services if they're running
if systemctl is-active --quiet network-monitor; then
    echo "Restarting network-monitor service..."
    sudo systemctl restart network-monitor
    echo "✓ network-monitor restarted"
fi

if systemctl is-active --quiet network-api; then
    echo "Restarting network-api service..."
    sudo systemctl restart network-api
    echo "✓ network-api restarted"
fi

echo "Deployment complete!"
