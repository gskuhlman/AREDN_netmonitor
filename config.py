"""
AREDN Network Monitor Configuration
"""

# Starting node - can be overridden via web UI
STARTING_NODE = "http://localnode.local.mesh/cgi-bin/sysinfo.json?lqm=1&hosts=1&services=1&services_local=1"

# Polling interval in seconds (increase if scans take too long)
POLL_INTERVAL = 60

# Link timeout thresholds (in seconds)
LINK_TIMEOUT = 300  # 5 minutes - mark link as dropped
LINK_REMOVE_AFTER = 600  # 10 minutes - remove from display

# Link quality thresholds (0-100)
QUALITY_GOOD = 85  # Above this = green
QUALITY_POOR = 50  # Above this = yellow, below = red

# Connection types to show (filter out tunnels)
SHOW_TUNNELS = False

# Maximum hops from starting node during discovery
MAX_DEPTH = 5

# Database file path
DATABASE_PATH = "aredn_monitor.db"

# Request timeout for node queries (seconds)
REQUEST_TIMEOUT = 10

# Web server settings
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False  # Disabled - eventlet doesn't work well with werkzeug's reloader

# ============ RF Statistics Configuration ============

# Enable/disable RF stats collection
RF_STATS_ENABLED = True

# Ping test settings
PING_INTERVAL = 60      # Seconds between ping rounds
PING_COUNT = 5          # Number of pings per test
PING_TIMEOUT = 5        # Timeout per ping in seconds

# Iperf3 test settings
IPERF_INTERVAL = 300    # Seconds between iperf queue processing (5 minutes)
IPERF_DURATION = 5      # Duration of each iperf test in seconds
IPERF_BANDWIDTH = '10M' # Bandwidth limit to avoid overwhelming network

# Quality threshold for running iperf tests (skip if below this)
QUALITY_THRESHOLD_IPERF = 50

# History retention
HISTORY_RETENTION_HOURS = 24  # How long to keep historical data
