"""
AREDN Network Monitor - Flask Application
Main entry point for the web application
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import atexit
import os
from datetime import datetime

import config
import database
import scanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'aredn-monitor-secret-key'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Initialize scheduler
scheduler = BackgroundScheduler()

# Track scan state
scan_state = {
    'is_scanning': False,
    'last_scan': None,
    'last_result': None
}


def scheduled_scan():
    """Background task to scan the network"""
    global scan_state

    if scan_state['is_scanning']:
        logger.warning("Scan already in progress, skipping")
        return

    scan_state['is_scanning'] = True

    # Notify clients that scan is starting
    socketio.emit('scan_started', {'timestamp': datetime.now().isoformat()})

    try:
        result = scanner.run_scan()
        scan_state['last_scan'] = result['timestamp']
        scan_state['last_result'] = result

        # Emit notifications for dropped links
        for link in result.get('dropped_links', []):
            socketio.emit('link_dropped', {
                'source': link['source'],
                'target': link['target'],
                'type': link['type']
            })

        # Emit notifications for inactive nodes
        for node in result.get('inactive_nodes', []):
            socketio.emit('node_inactive', {
                'node': node['name'],
                'ip': node.get('ip')
            })

        # Emit all events from this scan for real-time log updates
        for event in result.get('events', []):
            socketio.emit('new_event', event)

        # Get updated network data
        network_data = database.get_network_graph_data()

        # Notify clients with updated data
        socketio.emit('scan_complete', {
            'result': result,
            'network': network_data
        })

    except Exception as e:
        logger.error(f"Scan error: {e}")
        socketio.emit('scan_error', {'error': str(e)})

    finally:
        scan_state['is_scanning'] = False


# ============ Web Routes ============

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


# ============ API Routes ============

@app.route('/api/nodes')
def api_get_nodes():
    """Get all nodes"""
    nodes = database.get_all_nodes()
    return jsonify(nodes)


@app.route('/api/nodes/active')
def api_get_active_nodes():
    """Get active nodes only"""
    nodes = database.get_active_nodes()
    return jsonify(nodes)


@app.route('/api/node/<name>')
def api_get_node(name):
    """Get a specific node with its services"""
    node = database.get_node(name.lower())
    if not node:
        return jsonify({'error': 'Node not found'}), 404

    services = database.get_node_services(name.lower())
    links = database.get_node_links(name.lower())

    return jsonify({
        'node': node,
        'services': services,
        'links': links
    })


@app.route('/api/links')
def api_get_links():
    """Get all links"""
    links = database.get_all_links()
    return jsonify(links)


@app.route('/api/links/active')
def api_get_active_links():
    """Get active links only"""
    links = database.get_active_links()
    return jsonify(links)


@app.route('/api/network')
def api_get_network():
    """Get network graph data for vis.js"""
    data = database.get_network_graph_data()
    return jsonify(data)


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """Get current settings"""
    settings = database.get_all_settings()

    # Add defaults if not set
    if 'starting_node' not in settings:
        settings['starting_node'] = config.STARTING_NODE
    if 'show_tunnels' not in settings:
        settings['show_tunnels'] = 'true' if config.SHOW_TUNNELS else 'false'
    if 'max_depth' not in settings:
        settings['max_depth'] = config.MAX_DEPTH
    if 'auto_scan' not in settings:
        settings['auto_scan'] = 'true'
    if 'poll_interval' not in settings:
        settings['poll_interval'] = config.POLL_INTERVAL
    else:
        settings['poll_interval'] = int(settings['poll_interval'])

    settings['link_timeout'] = config.LINK_TIMEOUT
    settings['quality_good'] = config.QUALITY_GOOD
    settings['quality_poor'] = config.QUALITY_POOR

    return jsonify(settings)


@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    """Update settings"""
    data = request.get_json()

    if 'starting_node' in data:
        scanner.set_starting_node_url(data['starting_node'])

    if 'show_tunnels' in data:
        database.set_setting('show_tunnels', 'true' if data['show_tunnels'] else 'false')
        logger.info(f"Show tunnels updated to: {data['show_tunnels']}")

    if 'max_depth' in data:
        max_depth = max(1, min(20, int(data['max_depth'])))  # Clamp between 1-20
        database.set_setting('max_depth', str(max_depth))
        logger.info(f"Max depth updated to: {max_depth}")

    if 'auto_scan' in data:
        auto_scan = 'true' if data['auto_scan'] else 'false'
        database.set_setting('auto_scan', auto_scan)
        logger.info(f"Auto scan updated to: {auto_scan}")

        # Update scheduler
        if data['auto_scan']:
            if scheduler.get_job('network_scan') is None:
                poll_interval = int(database.get_setting('poll_interval', config.POLL_INTERVAL))
                scheduler.add_job(
                    scheduled_scan,
                    'interval',
                    seconds=poll_interval,
                    id='network_scan',
                    replace_existing=True
                )
                logger.info(f"Scheduler resumed with {poll_interval}s interval")
        else:
            job = scheduler.get_job('network_scan')
            if job:
                scheduler.remove_job('network_scan')
                logger.info("Scheduler paused")

    if 'poll_interval' in data:
        poll_interval = max(10, min(600, int(data['poll_interval'])))  # Clamp between 10-600
        database.set_setting('poll_interval', str(poll_interval))
        logger.info(f"Poll interval updated to: {poll_interval}s")

        # Reschedule if auto_scan is enabled
        auto_scan = database.get_setting('auto_scan', 'true')
        if auto_scan == 'true':
            scheduler.add_job(
                scheduled_scan,
                'interval',
                seconds=poll_interval,
                id='network_scan',
                replace_existing=True
            )
            logger.info(f"Scheduler rescheduled with {poll_interval}s interval")

    return jsonify({'success': True, 'settings': database.get_all_settings()})


@app.route('/api/scan', methods=['POST'])
def api_trigger_scan():
    """Trigger an immediate scan"""
    if scan_state['is_scanning']:
        return jsonify({'error': 'Scan already in progress'}), 409

    # Run scan in background
    socketio.start_background_task(scheduled_scan)

    return jsonify({'success': True, 'message': 'Scan started'})


@app.route('/api/status')
def api_get_status():
    """Get current scan status"""
    return jsonify({
        'is_scanning': scan_state['is_scanning'],
        'last_scan': scan_state['last_scan'],
        'last_result': scan_state['last_result'],
        'node_count': len(database.get_active_nodes()),
        'link_count': len(database.get_active_links())
    })


@app.route('/api/events')
def api_get_events():
    """Get event log"""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    events = database.get_events(limit=limit, offset=offset)
    return jsonify(events)


@app.route('/api/events/clear', methods=['POST'])
def api_clear_events():
    """Clear old events"""
    days = request.args.get('days', 30, type=int)
    count = database.clear_old_events(days=days)
    return jsonify({'success': True, 'cleared': count})


# ============ SocketIO Events ============

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")

    # Send current state
    emit('status', {
        'is_scanning': scan_state['is_scanning'],
        'last_scan': scan_state['last_scan']
    })

    # Send current network data
    emit('network_update', database.get_network_graph_data())


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


@socketio.on('request_scan')
def handle_request_scan():
    """Handle scan request from client"""
    if not scan_state['is_scanning']:
        socketio.start_background_task(scheduled_scan)
        emit('scan_acknowledged', {'message': 'Scan started'})
    else:
        emit('scan_acknowledged', {'message': 'Scan already in progress'})


@socketio.on('request_network')
def handle_request_network():
    """Handle request for current network data"""
    emit('network_update', database.get_network_graph_data())


@socketio.on('request_events')
def handle_request_events(data=None):
    """Handle request for event log"""
    limit = 100
    if data and 'limit' in data:
        limit = data['limit']
    events = database.get_events(limit=limit)
    emit('events_update', events)


# ============ Startup ============

def start_scheduler():
    """Start the background scheduler"""
    scheduler.add_job(
        scheduled_scan,
        'interval',
        seconds=config.POLL_INTERVAL,
        id='network_scan',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started with {config.POLL_INTERVAL}s interval")


# Ensure scheduler shuts down on exit
atexit.register(lambda: scheduler.shutdown(wait=False))


if __name__ == '__main__':
    logger.info("Starting AREDN Network Monitor")

    # Initialize database
    database.init_db()

    # Only start scheduler in the main process (not the reloader)
    # When debug=True, Flask uses a reloader that spawns a child process
    # WERKZEUG_RUN_MAIN is set to 'true' in the child process
    if not config.DEBUG or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Start scheduler
        start_scheduler()

        # Run initial scan
        logger.info("Running initial scan...")
        socketio.start_background_task(scheduled_scan)

    # Start server
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=config.DEBUG
    )
