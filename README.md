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
  - Green: Good quality (>70%)
  - Yellow: Poor quality (40-70%)
  - Red: Bad/Dropped connection
- **Link Type Identification**: Visual distinction between link types
  - RF Links: Green, standard width
  - DTD Links: Blue, thick (keeps paired nodes close)
  - Xlink: Purple
  - Tunnel/Wireguard: Gray, dashed
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
| `POLL_INTERVAL` | `30` | Seconds between scans |
| `MAX_DEPTH` | `5` | Maximum hops from starting node |
| `LINK_TIMEOUT` | `300` | Seconds before marking link as dropped |
| `SHOW_TUNNELS` | `False` | Show tunnel/wireguard links |
| `QUALITY_GOOD` | `70` | Threshold for "good" quality |
| `QUALITY_POOR` | `40` | Threshold for "poor" quality |

## Project Structure

```
AREDN_netmonitor/
├── app.py              # Flask application entry point
├── config.py           # Configuration settings
├── database.py         # SQLite database operations
├── scanner.py          # Network discovery logic
├── requirements.txt    # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css   # Application styles
│   └── js/
│       └── network.js  # vis.js network visualization
└── templates/
    └── index.html      # Main page template
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
