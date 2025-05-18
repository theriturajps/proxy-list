import requests
import re
import json
import csv
import os
import logging
import concurrent.futures
import ipaddress
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("proxy_scraper")

# Constants
TIMEOUT = 10
MAX_WORKERS = 10
VALIDATION_TIMEOUT = 5
CONNECTION_TIMEOUT = 5
VALIDATION_URL = "http://httpbin.org/ip"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
OUTPUT_DIR = "output"

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

@dataclass
class Proxy:
    ip: str
    port: int
    protocol: str = "http"
    country: str = ""
    anonymity: str = ""
    speed: float = 0.0
    last_checked: str = ""
    working: bool = False
    
    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"
    
    def to_dict(self) -> Dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "country": self.country,
            "anonymity": self.anonymity,
            "speed": self.speed,
            "last_checked": self.last_checked,
            "working": self.working,
        }


class ProxyScraper:
    def __init__(self):
        self.sources = [
            # Free HTTP/HTTPS proxy lists
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
        self.session = self._create_session()
        self.proxies: Dict[str, Proxy] = {}  # Use address as key
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retries and timeouts"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": USER_AGENT})
        return session
    
    def scrape_all_sources(self) -> None:
        """Scrape proxies from all sources concurrently"""
        logger.info(f"Starting scraping from {len(self.sources)} sources")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(self.scrape_source, url): url for url in self.sources}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    proxy_count = future.result()
                    logger.info(f"Scraped {proxy_count} proxies from {url}")
                except Exception as exc:
                    logger.error(f"Error scraping from {url}: {exc}")
        
        logger.info(f"Completed scraping. Total unique proxies: {len(self.proxies)}")
    
    def scrape_source(self, url: str) -> int:
        """Scrape proxies from a single source"""
        count = 0
        try:
            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            
            # Handle different response formats (plain text, JSON)
            if "json" in response.headers.get("Content-Type", ""):
                data = response.json()
                # Handle different JSON structures
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            ip = item.get("ip") or item.get("host") or item.get("addr")
                            port = item.get("port")
                            if ip and port:
                                proxy = Proxy(
                                    ip=ip,
                                    port=int(port),
                                    protocol=item.get("protocol", "http"),
                                    country=item.get("country", ""),
                                    anonymity=item.get("anonymity", ""),
                                    speed=float(item.get("speed", 0)),
                                    last_checked=item.get("last_checked", "")
                                )
                                self._add_proxy(proxy)
                                count += 1
                elif isinstance(data, dict):
                    # Handle nested data structures
                    for key in ["data", "proxies", "items", "results"]:
                        if key in data and isinstance(data[key], list):
                            for item in data[key]:
                                if isinstance(item, dict):
                                    ip = item.get("ip") or item.get("host") or item.get("addr")
                                    port = item.get("port")
                                    if ip and port:
                                        proxy = Proxy(
                                            ip=ip,
                                            port=int(port),
                                            protocol=item.get("protocol", "http"),
                                            country=item.get("country", ""),
                                            anonymity=item.get("anonymity", ""),
                                            speed=float(item.get("speed", 0)),
                                            last_checked=item.get("last_checked", "")
                                        )
                                        self._add_proxy(proxy)
                                        count += 1
            else:
                # Handle plain text responses
                for line in response.text.split('\n'):
                    line = line.strip()
                    proxy = self._parse_proxy_from_text(line)
                    if proxy:
                        self._add_proxy(proxy)
                        count += 1
                        
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            
        return count
    
    def _parse_proxy_from_text(self, text: str) -> Optional[Proxy]:
        """Parse proxy information from text line"""
        # Match IP:Port pattern
        ip_port_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)$', text)
        if ip_port_match:
            ip, port_str = ip_port_match.groups()
            # Validate IP address
            try:
                ipaddress.ip_address(ip)
                port = int(port_str)
                if 1 <= port <= 65535:
                    return Proxy(ip=ip, port=port)
            except ValueError:
                pass
        return None
    
    def _add_proxy(self, proxy: Proxy) -> None:
        """Add proxy to the collection, avoiding duplicates"""
        self.proxies[proxy.address] = proxy
    
    def validate_proxies(self, max_workers: int = MAX_WORKERS) -> None:
        """Validate all proxies concurrently and keep track of working ones"""
        logger.info(f"Starting validation of {len(self.proxies)} proxies")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(self._validate_proxy, proxy): proxy 
                              for proxy in self.proxies.values()}
            
            completed = 0
            total = len(future_to_proxy)
            
            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    proxy.working, proxy.speed = future.result()
                    proxy.last_checked = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    
                    completed += 1
                    if completed % 50 == 0 or completed == total:
                        working_count = sum(1 for p in self.proxies.values() if p.working)
                        logger.info(f"Validated {completed}/{total} proxies. Working: {working_count}")
                        
                except Exception as exc:
                    logger.error(f"Error validating {proxy.address}: {exc}")
                    
        working_count = sum(1 for p in self.proxies.values() if p.working)
        logger.info(f"Validation complete. Working proxies: {working_count}/{len(self.proxies)}")
    
    def _validate_proxy(self, proxy: Proxy) -> Tuple[bool, float]:
        """Validate a single proxy and return working status and speed"""
        proxy_url = f"{proxy.protocol}://{proxy.address}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        
        try:
            start_time = datetime.now()
            response = requests.get(
                VALIDATION_URL, 
                proxies=proxies, 
                timeout=VALIDATION_TIMEOUT,
                headers={"User-Agent": USER_AGENT}
            )
            end_time = datetime.now()
            
            if response.status_code == 200:
                speed = (end_time - start_time).total_seconds()
                # Verify the response contains the proxy's IP (anonymous check)
                data = response.json()
                if "origin" in data:
                    # For anonymous proxies, the origin might be different from the proxy IP
                    if data["origin"] != proxy.ip:
                        proxy.anonymity = "high"
                    else:
                        proxy.anonymity = "transparent"
                return True, speed
        except Exception:
            pass
            
        return False, 0.0
    
    def save_results(self) -> None:
        """Save proxies to different output formats"""
        self._save_txt()
        self._save_json()
        self._save_csv()
        self._update_readme()
        
    def _save_txt(self) -> None:
        """Save working proxies to a text file (IP:PORT format)"""
        working_proxies = [p.address for p in self.proxies.values() if p.working]
        working_proxies.sort()
        
        with open("proxies.txt", "w") as f:
            f.write("\n".join(working_proxies))
            
        logger.info(f"Saved {len(working_proxies)} working proxies to proxies.txt")
        
        # Also save a copy to the output directory
        with open(os.path.join(OUTPUT_DIR, "proxies.txt"), "w") as f:
            f.write("\n".join(working_proxies))
    
    def _save_json(self) -> None:
        """Save all proxy details to JSON format"""
        all_proxies = {p.address: p.to_dict() for p in self.proxies.values()}
        working_proxies = {p.address: p.to_dict() for p in self.proxies.values() if p.working}
        
        # Save all proxies
        with open(os.path.join(OUTPUT_DIR, "all_proxies.json"), "w") as f:
            json.dump(all_proxies, f, indent=2)
            
        # Save working proxies
        with open(os.path.join(OUTPUT_DIR, "working_proxies.json"), "w") as f:
            json.dump(working_proxies, f, indent=2)
            
        logger.info(f"Saved proxy details to JSON files")
    
    def _save_csv(self) -> None:
        """Save working proxies to CSV format with additional details"""
        working_proxies = [p for p in self.proxies.values() if p.working]
        
        with open(os.path.join(OUTPUT_DIR, "working_proxies.csv"), "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["IP", "Port", "Protocol", "Country", "Anonymity", "Speed (s)", "Last Checked"])
            for proxy in working_proxies:
                writer.writerow([
                    proxy.ip,
                    proxy.port,
                    proxy.protocol,
                    proxy.country,
                    proxy.anonymity,
                    f"{proxy.speed:.2f}",
                    proxy.last_checked
                ])
                
        logger.info(f"Saved {len(working_proxies)} working proxies to CSV")
    
    def _update_readme(self) -> None:
        """Update README.md with proxy statistics"""
        now = datetime.utcnow().strftime("%A %d-%m-%Y %H:%M:%S UTC")
        total_proxies = len([p for p in self.proxies.values() if p.working])
        
        # Count proxies by anonymity level
        anonymity_levels = {
            "transparent": sum(1 for p in self.proxies.values() if p.working and p.anonymity == "transparent"),
            "anonymous": sum(1 for p in self.proxies.values() if p.working and p.anonymity == "anonymous"),
            "high": sum(1 for p in self.proxies.values() if p.working and p.anonymity == "high"),
        }
        
        # Create statistics by country if available
        countries = {}
        for proxy in self.proxies.values():
            if proxy.working and proxy.country:
                countries[proxy.country] = countries.get(proxy.country, 0) + 1
        
        readme_content = f"""# Proxy List

Automatically updated repository of free public proxies. Hourly refreshed HTTP/HTTPS proxies for web scraping, cybersecurity, and testing.

**Last Updated:** `{now}`  
**Total Proxies:** `{total_proxies}`

## 📊 Statistics

- **Anonymity Levels**:
  - High Anonymous: `{anonymity_levels['high']}`
  - Anonymous: `{anonymity_levels['anonymous']}`
  - Transparent: `{anonymity_levels['transparent']}`

## 📥 Download

### Plain Text (IP:PORT format)
```bash
curl -O https://raw.githubusercontent.com/theriturajps/proxy-list/main/proxies.txt
```

### JSON Format (with detailed information)
```bash
curl -O https://raw.githubusercontent.com/theriturajps/proxy-list/main/output/working_proxies.json
```

### CSV Format (with detailed information)
```bash
curl -O https://raw.githubusercontent.com/theriturajps/proxy-list/main/output/working_proxies.csv
```

## 📋 Usage

### Python
```python
import requests

with open('proxies.txt', 'r') as f:
    proxies = [line.strip() for line in f if line.strip()]

for proxy in proxies:
    try:
        response = requests.get(
            'http://httpbin.org/ip', 
            proxies={'http': f'http://{proxy}', 'https': f'http://{proxy}'}, 
            timeout=5
        )
        if response.status_code == 200:
            print(f"Working proxy: {proxy}")
            break
    except:
        continue
```

### curl
```bash
proxy=$(head -n 1 proxies.txt)
curl -x "http://$proxy" http://httpbin.org/ip
```

## 🛠️ Features
- Hourly automatic updates via GitHub Actions
- Proxy validation to ensure all proxies are working
- Multiple output formats (TXT, JSON, CSV)
- Anonymity level detection
- Response time measurement

## ⚠️ Disclaimer
The proxies provided by this repository are free public proxies that are collected from various sources. They are provided for educational and testing purposes only. We do not guarantee their stability, anonymity, or legality for any specific use case.
"""

        with open("README.md", "w") as f:
            f.write(readme_content)
            
        logger.info("Updated README.md with statistics")


if __name__ == "__main__":
    scraper = ProxyScraper()
    scraper.scrape_all_sources()
    scraper.validate_proxies()
    scraper.save_results()