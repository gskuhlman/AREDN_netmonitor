# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AREDN Network Monitor - a real-time Flask web application for monitoring AREDN (Amateur Radio Emergency Data Network) mesh networks. Uses WebSocket (Socket.IO) for live updates and vis.js for interactive network visualization.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
# Server starts at http://localhost:5000

# No test suite or linting currently configured
```

## Architecture

### Backend Components

- **app.py**: Flask entry point with REST routes, WebSocket handlers, and APScheduler setup. Handles `/api/*` endpoints and Socket.IO events.
- **scanner.py**: BFS network discovery starting from seed node. Fetches `sysinfo.json` from each AREDN node, extracts node metadata and link quality metrics. Stops at supernode boundaries.
- **database.py**: SQLite operations for nodes, links, services, events, settings, and link_history tables.
- **rf_stats.py**: Ping tests and iperf3 throughput benchmarks with queue-based processing.
- **config.py**: Central configuration (poll intervals, timeouts, quality thresholds, RF stats settings).

### Frontend Components

- **templates/index.html**: Single-page app with Network and RF Stats tabs
- **static/js/network.js**: vis.js graph initialization, WebSocket message handling, node position persistence to localStorage
- **static/js/rf-stats.js**: Chart.js graphs for quality, SNR, latency, and throughput metrics
- **static/css/style.css**: Responsive layout with color-coded nodes/links

### Data Flow

1. APScheduler triggers `scheduled_scan()` at configured interval
2. `scanner.discover_network()` performs BFS traversal from seed node
3. Node/link data saved to SQLite, events logged
4. `socketio.emit('scan_complete', ...)` broadcasts to all connected clients
5. Frontend updates vis.js graph and event log

### Key Patterns

- **Producer-Consumer**: Scanner produces network state, SocketIO broadcasts to all clients
- **Event-Driven**: Node/link changes logged to events table and broadcast in real-time
- **Timeout-Based Status**: Links marked "dropped" after 5 min (300s), removed after 10 min (600s)

### Database Tables

- `nodes`: Network devices with IP, model, firmware, geolocation, RF info
- `links`: Connections with quality/SNR metrics, status (good/dropped/removed)
- `services`: Services per node (Phone, MeshChat, etc.)
- `events`: Event log with timestamp, type, severity
- `link_history`: Time-series RF metrics for trending
- `settings`: Runtime configuration (key-value)

### REST API

- `GET /api/network` - Graph data for vis.js
- `GET /api/nodes`, `/api/links` - Node/link lists
- `GET /api/node/<name>` - Node details with services
- `POST /api/scan` - Trigger immediate scan
- `GET/POST /api/settings` - Configuration
- `GET /api/events` - Event log (supports `limit`, `offset` params)
- `GET /api/rf-stats/*` - RF statistics and history

### WebSocket Events

Server emits: `scan_started`, `scan_complete`, `network_update`, `link_dropped`, `node_inactive`, `new_event`
Client emits: `request_scan`, `request_network`, `request_events`

## Configuration

Key settings in `config.py`:
- `STARTING_NODE`: Seed URL for discovery (e.g., `http://localnode.local.mesh/cgi-bin/sysinfo.json`)
- `POLL_INTERVAL`: Scan frequency (default 30s)
- `MAX_DEPTH`: Max hops from seed (default 5)
- `LINK_TIMEOUT`/`LINK_REMOVE_AFTER`: Dropped/removed thresholds (300s/600s)
- `RF_STATS_ENABLED`: Enable ping/iperf collection

Settings can be overridden at runtime via `/api/settings` and persist to database.

## Link Visualization

### Link Quality (Color)
- Green: >85% quality (good)
- Yellow: 50-85% quality (poor)
- Red: <50% quality (bad/dropped)
- Blue: DTD links (always blue, wired connections)

### Link Type (Line Pattern)
- RF: Solid line, normal width
- DTD: Thick solid blue line (wired connection)
- Tunnel (legacy): Dashed line
- Wireguard: Dotted line
- Xlink: Dash-dot pattern

### Node Colors
- Blue: Normal node
- Orange: Firmware mismatch
- Purple: Supernode
- Gray: Dropped/offline
