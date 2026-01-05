"""
Network Scanner for AREDN Network Monitor
Handles node discovery and polling
"""

import requests
import logging
from datetime import datetime
from urllib.parse import urlparse
import config
import database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_sysinfo_url(ip_or_hostname):
    """Build the sysinfo.json URL for a node"""
    # Remove any existing path/scheme
    host = ip_or_hostname.replace('http://', '').replace('https://', '').split('/')[0]
    return f"http://{host}/cgi-bin/sysinfo.json?lqm=1&hosts=1&services=1&services_local=1"


def fetch_node_info(url):
    """Fetch sysinfo.json from a node"""
    try:
        response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching {url}: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Invalid JSON from {url}: {e}")
        return None


def is_supernode(data):
    """Check if a node is a supernode"""
    if not data:
        return False

    node_details = data.get('node_details', {})

    # Check for supernode flag in node_details
    if node_details.get('supernode'):
        return True

    # Check for 'supernode' in node name or description
    node_name = data.get('node', '').lower()
    description = node_details.get('description', '').lower()

    if 'supernode' in node_name or 'supernode' in description:
        return True

    return False


def process_node_data(data):
    """Process and save node data from sysinfo.json response"""
    if not data:
        return None, []

    node_name = data.get('node', '').lower()
    if not node_name:
        return None, []

    events = []

    # Extract node details
    node_details = data.get('node_details', {})
    description = node_details.get('description', '')
    model = node_details.get('model', '')
    firmware = node_details.get('firmware_version', '')

    # Check if supernode
    supernode = is_supernode(data)

    lat = None
    lon = None
    try:
        lat = float(data.get('lat', 0)) or None
        lon = float(data.get('lon', 0)) or None
    except (ValueError, TypeError):
        pass

    # Extract RF information
    meshrf = data.get('meshrf', {})
    rf_frequency = meshrf.get('freq', '')
    rf_channel = meshrf.get('channel', '')

    # Find the main IP from interfaces
    ip = None
    for iface in data.get('interfaces', []):
        if iface.get('name') == 'br-lan' and iface.get('ip'):
            ip = iface['ip']
            break

    # Check if node exists and track changes
    existing_node = database.get_node(node_name)

    if existing_node is None:
        # New node discovered
        events.append({
            'type': database.EVENT_NODE_DISCOVERED,
            'node': node_name,
            'details': f"Model: {model}, IP: {ip}",
            'severity': 'info'
        })
        logger.info(f"New node discovered: {node_name}")
    else:
        # Check if node was previously inactive (came back online)
        if not existing_node.get('is_active'):
            events.append({
                'type': database.EVENT_NODE_ONLINE,
                'node': node_name,
                'details': f"Node back online",
                'severity': 'info'
            })
            logger.info(f"Node back online: {node_name}")

        # Check for frequency change (only log if change is >= 1 MHz)
        old_freq = existing_node.get('rf_frequency', '')
        if old_freq and rf_frequency and old_freq != rf_frequency:
            try:
                old_freq_val = float(old_freq)
                new_freq_val = float(rf_frequency)
                freq_diff = abs(new_freq_val - old_freq_val)
                if freq_diff >= 1.0:  # Only log changes >= 1 MHz
                    events.append({
                        'type': database.EVENT_FREQUENCY_CHANGE,
                        'node': node_name,
                        'details': f"Frequency changed: {old_freq} MHz -> {rf_frequency} MHz",
                        'severity': 'warning'
                    })
                    logger.info(f"Frequency change on {node_name}: {old_freq} -> {rf_frequency}")
            except (ValueError, TypeError):
                pass  # Ignore if frequencies aren't valid numbers

    # Upsert the node
    database.upsert_node(
        name=node_name,
        ip=ip,
        description=description,
        model=model,
        firmware_version=firmware,
        lat=lat,
        lon=lon,
        rf_frequency=rf_frequency,
        rf_channel=rf_channel,
        is_supernode=supernode
    )

    # Process services_local (services provided by this node)
    database.clear_node_services(node_name)
    for service in data.get('services_local', []):
        database.upsert_service(
            node_name=node_name,
            name=service.get('name', ''),
            protocol=service.get('protocol', 'tcp'),
            link=service.get('link', ''),
            ip=ip
        )

    return node_name, events


def process_links(data, source_node):
    """Process LQM tracker data to extract links and discover connected nodes"""
    if not data or not source_node:
        return [], []

    lqm_info = data.get('lqm', {}).get('info', {})
    trackers = lqm_info.get('trackers', {})
    discovered_nodes = []
    events = []

    # Handle case where trackers might be a list instead of dict
    if isinstance(trackers, list):
        # Convert list to dict using index as key
        trackers = {str(i): t for i, t in enumerate(trackers)}
    elif not isinstance(trackers, dict):
        logger.warning(f"Unexpected trackers type: {type(trackers)}")
        return [], []

    # Check if tunnels should be shown (from settings or config)
    show_tunnels = database.get_setting('show_tunnels', 'false').lower() == 'true' or config.SHOW_TUNNELS

    for mac, tracker in trackers.items():
        link_type = tracker.get('type', '')
        hostname = tracker.get('hostname', '').lower()

        if not hostname:
            continue

        canonical_ip = tracker.get('canonical_ip')
        quality = tracker.get('quality', 0)
        snr = tracker.get('snr')
        distance = tracker.get('distance')

        # Ensure quality is an integer
        try:
            quality = int(quality)
        except (ValueError, TypeError):
            quality = 0

        # Always save RF and DTD links, optionally save tunnel links
        is_tunnel = link_type.upper() in ('WIREGUARD', 'TUN', 'TUNNEL', 'VTUN', 'WG')
        if not is_tunnel or show_tunnels:
            # Check if this is a new link or restored link
            existing_link = database.get_link(source_node, hostname)

            if existing_link is None:
                # New link
                events.append({
                    'type': database.EVENT_LINK_NEW,
                    'node': source_node,
                    'details': f"New {link_type} link to {hostname} (Q:{quality}%)",
                    'severity': 'info'
                })
                logger.info(f"New link: {source_node} <-> {hostname} ({link_type})")
            elif existing_link.get('status') == 'dropped':
                # Link restored
                events.append({
                    'type': database.EVENT_LINK_RESTORED,
                    'node': source_node,
                    'details': f"{link_type} link to {hostname} restored (Q:{quality}%)",
                    'severity': 'info'
                })
                logger.info(f"Link restored: {source_node} <-> {hostname}")

            database.upsert_link(
                source_node=source_node,
                target_node=hostname,
                link_type=link_type,
                quality=quality,
                snr=snr,
                distance=distance
            )

        # ALWAYS add routable nodes to discovery queue (regardless of link type)
        # This ensures we discover all nodes even if connected only via tunnels
        if tracker.get('routable') and canonical_ip:
            discovered_nodes.append({
                'hostname': hostname,
                'ip': canonical_ip,
                'url': build_sysinfo_url(canonical_ip)
            })

    return discovered_nodes, events


def normalize_start_url(url):
    """Ensure the URL has the proper sysinfo.json path"""
    if not url:
        return config.STARTING_NODE

    # If it doesn't contain the sysinfo.json path, add it
    if '/cgi-bin/sysinfo.json' not in url:
        return build_sysinfo_url(url)

    return url


def discover_network(start_url=None, max_depth=None):
    """
    Discover the network starting from a node.
    Uses BFS traversal to find all connected nodes.
    Returns a dictionary with scan results.

    Args:
        start_url: Starting node URL
        max_depth: Maximum hops from starting node (default from settings/config)
    """
    if start_url is None:
        # Check for override in settings
        start_url = database.get_setting('starting_node', config.STARTING_NODE)

    if max_depth is None:
        # Get from settings or config
        max_depth = int(database.get_setting('max_depth', config.MAX_DEPTH))

    # Normalize the URL to ensure it has the proper path
    start_url = normalize_start_url(start_url)

    logger.info(f"Starting network discovery from {start_url} (max depth: {max_depth})")

    visited_urls = set()
    visited_nodes = set()
    # Queue now contains tuples of (url, depth)
    queue = [(start_url, 0)]
    nodes_found = 0
    links_found = 0
    errors = []
    max_depth_reached = 0
    all_events = []

    while queue:
        url, depth = queue.pop(0)

        # Normalize URL for comparison
        normalized = url.lower()
        if normalized in visited_urls:
            continue
        visited_urls.add(normalized)

        logger.info(f"Scanning (depth {depth}): {url}")

        # Fetch node data
        data = fetch_node_info(url)
        if not data:
            errors.append(f"Failed to fetch: {url}")
            continue

        # Process the node
        node_name, node_events = process_node_data(data)
        all_events.extend(node_events)

        if not node_name:
            errors.append(f"Invalid node data from: {url}")
            continue

        if node_name not in visited_nodes:
            visited_nodes.add(node_name)
            nodes_found += 1
            max_depth_reached = max(max_depth_reached, depth)

        # Check if this is a supernode - if so, don't traverse beyond it
        supernode = is_supernode(data)
        if supernode:
            logger.info(f"Found supernode: {node_name} - not traversing beyond")

        # Process links and get discovered nodes
        discovered, link_events = process_links(data, node_name)
        all_events.extend(link_events)
        links_found += len(discovered)

        # Add new nodes to queue only if:
        # 1. We haven't reached max depth
        # 2. This node is NOT a supernode (don't traverse past supernodes)
        if depth < max_depth and not supernode:
            for node_info in discovered:
                node_url = node_info['url']
                if node_url.lower() not in visited_urls:
                    queue.append((node_url, depth + 1))

    logger.info(f"Discovery complete: {nodes_found} nodes, {links_found} links, max depth reached: {max_depth_reached}")

    return {
        'nodes_found': nodes_found,
        'links_found': links_found,
        'nodes_visited': len(visited_nodes),
        'max_depth_reached': max_depth_reached,
        'errors': errors,
        'events': all_events,
        'timestamp': datetime.now().isoformat()
    }


def update_link_statuses():
    """Update link statuses based on timeouts, return details of changes"""
    # Get links that will be dropped before marking them
    dropped_links = database.get_links_to_drop(config.LINK_TIMEOUT)
    events = []

    # Log events for dropped links
    for link in dropped_links:
        events.append({
            'type': database.EVENT_LINK_DROPPED,
            'node': link['source'],
            'details': f"{link['type']} link to {link['target']} dropped",
            'severity': 'warning'
        })

    dropped = database.mark_stale_links_dropped(config.LINK_TIMEOUT)
    removed = database.remove_old_dropped_links(config.LINK_REMOVE_AFTER)

    if dropped > 0:
        logger.info(f"Marked {dropped} links as dropped")
    if removed > 0:
        logger.info(f"Removed {removed} old dropped links")

    return {
        'dropped': dropped,
        'removed': removed,
        'dropped_links': dropped_links,
        'events': events
    }


def update_node_statuses():
    """Update node statuses based on timeouts, return details of changes"""
    # Get nodes that will be marked inactive before marking them
    inactive_nodes = database.get_nodes_to_mark_inactive(config.LINK_TIMEOUT)
    events = []

    # Log events for nodes going offline
    for node in inactive_nodes:
        events.append({
            'type': database.EVENT_NODE_OFFLINE,
            'node': node['name'],
            'details': f"Node offline (IP: {node.get('ip', 'unknown')})",
            'severity': 'warning'
        })

    count = database.mark_stale_nodes_inactive(config.LINK_TIMEOUT)

    if count > 0:
        logger.info(f"Marked {count} nodes as inactive")

    return {
        'marked_inactive': count,
        'inactive_nodes': inactive_nodes,
        'events': events
    }


def run_scan():
    """
    Run a complete network scan.
    This is the main entry point for scheduled scans.
    """
    logger.info("Starting scheduled scan...")

    # Discover network
    result = discover_network()

    # Collect all events
    all_events = result.get('events', [])

    # Update link statuses
    link_status = update_link_statuses()
    result['dropped'] = link_status['dropped']
    result['removed'] = link_status['removed']
    result['dropped_links'] = link_status['dropped_links']
    all_events.extend(link_status.get('events', []))

    # Update node statuses
    node_status = update_node_statuses()
    result['inactive_nodes'] = node_status['inactive_nodes']
    all_events.extend(node_status.get('events', []))

    # Save all events to database
    for event in all_events:
        database.log_event(
            event_type=event['type'],
            node_name=event.get('node'),
            details=event.get('details'),
            severity=event.get('severity', 'info')
        )

    result['events'] = all_events

    logger.info(f"Scan complete: {result['nodes_found']} nodes, {result['links_found']} links, {len(all_events)} events")
    return result


def get_starting_node_url():
    """Get the current starting node URL"""
    return database.get_setting('starting_node', config.STARTING_NODE)


def set_starting_node_url(url):
    """Set the starting node URL"""
    database.set_setting('starting_node', url)
    logger.info(f"Starting node updated to: {url}")
