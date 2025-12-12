from collections import defaultdict

# Used to track running threads for traffic capture
thread_controls = {}

# Tracks anomaly counts per IP address
ip_anomaly_counter = defaultdict(int)

# Tracks anomaly counts per port
port_anomaly_counter = defaultdict(int)
