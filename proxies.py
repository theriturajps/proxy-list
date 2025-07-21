import requests
import re
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random

SOURCES = [
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http",
    "https://www.proxyscan.io/api/proxy?format=txt&type=http&limit=1000",
    "https://proxylist.geonode.com/api/proxy-list?protocols=http,https&limit=500",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list.txt"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def fetch_proxies(url):
    try:
        headers = {
            'User-Agent': get_random_user_agent()
        }
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            proxies = set()
            for line in response.text.split('\n'):
                line = line.strip()
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', line):
                    proxies.add(line)
            return proxies
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
    return set()

def get_proxies():
    proxies = set()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_proxies, url) for url in SOURCES]
        for future in as_completed(futures):
            try:
                proxies.update(future.result())
            except Exception as e:
                print(f"Error processing future: {str(e)}")
    return sorted(proxies)

def save_proxies(proxies):
    # Save as TXT
    with open("proxies.txt", "w") as f:
        f.write("\n".join(proxies))
    
    # Save as JSON with metadata
    proxy_data = {
        "metadata": {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "count": len(proxies),
            "sources": SOURCES
        },
        "proxies": proxies
    }
    with open("proxies.json", "w") as f:
        json.dump(proxy_data, f, indent=2)
    
    # Save for website
    with open("docs/proxies.json", "w") as f:
        json.dump(proxy_data, f, indent=2)

def update_readme(count):
    now = datetime.utcnow().strftime("%A %d-%m-%Y %H:%M:%S UTC")
    try:
        with open("README.md", "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = """# Advanced Proxy List

Automatically updated repository of free public proxies. Hourly refreshed HTTP/HTTPS proxies in both TXT and JSON formats.

## Features
- Multiple reliable sources
- Concurrent fetching for faster updates
- Both TXT and JSON formats
- Detailed metadata
- Web interface for easy browsing
"""

    content = re.sub(
        r'\*\*Last Updated:\*\*.*',
        f'**Last Updated:** `{now}`  ',
        content
    )
    
    content = re.sub(
        r'\*\*Total Proxies:\*\*.*',
        f'**Total Proxies:** `{count}`',
        content
    )

    with open("README.md", "w") as f:
        f.write(content)

if __name__ == "__main__":
    start_time = time.time()
    print("Starting proxy update...")
    
    proxies = get_proxies()
    save_proxies(proxies)
    update_readme(len(proxies))
    
    elapsed = time.time() - start_time
    print(f"Updated {len(proxies)} proxies in {elapsed:.2f} seconds")