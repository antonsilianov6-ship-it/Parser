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
# ``CDP_PORT`` is the port the panel reaches from outside (docker network).
# Chromium 128+ silently ignores ``--remote-debugging-address=0.0.0.0`` and
# binds DevTools to 127.0.0.1 — so Chromium listens on the loopback-only
# ``CDP_LOOPBACK_PORT`` and we run a socat proxy that forwards public
# ``CDP_PORT`` -> 127.0.0.1:CDP_LOOPBACK_PORT.
CDP_PORT="${BROWSER_CDP_PORT:-9222}"
CDP_LOOPBACK_PORT="${BROWSER_CDP_LOOPBACK_PORT:-9221}"
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
# --remote-allow-origins=* is required for Chromium >=110: without it the
# DevTools endpoint rejects cross-host connections with "Host header is
# specified and is not an IP address or localhost." (the panel reaches CDP
# through the docker service name ``browser`` rather than 127.0.0.1).
# Stale Chromium profile lockfiles must be wiped before launch, otherwise
# the second-and-later container starts crash with
# "The profile appears to be in use by another Chromium process".
rm -f "$PROFILE_DIR/SingletonLock" "$PROFILE_DIR/SingletonCookie" "$PROFILE_DIR/SingletonSocket"
chromium \
  --no-first-run \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-features=UseOzonePlatform \
  --remote-debugging-port="$CDP_LOOPBACK_PORT" \
  --remote-allow-origins=* \
  --user-data-dir="$PROFILE_DIR" \
  --window-position=0,0 \
  --window-size=1280,800 \
  --start-maximized \
  about:blank &
CHROMIUM_PID=$!

# Bridge the loopback-only DevTools endpoint to the docker network so the
# panel container can reach Chromium. socat is a plain TCP forwarder so it
# preserves the Host header — the panel is expected to resolve the
# ``browser`` hostname to an IP before connecting (otherwise Chromium's
# "Host must be an IP or localhost" check fires).
socat TCP-LISTEN:"$CDP_PORT",fork,reuseaddr TCP:127.0.0.1:"$CDP_LOOPBACK_PORT" &
SOCAT_PID=$!

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
trap 'kill $CHROMIUM_PID $WEBSOCKIFY_PID $XVFB_PID $SOCAT_PID 2>/dev/null || true' TERM INT

# Block on chromium so the container exits when the browser dies.
wait "$CHROMIUM_PID"
