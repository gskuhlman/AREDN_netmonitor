"""
AREDN Network Monitor Configuration
"""

# Starting node - can be overridden via web UI
STARTING_NODE = "http://localnode.local.mesh/cgi-bin/sysinfo.json?lqm=1&hosts=1&services=1&services_local=1"

# Polling interval in seconds
POLL_INTERVAL = 30

# Link timeout thresholds (in seconds)
LINK_TIMEOUT = 300  # 5 minutes - mark link as dropped
LINK_REMOVE_AFTER = 600  # 10 minutes - remove from display

# Link quality thresholds (0-100)
QUALITY_GOOD = 70  # Above this = green
QUALITY_POOR = 40  # Above this = yellow, below = red

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
DEBUG = True
