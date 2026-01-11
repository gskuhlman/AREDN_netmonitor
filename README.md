# AREDN Network Monitor

A real-time web application for monitoring and visualizing AREDN (Amateur Radio Emergency Data Network) mesh networks.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.0+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

- **Network Discovery**: Automatically discovers nodes via BFS traversal starting from a configurable seed node
- **Real-time Updates**: Live updates via WebSocket (Socket.IO) with 30-second polling interval
- **Interactive Visualization**: Drag-and-drop network graph using vis.js
- **Link Quality Monitoring**: Color-coded links showing connection quality
  - Green: Good quality (>85%)
  - Yellow: Poor quality (50-85%)
  - Red: Bad/Dropped connection (<50%)
  - Blue: DTD links (always blue, wired connections)
- **Link Type Identification**: Line patterns distinguish link types
  - RF Links: Solid line, normal width
  - DTD Links: Thick solid blue line
  - Tunnel (legacy): Dashed line
  - Wireguard: Dotted line
  - Xlink: Dash-dot pattern
- **Supernode Detection**: Purple highlighting for supernodes, discovery stops at supernode boundaries
- **Service Icons**: Shows available services (Phone, MeshChat, PBX, Camera, etc.) on node labels
- **Firmware Mismatch Detection**: Orange highlighting for nodes with mismatched firmware
- **Persistent Layout**: Node positions saved to browser localStorage
- **Configurable Settings**:
  - Starting node URL
  - Maximum discovery depth
  - Show/hide tunnel links

## Requirements

- Python 3.8+
- Access to an AREDN mesh network

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gskuhlman/AREDN_netmonitor.git
   cd AREDN_netmonitor
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the starting node in `config.py`:
   ```python
   STARTING_NODE = "http://your-node.local.mesh"
   ```

## Usage

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your browser to `http://localhost:5000`

3. The network will begin scanning automatically. You can also:
   - Click **Scan Now** to trigger an immediate scan
   - Click **Settings** to configure options
   - Click on any node to see detailed information
   - Drag nodes to rearrange the layout

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `STARTING_NODE` | `http://localnode.local.mesh` | Seed node for discovery |
| `POLL_INTERVAL` | `60` | Seconds between scans |
| `MAX_DEPTH` | `5` | Maximum hops from starting node |
| `LINK_TIMEOUT` | `300` | Seconds before marking link as dropped |
| `SHOW_TUNNELS` | `False` | Show tunnel/wireguard links |
| `QUALITY_GOOD` | `85` | Threshold for "good" quality (green) |
| `QUALITY_POOR` | `50` | Threshold for "poor" quality (yellow) |

## Deployment (Ubuntu Server)

### Quick Start

```bash
# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git iputils-ping iperf3

# Clone and setup
git clone https://github.com/gskuhlman/AREDN_netmonitor.git
cd AREDN_netmonitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure your starting node
nano config.py

# Run
python app.py
```

### Systemd Service (Recommended for Production)

1. Create a dedicated user:
   ```bash
   sudo useradd -r -s /bin/bash -m -d /home/aredn aredn
   ```

2. Setup as the aredn user:
   ```bash
   sudo -u aredn -i
   git clone https://github.com/gskuhlman/AREDN_netmonitor.git
   cd AREDN_netmonitor
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   nano config.py  # Set your starting node
   exit
   ```

3. Install and enable the service:
   ```bash
   sudo cp /home/aredn/AREDN_netmonitor/aredn-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now aredn-monitor
   ```

4. Manage the service:
   ```bash
   sudo systemctl status aredn-monitor   # Check status
   sudo journalctl -u aredn-monitor -f   # View logs
   sudo systemctl restart aredn-monitor  # Restart
   ```

### Using Your Own Username

Edit the service file before installing:
```bash
sudo nano /etc/systemd/system/aredn-monitor.service
# Replace 'aredn' with your username in User=, Group=, WorkingDirectory=, etc.
```

## Project Structure

```
AREDN_netmonitor/
├── app.py                  # Flask application entry point
├── config.py               # Configuration settings
├── database.py             # SQLite database operations
├── scanner.py              # Network discovery logic
├── rf_stats.py             # RF statistics (ping/iperf testing)
├── requirements.txt        # Python dependencies
├── aredn-monitor.service   # Systemd service file for deployment
├── static/
│   ├── css/
│   │   └── style.css       # Application styles
│   └── js/
│       ├── network.js      # vis.js network visualization
│       └── rf-stats.js     # RF statistics charts
└── templates/
    └── index.html          # Main page template
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/nodes` | GET | Get all nodes |
| `/api/nodes/active` | GET | Get active nodes only |
| `/api/node/<name>` | GET | Get node details with services |
| `/api/links` | GET | Get all links |
| `/api/links/active` | GET | Get active links only |
| `/api/network` | GET | Get full network graph data |
| `/api/settings` | GET/POST | Get or update settings |
| `/api/scan` | POST | Trigger immediate scan |
| `/api/status` | GET | Get current scan status |

## WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `scan_started` | Server → Client | Scan has begun |
| `scan_complete` | Server → Client | Scan finished with results |
| `network_update` | Server → Client | Updated network data |
| `link_dropped` | Server → Client | Link connection lost |
| `node_inactive` | Server → Client | Node went offline |
| `request_scan` | Client → Server | Request immediate scan |

## License

MIT License - feel free to use and modify for your amateur radio network monitoring needs.

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.

## Acknowledgments

- [AREDN Project](https://www.arednmesh.org/) for the mesh networking firmware
- [vis.js](https://visjs.org/) for the network visualization library
- [Flask](https://flask.palletsprojects.com/) and [Flask-SocketIO](https://flask-socketio.readthedocs.io/) for the web framework
