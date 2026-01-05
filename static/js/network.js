/**
 * AREDN Network Monitor - Network Visualization
 * Uses vis.js for interactive network graph
 */

// Global state
let network = null;
let nodesDataset = null;
let edgesDataset = null;
let socket = null;
let selectedNode = null;
let knownNodes = new Set();  // Track known nodes for drop detection
let isInitialLoad = true;    // Track if this is the first load (for physics)

// LocalStorage key for node positions
const POSITIONS_STORAGE_KEY = 'aredn_node_positions';

/**
 * Save node positions to localStorage
 */
function saveNodePositions() {
    const positions = {};
    nodesDataset.forEach(node => {
        if (node.x !== undefined && node.y !== undefined) {
            positions[node.id] = { x: node.x, y: node.y };
        }
    });
    localStorage.setItem(POSITIONS_STORAGE_KEY, JSON.stringify(positions));
}

/**
 * Load node positions from localStorage
 */
function loadNodePositions() {
    try {
        const stored = localStorage.getItem(POSITIONS_STORAGE_KEY);
        return stored ? JSON.parse(stored) : {};
    } catch (e) {
        console.error('Error loading positions:', e);
        return {};
    }
}

// DOM elements
const networkContainer = document.getElementById('network-container');
const sidePanel = document.getElementById('side-panel');
const settingsPanel = document.getElementById('settings-panel');
const logPanel = document.getElementById('log-panel');
const panelTitle = document.getElementById('panel-title');
const panelContent = document.getElementById('panel-content');
const logContent = document.getElementById('log-content');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

// Event log state
let eventLog = [];

// Node colors
const NODE_COLORS = {
    normal: {
        background: '#97C2FC',
        border: '#2B7CE9',
        highlight: { background: '#D2E5FF', border: '#2B7CE9' }
    },
    firmwareMismatch: {
        background: '#FFA500',
        border: '#FF6600',
        highlight: { background: '#FFD280', border: '#FF6600' }
    },
    supernode: {
        background: '#9B59B6',
        border: '#8E44AD',
        highlight: { background: '#D7BDE2', border: '#8E44AD' }
    }
};

// vis.js network options
const networkOptions = {
    nodes: {
        shape: 'dot',
        size: 25,
        font: {
            size: 12,
            color: '#333',
            multi: 'html'
        },
        borderWidth: 2,
        shadow: true,
        color: NODE_COLORS.normal,
        fixed: {
            x: false,
            y: false
        }
    },
    edges: {
        width: 2,
        smooth: {
            type: 'continuous',
            roundness: 0.5
        },
        shadow: true
    },
    physics: {
        enabled: true,
        barnesHut: {
            gravitationalConstant: -3000,
            centralGravity: 0.3,
            springLength: 200,
            springConstant: 0.04,
            damping: 0.09,
            avoidOverlap: 0.5
        },
        stabilization: {
            enabled: true,
            iterations: 150,
            updateInterval: 25
        }
    },
    interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragNodes: true
    }
};

/**
 * Initialize the network visualization
 */
function initNetwork() {
    nodesDataset = new vis.DataSet([]);
    edgesDataset = new vis.DataSet([]);

    const data = {
        nodes: nodesDataset,
        edges: edgesDataset
    };

    network = new vis.Network(networkContainer, data, networkOptions);

    // Event handlers
    network.on('click', handleNetworkClick);
    network.on('hoverNode', handleNodeHover);
    network.on('blurNode', handleNodeBlur);

    // Disable physics after initial stabilization and save positions
    network.on('stabilized', function() {
        if (isInitialLoad) {
            console.log('Initial layout stabilized, disabling physics');
            network.setOptions({ physics: { enabled: false } });
            isInitialLoad = false;

            // Save all positions after initial layout
            const allPositions = network.getPositions();
            for (const nodeId in allPositions) {
                nodesDataset.update({
                    id: nodeId,
                    x: allPositions[nodeId].x,
                    y: allPositions[nodeId].y
                });
            }
            saveNodePositions();
        }
    });

    // Save node position after drag
    network.on('dragEnd', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const positions = network.getPositions([nodeId]);

            nodesDataset.update({
                id: nodeId,
                x: positions[nodeId].x,
                y: positions[nodeId].y
            });

            // Save to localStorage
            saveNodePositions();
        }
    });
}

/**
 * Handle click on network
 */
function handleNetworkClick(params) {
    if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        showNodeDetails(nodeId);
    } else {
        hidePanel();
    }
}

/**
 * Handle node hover
 */
function handleNodeHover(params) {
    networkContainer.style.cursor = 'pointer';
}

/**
 * Handle node blur (mouse leave)
 */
function handleNodeBlur(params) {
    networkContainer.style.cursor = 'default';
}

/**
 * Show node details in side panel
 */
async function showNodeDetails(nodeId) {
    selectedNode = nodeId;
    panelTitle.textContent = nodeId;

    try {
        const response = await fetch(`/api/node/${encodeURIComponent(nodeId)}`);
        if (!response.ok) throw new Error('Node not found');

        const data = await response.json();
        renderNodeDetails(data);
        sidePanel.classList.remove('hidden');

    } catch (error) {
        console.error('Error fetching node details:', error);
        panelContent.innerHTML = '<p class="error">Failed to load node details</p>';
        sidePanel.classList.remove('hidden');
    }
}

/**
 * Render node details in panel
 */
function renderNodeDetails(data) {
    const node = data.node;
    const services = data.services || [];
    const links = data.links || [];

    let html = `
        <div class="node-info">
            <h3>Node Information</h3>
            <table class="info-table">
                <tr><td>Name:</td><td>${node.name}</td></tr>
                <tr><td>IP:</td><td>${node.ip || 'N/A'}</td></tr>
                <tr><td>Model:</td><td>${node.model || 'Unknown'}</td></tr>
                <tr><td>Firmware:</td><td>${node.firmware_version || 'Unknown'}</td></tr>
                <tr><td>Description:</td><td>${node.description || 'N/A'}</td></tr>
                <tr><td>First Seen:</td><td>${formatDate(node.first_seen)}</td></tr>
                <tr><td>Last Seen:</td><td>${formatDate(node.last_seen)}</td></tr>
            </table>
        </div>
    `;

    if (node.lat && node.lon) {
        html += `
            <div class="node-location">
                <h3>Location</h3>
                <p>Lat: ${node.lat}, Lon: ${node.lon}</p>
            </div>
        `;
    }

    if (links.length > 0) {
        html += `
            <div class="node-links">
                <h3>Links (${links.length})</h3>
                <table class="info-table">
                    <tr><th>Node</th><th>Type</th><th>Quality</th><th>SNR</th></tr>
        `;

        for (const link of links) {
            const otherNode = link.source_node === node.name ? link.target_node : link.source_node;
            const qualityClass = getQualityClass(link.quality);
            html += `
                <tr>
                    <td><a href="#" onclick="showNodeDetails('${otherNode}'); return false;">${otherNode}</a></td>
                    <td>${link.link_type}</td>
                    <td class="${qualityClass}">${link.quality}%</td>
                    <td>${link.snr || 'N/A'}</td>
                </tr>
            `;
        }

        html += '</table></div>';
    }

    if (services.length > 0) {
        html += `
            <div class="node-services">
                <h3>Services (${services.length})</h3>
                <ul class="services-list">
        `;

        for (const service of services) {
            const icon = getServiceIcon(service.name);
            const iconHtml = icon ? `<span class="service-icon">${icon}</span> ` : '';
            if (service.link) {
                html += `<li>${iconHtml}<a href="${service.link}" target="_blank">${service.name}</a></li>`;
            } else {
                html += `<li>${iconHtml}${service.name}</li>`;
            }
        }

        html += '</ul></div>';
    }

    panelContent.innerHTML = html;
}

/**
 * Get CSS class for quality value
 */
function getQualityClass(quality) {
    if (quality > 70) return 'quality-good';
    if (quality > 40) return 'quality-poor';
    return 'quality-bad';
}

/**
 * Get service icon based on service name
 */
function getServiceIcon(serviceName) {
    const name = serviceName.toLowerCase();

    // Phone/VOIP services
    if (name.includes('phone') || name.includes('voip') || name.includes('sip') ||
        name.includes('x1') || name.includes('extension') || name.includes('direct ip')) {
        return '&#128222;';  // Phone icon
    }

    // MeshChat services
    if (name.includes('meshchat') || name.includes('chat')) {
        return '&#128172;';  // Chat bubble icon
    }

    // PBX services
    if (name.includes('pbx') || name.includes('asterisk') || name.includes('freepbx')) {
        return '&#9742;';  // Telephone icon
    }

    // Camera/Video services
    if (name.includes('camera') || name.includes('cam') || name.includes('video') ||
        name.includes('stream') || name.includes('webcam')) {
        return '&#127909;';  // Camera icon
    }

    // Weather services
    if (name.includes('weather') || name.includes('weewx')) {
        return '&#127780;';  // Sun behind cloud
    }

    // Winlink services
    if (name.includes('winlink')) {
        return '&#9993;';  // Envelope icon
    }

    return null;  // No icon
}

/**
 * Format date string
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

/**
 * Show a toast notification
 */
function showToast(type, title, message, duration = 10000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        warning: '&#9888;',    // Warning triangle
        error: '&#10060;',     // Red X
        info: '&#8505;',       // Info symbol
        success: '&#10004;'    // Checkmark
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

/**
 * Hide the side panel
 */
function hidePanel() {
    sidePanel.classList.add('hidden');
    selectedNode = null;
}

/**
 * Update network with new data
 */
function updateNetwork(data) {
    if (!data || !data.nodes || !data.edges) return;

    const currentNodeIds = nodesDataset.getIds();
    const newNodeIds = data.nodes.map(n => n.id);
    const savedPositions = loadNodePositions();

    // Detect dropped nodes (were known but no longer in the network)
    const droppedNodes = [];
    for (const nodeId of knownNodes) {
        if (!newNodeIds.includes(nodeId)) {
            droppedNodes.push(nodeId);
        }
    }

    // Show alerts for dropped nodes
    for (const nodeId of droppedNodes) {
        showToast('warning', 'Node Dropped', `${nodeId} is no longer responding`);
        knownNodes.delete(nodeId);
    }

    // Detect new nodes
    const newNodes = [];
    for (const nodeId of newNodeIds) {
        if (!knownNodes.has(nodeId)) {
            newNodes.push(nodeId);
            knownNodes.add(nodeId);
        }
    }

    // Show info for new nodes (after initial load)
    if (currentNodeIds.length > 0) {
        for (const nodeId of newNodes) {
            showToast('success', 'Node Discovered', `${nodeId} joined the network`);
        }
    } else {
        // Initial load - just add all to known nodes
        for (const nodeId of newNodeIds) {
            knownNodes.add(nodeId);
        }
    }

    // Remove nodes that no longer exist
    const nodesToRemove = currentNodeIds.filter(id => !newNodeIds.includes(id));
    nodesDataset.remove(nodesToRemove);

    // Add or update nodes with appropriate coloring
    for (const node of data.nodes) {
        if (node.is_supernode) {
            node.color = NODE_COLORS.supernode;
            node.size = 35;  // Make supernodes larger
        } else if (node.firmware_mismatch) {
            node.color = NODE_COLORS.firmwareMismatch;
        } else {
            node.color = NODE_COLORS.normal;
        }

        if (currentNodeIds.includes(node.id)) {
            // Preserve existing position if node was manually positioned
            const existingNode = nodesDataset.get(node.id);
            if (existingNode && existingNode.x !== undefined) {
                node.x = existingNode.x;
                node.y = existingNode.y;
            }
            nodesDataset.update(node);
        } else {
            // New node - check if we have a saved position from localStorage
            if (savedPositions[node.id]) {
                node.x = savedPositions[node.id].x;
                node.y = savedPositions[node.id].y;
            }
            nodesDataset.add(node);
        }
    }

    // Update edges
    edgesDataset.clear();
    for (let i = 0; i < data.edges.length; i++) {
        const edge = data.edges[i];
        edge.id = `${edge.from}-${edge.to}`;
        edgesDataset.add(edge);
    }

    // Update footer stats
    updateStats(data.nodes.length, data.edges.length);
}

/**
 * Update statistics display
 */
function updateStats(nodeCount, linkCount, lastScan, maxDepth) {
    document.getElementById('footer-nodes').textContent = nodeCount;
    document.getElementById('footer-links').textContent = linkCount;
    document.getElementById('node-count').textContent = nodeCount;
    document.getElementById('link-count').textContent = linkCount;

    if (maxDepth !== undefined) {
        document.getElementById('footer-depth').textContent = maxDepth;
    }

    if (lastScan) {
        const formattedDate = formatDate(lastScan);
        document.getElementById('footer-last-scan').textContent = formattedDate;
        document.getElementById('last-scan').textContent = formattedDate;
    }
}

/**
 * Set connection status indicator
 */
function setStatus(connected, message) {
    statusIndicator.className = 'status-indicator ' + (connected ? 'connected' : 'disconnected');
    statusText.textContent = message || (connected ? 'Connected' : 'Disconnected');
}

/**
 * Initialize Socket.IO connection
 */
function initSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('Connected to server');
        setStatus(true, 'Connected');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        setStatus(false, 'Disconnected');
    });

    socket.on('status', (data) => {
        if (data.is_scanning) {
            setStatus(true, 'Scanning...');
        }
    });

    socket.on('network_update', (data) => {
        console.log('Received network update:', data);
        updateNetwork(data);
    });

    socket.on('scan_started', (data) => {
        setStatus(true, 'Scanning...');
        document.getElementById('scan-btn').disabled = true;
    });

    socket.on('scan_complete', (data) => {
        console.log('Scan complete:', data);
        setStatus(true, 'Connected');
        document.getElementById('scan-btn').disabled = false;

        if (data.network) {
            updateNetwork(data.network);
        }

        if (data.result && data.result.timestamp) {
            updateStats(
                data.result.nodes_found,
                data.result.links_found,
                data.result.timestamp,
                data.result.max_depth_reached
            );
        }
    });

    socket.on('scan_error', (data) => {
        console.error('Scan error:', data);
        setStatus(true, 'Scan failed');
        document.getElementById('scan-btn').disabled = false;
        showToast('error', 'Scan Failed', data.error || 'An error occurred during the network scan');
    });

    // Handle link drop notifications
    socket.on('link_dropped', (data) => {
        console.log('Link dropped:', data);
        showToast('warning', 'Link Dropped',
            `Connection lost between ${data.source} and ${data.target}`);
    });

    // Handle node inactive notifications
    socket.on('node_inactive', (data) => {
        console.log('Node inactive:', data);
        showToast('warning', 'Node Inactive',
            `${data.node} has gone offline`);
    });

    // Handle new events for real-time log updates
    socket.on('new_event', (data) => {
        console.log('New event:', data);
        addEventToLog(data);
    });
}

/**
 * Request a network scan
 */
function requestScan() {
    if (socket && socket.connected) {
        socket.emit('request_scan');
    } else {
        // Fallback to REST API
        fetch('/api/scan', { method: 'POST' })
            .then(response => response.json())
            .then(data => console.log('Scan triggered:', data))
            .catch(error => console.error('Scan error:', error));
    }
}

/**
 * Load and display settings
 */
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();

        document.getElementById('starting-node').value = settings.starting_node || '';
        document.getElementById('show-tunnels').checked = settings.show_tunnels === 'true';
        document.getElementById('max-depth').value = settings.max_depth || 5;

    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

/**
 * Save settings
 */
async function saveSettings() {
    const startingNode = document.getElementById('starting-node').value.trim();
    const showTunnels = document.getElementById('show-tunnels').checked;
    const maxDepth = parseInt(document.getElementById('max-depth').value) || 5;

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                starting_node: startingNode,
                show_tunnels: showTunnels,
                max_depth: maxDepth
            })
        });

        if (response.ok) {
            alert('Settings saved successfully. A new scan will apply the changes.');
            settingsPanel.classList.add('hidden');
            // Trigger a new scan to apply the changes
            requestScan();
        } else {
            alert('Failed to save settings');
        }

    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Failed to save settings');
    }
}

/**
 * Toggle settings panel
 */
function toggleSettings() {
    if (settingsPanel.classList.contains('hidden')) {
        loadSettings();
        settingsPanel.classList.remove('hidden');
        sidePanel.classList.add('hidden');
    } else {
        settingsPanel.classList.add('hidden');
    }
}

/**
 * Event type icons and labels
 */
const EVENT_ICONS = {
    'node_discovered': { icon: '&#10133;', label: 'Node Discovered', class: 'event-info' },
    'node_offline': { icon: '&#10060;', label: 'Node Offline', class: 'event-warning' },
    'node_online': { icon: '&#10004;', label: 'Node Online', class: 'event-success' },
    'link_new': { icon: '&#128279;', label: 'New Link', class: 'event-info' },
    'link_dropped': { icon: '&#128280;', label: 'Link Dropped', class: 'event-warning' },
    'link_restored': { icon: '&#128279;', label: 'Link Restored', class: 'event-success' },
    'frequency_change': { icon: '&#128246;', label: 'Frequency Change', class: 'event-warning' }
};

/**
 * Toggle event log panel
 */
function toggleLog() {
    if (logPanel.classList.contains('hidden')) {
        loadEventLog();
        logPanel.classList.remove('hidden');
        sidePanel.classList.add('hidden');
        settingsPanel.classList.add('hidden');
    } else {
        logPanel.classList.add('hidden');
    }
}

/**
 * Load event log from server
 */
async function loadEventLog() {
    try {
        const response = await fetch('/api/events?limit=200');
        const events = await response.json();
        eventLog = events;
        renderEventLog();
    } catch (error) {
        console.error('Error loading event log:', error);
    }
}

/**
 * Render event log with filters
 */
function renderEventLog() {
    const showNodes = document.getElementById('filter-nodes').checked;
    const showLinks = document.getElementById('filter-links').checked;
    const showFreq = document.getElementById('filter-freq').checked;

    const nodeEvents = ['node_discovered', 'node_offline', 'node_online'];
    const linkEvents = ['link_new', 'link_dropped', 'link_restored'];
    const freqEvents = ['frequency_change'];

    const filtered = eventLog.filter(event => {
        if (nodeEvents.includes(event.event_type) && !showNodes) return false;
        if (linkEvents.includes(event.event_type) && !showLinks) return false;
        if (freqEvents.includes(event.event_type) && !showFreq) return false;
        return true;
    });

    if (filtered.length === 0) {
        logContent.innerHTML = '<p class="log-empty">No events to display</p>';
        return;
    }

    let html = '';
    for (const event of filtered) {
        const eventInfo = EVENT_ICONS[event.event_type] || { icon: '&#8226;', label: event.event_type, class: 'event-info' };
        const timestamp = formatLogTimestamp(event.timestamp);

        html += `
            <div class="log-entry ${eventInfo.class}">
                <span class="log-icon">${eventInfo.icon}</span>
                <div class="log-details">
                    <div class="log-header">
                        <span class="log-type">${eventInfo.label}</span>
                        <span class="log-time">${timestamp}</span>
                    </div>
                    <div class="log-node">${event.node_name || ''}</div>
                    <div class="log-message">${event.details || ''}</div>
                </div>
            </div>
        `;
    }

    logContent.innerHTML = html;
}

/**
 * Format timestamp for log display
 */
function formatLogTimestamp(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
}

/**
 * Add new event to log (called from WebSocket)
 */
function addEventToLog(event) {
    console.log('Adding event to log:', event);

    // Add to beginning of array
    eventLog.unshift({
        event_type: event.type,
        node_name: event.node,
        details: event.details,
        severity: event.severity,
        timestamp: new Date().toISOString()
    });

    // Keep only last 200 events in memory
    if (eventLog.length > 200) {
        eventLog.pop();
    }

    // Re-render if log panel is visible
    if (logPanel && !logPanel.classList.contains('hidden')) {
        renderEventLog();
        // Scroll to top to show new event
        if (logContent) {
            logContent.scrollTop = 0;
        }
    }
}

/**
 * Initialize event listeners
 */
function initEventListeners() {
    // Scan button
    document.getElementById('scan-btn').addEventListener('click', requestScan);

    // Log button
    document.getElementById('log-btn').addEventListener('click', toggleLog);

    // Settings button
    document.getElementById('settings-btn').addEventListener('click', toggleSettings);

    // Close panel buttons
    document.getElementById('close-panel').addEventListener('click', hidePanel);
    document.getElementById('close-settings').addEventListener('click', () => {
        settingsPanel.classList.add('hidden');
    });
    document.getElementById('close-log').addEventListener('click', () => {
        logPanel.classList.add('hidden');
    });

    // Save settings button
    document.getElementById('save-settings').addEventListener('click', saveSettings);

    // Reset positions button
    document.getElementById('reset-positions').addEventListener('click', resetNodePositions);

    // Log filter checkboxes
    document.getElementById('filter-nodes').addEventListener('change', renderEventLog);
    document.getElementById('filter-links').addEventListener('change', renderEventLog);
    document.getElementById('filter-freq').addEventListener('change', renderEventLog);
}

/**
 * Reset all node positions and re-run physics layout
 */
function resetNodePositions() {
    if (!confirm('Reset all node positions? This will re-run the automatic layout.')) {
        return;
    }

    // Clear localStorage
    localStorage.removeItem(POSITIONS_STORAGE_KEY);

    // Clear fixed positions from all nodes
    nodesDataset.forEach(node => {
        nodesDataset.update({
            id: node.id,
            x: undefined,
            y: undefined,
            fixed: { x: false, y: false }
        });
    });

    // Re-enable physics temporarily to re-layout
    isInitialLoad = true;
    network.setOptions({ physics: { enabled: true } });
}

/**
 * Load initial data
 */
async function loadInitialData() {
    try {
        const response = await fetch('/api/network');
        const data = await response.json();
        updateNetwork(data);

        // Also get status
        const statusResponse = await fetch('/api/status');
        const status = await statusResponse.json();
        const maxDepth = status.last_result ? status.last_result.max_depth_reached : 0;
        updateStats(status.node_count, status.link_count, status.last_scan, maxDepth);

    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

/**
 * Main initialization
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing AREDN Network Monitor');

    initNetwork();
    initSocket();
    initEventListeners();
    loadInitialData();
});
