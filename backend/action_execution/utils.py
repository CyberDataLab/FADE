import ipaddress

def build_mac_command(policy_type, value):
    """
    Builds a shell command string to apply a firewall rule on macOS using pfctl.

    Supported policy types:
        - 'block_ip': Blocks traffic from the specified IP address.
        - 'block_port': Blocks both TCP and UDP traffic on the specified port.
        - 'allow_ip': Allows traffic from the specified IP address.
        - 'allow_port': Allows both TCP and UDP traffic on the specified port.
        - 'limit_bandwidth': Not supported; returns a warning command.

    Args:
        policy_type (str): The type of policy to apply (e.g., 'block_ip').
        value (str or int): The value used in the rule (e.g., IP address or port).

    Returns:
        str: A shell command to append the rule to /etc/pf-block.rules and reload pf.

    Raises:
        ValueError: If an unsupported policy_type is passed.
    """
    def build_rule(rule):
        # Constructs the shell command to append a rule and reload pf rules
        return (
            f"echo \"{rule}\" | sudo tee -a /etc/pf-block.rules && "
            f"sudo pfctl -a blockrules -f /etc/pf-block.rules"
        )

    # Mapping of policy types to their corresponding pf rule templates
    rules = {
        # Block source IP (inbound)
        'block_ip_src': lambda v: (
            f"block drop in quick from {v} to any"
        ),

        # Block destination IP (outbound)
        'block_ip_dst': lambda v: (
            f"block drop out quick to {v}"
        ),

        # Allow SOURCE IP (inbound)
        'allow_ip_src': lambda v: (
            f"pass in quick from {v} to any"
        ),
        # Allow DESTINATION IP (outbound)
        'allow_ip_dst': lambda v: (
            f"pass out quick to {v}"
        ),

        # Allow both TCP and UDP traffic from a specific port (inbound and outbound)
        'block_port_src': lambda v: (
            f"block drop in quick proto tcp from any port {v} to any\n"
            f"block drop in quick proto udp from any port {v} to any\n"
            f"block drop out quick proto tcp from any port {v} to any\n"
            f"block drop out quick proto udp from any port {v} to any"
        ),

        # Block both TCP and UDP traffic to a specific port (inbound and outbound)
        'block_port_dst': lambda v: (
            f"block drop in quick proto tcp from any to any port {v}\n"
            f"block drop in quick proto udp from any to any port {v}\n"
            f"block drop out quick proto tcp to any port {v}\n"
            f"block drop out quick proto udp to any port {v}"
        ),

        # Allow both TCP and UDP traffic from a specific port (inbound and outbound)
        'allow_port_src': lambda v: (
            f"pass in quick proto tcp from any port {v} to any\n"
            f"pass in quick proto udp from any port {v} to any\n"
            f"pass out quick proto tcp from any port {v} to any\n"
            f"pass out quick proto udp from any port {v} to any"
        ),

        # Allow both TCP and UDP traffic to a specific port (inbound and outbound)
        'allow_port_dst': lambda v: (
            f"pass in quick proto tcp from any to any port {v}\n"
            f"pass in quick proto udp from any to any port {v}\n"
            f"pass out quick proto tcp to any port {v}\n"
            f"pass out quick proto udp to any port {v}"
        ),
    }

    if policy_type in rules:
        # Generate one or more rules and build command(s) for each
        rule = rules[policy_type](value)
        return " && ".join([build_rule(r) for r in rule.split('\n')])

    elif policy_type == 'limit_bandwidth':
        # Bandwidth limiting is not supported on modern macOS versions
        return "echo 'Bandwidth limiting not supported on recent macOS versions'"

    else:
        # Raise error if policy_type is unsupported
        raise ValueError(f"Unsupported policy type: {policy_type}")

def _tool_for_ip(v):
    """Return the proper firewall tool for the given IP: 'iptables' (IPv4) or 'ip6tables' (IPv6)."""
    try:
        return "iptables" if ipaddress.ip_address(v).version == 4 else "ip6tables"
    except ValueError:
        raise ValueError(f"Invalid IP address: {v}")
    
def build_linux_command(policy_type, value):
    """
    Builds a shell command string to apply a firewall or traffic control rule on Linux.

    Supported policy types:
        - 'block_ip': Blocks incoming traffic from the specified IP address.
        - 'block_port': Blocks incoming TCP traffic on the specified port.
        - 'allow_ip': Allows incoming traffic from the specified IP address.
        - 'allow_port': Allows incoming TCP traffic on the specified port.
        - 'limit_bandwidth': Applies a bandwidth limit using `tc` on a specified interface.

    Args:
        policy_type (str): The type of policy to apply (e.g., 'block_ip', 'limit_bandwidth').
        value (str): The value used in the rule. For 'limit_bandwidth', use format "interface:rate" (e.g., "eth0:1mbit").

    Returns:
        str: A shell command string to apply the rule on a Linux system.

    Raises:
        ValueError: If the policy_type is not recognized.
    """
    if policy_type in ('block_ip_src', 'block_ip_dst', 'allow_ip_src', 'allow_ip_dst'):
        tool = _tool_for_ip(value)

        if policy_type == 'block_ip_src':
            # Drop inbound traffic from source IP
            return f"sudo {tool} -I INPUT 1  -s {value} -j DROP"

        elif policy_type == 'block_ip_dst':
            # Drop outbound traffic to destination IP
            return f"sudo {tool} -I OUTPUT 1 -d {value} -j DROP"

        elif policy_type == 'allow_ip_src':
            # Accept inbound traffic from source IP
            return f"sudo {tool} -I INPUT 1  -s {value} -j ACCEPT"

        elif policy_type == 'allow_ip_dst':
            # Accept outbound traffic to destination IP
            return f"sudo {tool} -I OUTPUT 1 -d {value} -j ACCEPT"

    # --- Port-based rules (always TCP+UDP, INPUT+OUTPUT, v4+v6) ---
    elif policy_type == 'block_port_src':
        cmds = [
            f"sudo iptables  -I INPUT  1 -p tcp --sport {value} -j DROP",
            f"sudo iptables  -I INPUT  1 -p udp --sport {value} -j DROP",
            f"sudo iptables  -I OUTPUT 1 -p tcp --sport {value} -j DROP",
            f"sudo iptables  -I OUTPUT 1 -p udp --sport {value} -j DROP",
            f"sudo ip6tables -I INPUT  1 -p tcp --sport {value} -j DROP",
            f"sudo ip6tables -I INPUT  1 -p udp --sport {value} -j DROP",
            f"sudo ip6tables -I OUTPUT 1 -p tcp --sport {value} -j DROP",
            f"sudo ip6tables -I OUTPUT 1 -p udp --sport {value} -j DROP",
        ]
        return " && ".join(cmds)

    elif policy_type == 'block_port_dst':
        cmds = [
            f"sudo iptables  -I INPUT  1 -p tcp --dport {value} -j DROP",
            f"sudo iptables  -I INPUT  1 -p udp --dport {value} -j DROP",
            f"sudo iptables  -I OUTPUT 1 -p tcp --dport {value} -j DROP",
            f"sudo iptables  -I OUTPUT 1 -p udp --dport {value} -j DROP",
            f"sudo ip6tables -I INPUT  1 -p tcp --dport {value} -j DROP",
            f"sudo ip6tables -I INPUT  1 -p udp --dport {value} -j DROP",
            f"sudo ip6tables -I OUTPUT 1 -p tcp --dport {value} -j DROP",
            f"sudo ip6tables -I OUTPUT 1 -p udp --dport {value} -j DROP",
        ]
        return " && ".join(cmds)

    elif policy_type == 'allow_port_src':
        cmds = [
            f"sudo iptables  -I INPUT  1 -p tcp --sport {value} -j ACCEPT",
            f"sudo iptables  -I INPUT  1 -p udp --sport {value} -j ACCEPT",
            f"sudo iptables  -I OUTPUT 1 -p tcp --sport {value} -j ACCEPT",
            f"sudo iptables  -I OUTPUT 1 -p udp --sport {value} -j ACCEPT",
            f"sudo ip6tables -I INPUT  1 -p tcp --sport {value} -j ACCEPT",
            f"sudo ip6tables -I INPUT  1 -p udp --sport {value} -j ACCEPT",
            f"sudo ip6tables -I OUTPUT 1 -p tcp --sport {value} -j ACCEPT",
            f"sudo ip6tables -I OUTPUT 1 -p udp --sport {value} -j ACCEPT",
        ]
        return " && ".join(cmds)

    elif policy_type == 'allow_port_dst':
        cmds = [
            f"sudo iptables  -I INPUT  1 -p tcp --dport {value} -j ACCEPT",
            f"sudo iptables  -I INPUT  1 -p udp --dport {value} -j ACCEPT",
            f"sudo iptables  -I OUTPUT 1 -p tcp --dport {value} -j ACCEPT",
            f"sudo iptables  -I OUTPUT 1 -p udp --dport {value} -j ACCEPT",
            f"sudo ip6tables -I INPUT  1 -p tcp --dport {value} -j ACCEPT",
            f"sudo ip6tables -I INPUT  1 -p udp --dport {value} -j ACCEPT",
            f"sudo ip6tables -I OUTPUT 1 -p tcp --dport {value} -j ACCEPT",
            f"sudo ip6tables -I OUTPUT 1 -p udp --dport {value} -j ACCEPT",
        ]
        return " && ".join(cmds)
    
    elif policy_type == 'limit_bandwidth':
        # Limit bandwidth on a given interface
        # Format: "interface:rate" (e.g., "eth0:1mbit")
        interface, rate = value.split(":")
        return f"sudo tc qdisc add dev {interface} root tbf rate {rate} burst 32kbit latency 400ms"

    else:
        # Raise error for unsupported policy types
        raise ValueError(f"Unsupported policy type: {policy_type}")