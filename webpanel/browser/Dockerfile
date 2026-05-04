# Headed Chromium + Xvfb + x11vnc + noVNC service.
#
# Used by the panel to run a browser the end-user can drive over a
# noVNC iframe (currently only for the NotebookLM login flow). The
# panel connects to Chromium's CDP on :9222 to programmatically
# navigate the page and harvest the authenticated storage_state.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    XVFB_WHD=1280x800x24 \
    BROWSER_VNC_PORT=5900 \
    BROWSER_NOVNC_PORT=6080 \
    BROWSER_CDP_PORT=9222 \
    BROWSER_PROFILE_DIR=/data/profile

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-sandbox \
        xvfb \
        x11vnc \
        fluxbox \
        websockify \
        novnc \
        ca-certificates \
        fonts-liberation \
        fonts-noto-color-emoji \
        dumb-init \
        procps \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Convenience: expose noVNC at /vnc.html (websockify already serves
# the bundled novnc directory at the root path).
RUN ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Volume for the chromium profile so cookies / storage survive
# container restarts.
VOLUME ["/data"]

EXPOSE 6080 9222

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
