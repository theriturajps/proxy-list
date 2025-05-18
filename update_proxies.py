import requests
import json
import time
import re
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Configuration
MAX_WORKERS = 20
TIMEOUT = 15
VALIDATE_PROXIES = True
VALIDATION_TIMEOUT = 5
VALIDATION_URL = "http://httpbin.org/ip"

# Proxy Sources (HTTP/HTTPS)
SOURCES = [
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http",
    "https://www.proxyscan.io/api/proxy?format=txt&type=http&limit=1000",
    "https://proxylist.geonode.com/api/proxy-list?protocols=http,https&limit=500",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://proxyspace.pro/http.txt",
    "https://api.proxyscrape.com/?request=getproxies&proxytype=http",
    "https://api.openproxylist.xyz/http.txt",
]

def fetch_proxies_from_source(url):
    """Fetch proxies from a single source"""
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            proxies = set()
            for line in response.text.splitlines():
                line = line.strip()
                if is_valid_proxy(line):
                    proxies.add(line)
            return proxies
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
    return set()

def is_valid_proxy(proxy):
    """Check if a proxy string is valid"""
    parts = proxy.split(':')
    if len(parts) != 2:
        return False
    
    ip, port = parts
    if not port.isdigit():
        return False
    
    # Simple IP validation
    ip_parts = ip.split('.')
    if len(ip_parts) != 4:
        return False
    
    return all(part.isdigit() and 0 <= int(part) <= 255 for part in ip_parts)

def validate_proxy(proxy):
    """Test if a proxy is actually working"""
    try:
        response = requests.get(
            VALIDATION_URL,
            proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
            timeout=VALIDATION_TIMEOUT
        )
        return response.status_code == 200
    except:
        return False

def get_proxies():
    """Fetch and validate proxies from all sources"""
    all_proxies = set()
    
    # Fetch proxies from all sources in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(fetch_proxies_from_source, url): url for url in SOURCES}
        for future in as_completed(future_to_url):
            all_proxies.update(future.result())
    
    # Validate proxies if enabled
    if VALIDATE_PROXIES:
        valid_proxies = set()
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_proxy = {executor.submit(validate_proxy, proxy): proxy for proxy in all_proxies}
            for future in as_completed(future_to_proxy):
                if future.result():
                    valid_proxies.add(future_to_proxy[future])
        all_proxies = valid_proxies
    
    return sorted(all_proxies)

def save_proxies(proxies):
    """Save proxies to both JSON and TXT files"""
    # Save as TXT
    with open("proxies.txt", "w") as f:
        f.write("\n".join(proxies))
    
    # Save as JSON with metadata
    data = {
        "metadata": {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "count": len(proxies),
            "sources": [urlparse(url).netloc for url in SOURCES],
            "validation": VALIDATE_PROXIES
        },
        "proxies": proxies
    }
    
    with open("proxies.json", "w") as f:
        json.dump(data, f, indent=2)

def update_readme(count):
    """Update README with current stats"""
    now = datetime.now(timezone.utc).strftime("%A %d-%m-%Y %H:%M:%S UTC")
    
    try:
        with open("README.md", "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = """# Proxy List

Automatically updated repository of free public proxies. Regularly refreshed HTTP/HTTPS proxies for web scraping, cybersecurity, and testing. Available in both raw text and JSON formats.

**Last Updated:** `Sunday 18-05-2025 15:15:04 UTC`  
**Total Proxies:** `0`

## Features
- Multiple reliable sources
- Proxy validation
- JSON and TXT formats
- Hourly updates
- Detailed metadata

## 📥 Download

### Raw Text Format
```bash
curl -O https://raw.githubusercontent.com/yourusername/proxy-list/main/proxies.txt
```