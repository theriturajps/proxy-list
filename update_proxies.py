import requests
import re
from datetime import datetime

SOURCES = [
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http",
    "https://www.proxyscan.io/api/proxy?format=txt&type=http&limit=1000",
    "https://proxylist.geonode.com/api/proxy-list?protocols=http,https&limit=500"
]

def get_proxies():
    proxies = set()
    for url in SOURCES:
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', line):
                        proxies.add(line)
        except Exception as e:
            print(f"Error: {str(e)}")
    return sorted(proxies)

def update_readme(count):
    now = datetime.utcnow().strftime("%A %d-%m-%Y %H:%M:%S UTC")
    try:
        with open("README.md", "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Proxy List\n\n"
        
    content = re.sub(r"Last Updated:.*", f"Last Updated: `{now}`", content)
    content = re.sub(r"Total Proxies:.*", f"Total Proxies: `{count}`", content)
    
    with open("README.md", "w") as f:
        f.write(content)

if __name__ == "__main__":
    proxies = get_proxies()
    
    with open("proxies.txt", "w") as f:
        f.write("\n".join(proxies))
    
    update_readme(len(proxies))
    print(f"Updated {len(proxies)} proxies")