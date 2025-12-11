"""Network utility functions for Z-Image Studio."""

import socket
import ipaddress
import sys
import os
from typing import List, Tuple

# Handle both module and direct execution
try:
    from .logger import get_logger
except ImportError:
    # When running directly, adjust path and import
    sys.path.insert(0, os.path.dirname(__file__))
    from logger import get_logger

logger = get_logger(__name__)


def get_local_ips() -> List[str]:
    """
    Get all non-loopback IPv4 addresses on the current machine.

    Returns:
        List of IPv4 addresses as strings
    """
    ips = []

    try:
        # Get hostname
        hostname = socket.gethostname()

        # Get all addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, None)

        # Extract unique IPv4 addresses, excluding loopback
        seen_ips = set()
        for info in addr_info:
            ip = info[4][0]

            # Only include IPv4 addresses
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == 4 and not ip_obj.is_loopback:
                    # Exclude link-local addresses (169.254.x.x)
                    if not ip_obj.is_link_local:
                        if ip not in seen_ips:
                            seen_ips.add(ip)
                            ips.append(ip)
            except ValueError:
                # Skip invalid IP addresses
                continue

    except Exception as e:
        logger.debug(f"Error getting local IPs via hostname: {e}")

    # Fallback: try to get IP by connecting to external address
    if not ips:
        try:
            # This creates a dummy socket to determine the outgoing IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to a public DNS server (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if local_ip and not local_ip.startswith("127.") and not local_ip.startswith("169.254."):
                    ips.append(local_ip)
        except Exception as e:
            logger.debug(f"Error getting local IP via fallback method: {e}")

    # Sort IPs for consistent output
    ips.sort(key=lambda ip: ipaddress.ip_address(ip))

    # Always include localhost as the first option
    if "127.0.0.1" not in ips:
        ips.insert(0, "127.0.0.1")

    return ips


def get_accessible_urls(host: str, port: int) -> Tuple[List[str], str]:
    """
    Generate a list of accessible URLs for the web server.

    Args:
        host: The host the server is bound to
        port: The port the server is listening on

    Returns:
        Tuple of (list_of_accessible_urls, primary_url)
    """
    urls = []
    primary_url = f"http://{host}:{port}"

    # If binding to all interfaces (0.0.0.0), show all possible access methods
    if host == "0.0.0.0":
        # Get all local IPs
        local_ips = get_local_ips()

        # Generate URLs for each IP
        for ip in local_ips:
            url = f"http://{ip}:{port}"
            urls.append(url)

        # Use localhost as the primary URL for user convenience
        primary_url = f"http://localhost:{port}"
    else:
        # Binding to a specific interface
        urls.append(primary_url)

    return urls, primary_url


def format_server_urls(host: str, port: int) -> str:
    """
    Format server URLs for display in startup message.

    Args:
        host: The host the server is bound to
        port: The port the server is listening on

    Returns:
        Formatted string with URLs
    """
    urls, primary_url = get_accessible_urls(host, port)

    # If only one URL, return it directly
    if len(urls) == 1:
        return f"      {primary_url}"

    # Multiple URLs - format as a list
    lines = [f"      {primary_url}", f"      Other accessible URLs:"]

    for url in urls:
        lines.append(f"      {url}")

    return "\n".join(lines)