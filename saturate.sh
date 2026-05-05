#!/bin/bash
# Saturates your connection with parallel downloads to help demonstrate
# network issues to ISP tech. Press Ctrl+C to stop.

export LC_ALL=C

STREAMS=${1:-8}
echo "🔥 Saturating connection with $STREAMS parallel streams..."
echo "   Press Ctrl+C to stop"
echo ""

cleanup() {
    echo -e "\n🛑 Stopping..."
    kill $(jobs -p) 2>/dev/null
    wait 2>/dev/null
    echo "Done."
    exit 0
}
trap cleanup INT TERM

URLS=(
    "https://ash-speed.hetzner.com/100MB.bin"
    "https://ash-speed.hetzner.com/100MB.bin"
    "http://speedtest.newark.linode.com/100MB-newark.bin"
    "http://speedtest.newark.linode.com/100MB-newark.bin"
    "https://proof.ovh.net/files/100Mb.dat"
    "https://proof.ovh.net/files/100Mb.dat"
    "https://ash-speed.hetzner.com/100MB.bin"
    "http://speedtest.newark.linode.com/100MB-newark.bin"
)

for i in $(seq 1 $STREAMS); do
    url="${URLS[$(( (i-1) % ${#URLS[@]} ))]}"
    (
        while true; do
            result=$(curl -w "%{size_download} %{time_total}" -s -o /dev/null "$url")
            bytes=$(echo "$result" | awk '{print $1}')
            time=$(echo "$result" | awk '{print $2}')
            mbps=$(awk "BEGIN {if ($time > 0) printf \"%.1f\", $bytes * 8 / $time / 1000000; else print \"0.0\"}")
            printf "[Stream %02d] %7s Mbps  (%s)\n" "$i" "$mbps" "$(basename "$url")"
        done
    ) &
done

sleep 1
echo "⏳ Running... watch your dashboard for packet loss"
wait
