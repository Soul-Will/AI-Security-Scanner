import socket
import ipaddress
from urllib.parse import urlparse

# Define the denylist based on TRD-02 Feature 2
SSRF_DENYLIST = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
]

def is_ip_in_denylist(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in SSRF_DENYLIST:
            if ip in network:
                return True
        return False
    except ValueError:
        return True # Treat invalid IPs as unsafe

def validate_url_safety(url: str) -> tuple[bool, str, list[str]]:
    """
    Validates a URL against SSRF vulnerabilities by resolving its hostname
    and checking against a denylist of private/local subnets.
    Returns: (is_safe, reason, resolved_ips)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format: missing hostname.", []

        # Resolve hostname (both IPv4 and IPv6 if available)
        addr_info = socket.getaddrinfo(hostname, None)
        resolved_ips = []
        for info in addr_info:
            ip = info[4][0]
            if ip not in resolved_ips:
                resolved_ips.append(ip)

        if not resolved_ips:
            return False, "DNS resolution failed: no IP addresses found.", []

        for ip in resolved_ips:
            if is_ip_in_denylist(ip):
                return False, f"SSRF block: Host resolves to denylisted IP ({ip}).", resolved_ips

        # Perform a quick reachability check (Feature 3)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        reachable = False
        for ip in resolved_ips:
            try:
                # Use a fast timeout for reachability check (sub-second or short timeout)
                # TRD-02 indicates ~500ms constraint, but resolving/testing over internet might take up to 2-3s.
                socket.create_connection((ip, port), timeout=3.0)
                reachable = True
                break
            except (socket.timeout, socket.error):
                continue
                
        if not reachable:
            return False, f"Reachability failed: Host did not respond on expected port {port}.", resolved_ips

        return True, "reachable and safe", resolved_ips
        
    except socket.gaierror:
        return False, "DNS resolution failed: NXDOMAIN or unable to resolve.", []
    except Exception as e:
        return False, f"Unexpected error during validation: {str(e)}", []
