#!/usr/bin/env bash
# Boot order: Xvfb -> fluxbox -> chromium (with CDP) -> x11vnc -> websockify.
#
# The panel reaches Chromium via the CDP port (defaults to 9222) on
# the docker network. Browser users reach the same display via noVNC
# (defaults to 6080) — typically embedded in the panel UI as an
# iframe.
set -euo pipefail

DISPLAY="${DISPLAY:-:99}"
XVFB_WHD="${XVFB_WHD:-1280x800x24}"
VNC_PORT="${BROWSER_VNC_PORT:-5900}"
NOVNC_PORT="${BROWSER_NOVNC_PORT:-6080}"
CDP_PORT="${BROWSER_CDP_PORT:-9222}"
PROFILE_DIR="${BROWSER_PROFILE_DIR:-/data/profile}"

mkdir -p "$PROFILE_DIR"

# Background Xvfb on the configured display.
Xvfb "$DISPLAY" -screen 0 "$XVFB_WHD" -ac +extension RANDR &
XVFB_PID=$!

# Tiny window manager so chromium can resize properly.
fluxbox >/dev/null 2>&1 &

# Wait for Xvfb to be ready before spawning Chromium.
for _ in $(seq 1 30); do
  if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

# Chromium with CDP exposed on 0.0.0.0:CDP_PORT so the panel container
# can talk to it across the docker network. ``--no-sandbox`` is
# required because the container runs without user-namespace caps.
chromium \
  --no-first-run \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-features=UseOzonePlatform \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --window-position=0,0 \
  --window-size=1280,800 \
  --start-maximized \
  about:blank &
CHROMIUM_PID=$!

# x11vnc shares the X display over plain VNC; websockify wraps it
# in WebSockets and serves the noVNC HTML/JS bundle on $NOVNC_PORT.
x11vnc \
  -display "$DISPLAY" \
  -forever \
  -shared \
  -nopw \
  -quiet \
  -rfbport "$VNC_PORT" \
  -bg

websockify --web=/usr/share/novnc "$NOVNC_PORT" "localhost:$VNC_PORT" &
WEBSOCKIFY_PID=$!

# Forward signals to Chromium so docker stop terminates cleanly.
trap 'kill $CHROMIUM_PID $WEBSOCKIFY_PID $XVFB_PID 2>/dev/null || true' TERM INT

# Block on chromium so the container exits when the browser dies.
wait "$CHROMIUM_PID"
