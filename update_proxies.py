import requests
import re
import json
import csv
import os
import logging
import concurrent.futures
import ipaddress
import socket
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("proxy_scraper")

# Constants
TIMEOUT = 5  # Reduced from 10
MAX_WORKERS = 100  # Significantly increased from 20
VALIDATION_TIMEOUT = 2  # Reduced from 5
CONNECTION_TIMEOUT = 2  # Reduced from 5
VALIDATION_URL = "http://httpbin.org/ip"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
OUTPUT_DIR = "output"
VALIDATION_BATCH_SIZE = 500  # Process proxies in larger batches
SOCKET_TIMEOUT = 1  # Quick socket check timeout

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
            total=2,  # Reduced from 3
            backoff_factor=0.5,  # Reduced from 1
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
            content_type = response.headers.get("Content-Type", "").lower()
            
            if "json" in content_type:
                try:
                    data = response.json()
                    # Handle different JSON structures
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                ip = item.get("ip") or item.get("host") or item.get("addr")
                                port = item.get("port")
                                if ip and port:
                                    try:
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
                                    except (ValueError, TypeError):
                                        continue
                    elif isinstance(data, dict):
                        # Handle nested data structures
                        for key in ["data", "proxies", "items", "results"]:
                            if key in data and isinstance(data[key], list):
                                for item in data[key]:
                                    if isinstance(item, dict):
                                        ip = item.get("ip") or item.get("host") or item.get("addr")
                                        port = item.get("port")
                                        if ip and port:
                                            try:
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
                                            except (ValueError, TypeError):
                                                continue
                except json.JSONDecodeError:
                    # Fallback to text processing if JSON parsing fails
                    pass
            
            # Process as text (either because it's not JSON or JSON parsing failed)
            if count == 0:
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
        if not text:
            return None
            
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
        try:
            # Basic IP validation
            ipaddress.ip_address(proxy.ip)
            
            # Port validation
            if not (1 <= proxy.port <= 65535):
                return
                
            self.proxies[proxy.address] = proxy
        except ValueError:
            # Invalid IP address
            pass
    
    def quick_filter_proxies(self) -> None:
        """Do a quick socket check to filter obviously dead proxies before full validation"""
        logger.info(f"Performing quick socket check on {len(self.proxies)} proxies")
        valid_proxies = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_proxy = {executor.submit(self._socket_check, proxy): proxy for proxy in self.proxies.values()}
            
            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    is_valid = future.result()
                    if is_valid:
                        valid_proxies[proxy.address] = proxy
                except Exception:
                    pass
        
        self.proxies = valid_proxies
        logger.info(f"Quick filter complete. {len(self.proxies)} proxies passed socket check")
    
    def _socket_check(self, proxy: Proxy) -> bool:
        """Check if a socket can be established with the proxy"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            result = sock.connect_ex((proxy.ip, proxy.port))
            sock.close()
            return result == 0
        except:
            return False
    
    def validate_proxies(self, max_workers: int = MAX_WORKERS) -> None:
        """Validate all proxies concurrently and keep track of working ones"""
        logger.info(f"Starting validation of {len(self.proxies)} proxies")
        
        # Split validation into batches to avoid overwhelming resources
        batch_size = VALIDATION_BATCH_SIZE
        proxy_list = list(self.proxies.values())
        total_proxies = len(proxy_list)
        validated_count = 0
        working_count = 0
        
        # Use a shared session for validation to reuse connections
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        
        for i in range(0, total_proxies, batch_size):
            batch = proxy_list[i:min(i+batch_size, total_proxies)]
            logger.info(f"Validating batch {i//batch_size + 1}/{(total_proxies + batch_size - 1)//batch_size}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Use a simplified validation to speedup
                future_to_proxy = {executor.submit(self._fast_validate_proxy, proxy, session): proxy for proxy in batch}
                
                for future in concurrent.futures.as_completed(future_to_proxy):
                    proxy = future_to_proxy[future]
                    try:
                        proxy.working = future.result()
                        proxy.last_checked = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                        
                        if proxy.working:
                            working_count += 1
                            
                        validated_count += 1
                        if validated_count % 100 == 0 or validated_count == total_proxies:
                            logger.info(f"Progress: {validated_count}/{total_proxies} proxies validated. Working: {working_count}")
                            
                    except Exception as exc:
                        proxy.working = False
                        validated_count += 1
        
        logger.info(f"Validation complete. Working proxies: {working_count}/{total_proxies}")
    
    def _fast_validate_proxy(self, proxy: Proxy, session: requests.Session) -> bool:
        """Simplified validation that just checks if the proxy works at all"""
        proxy_url = f"{proxy.protocol}://{proxy.address}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        
        try:
            start_time = time.time()
            response = session.get(
                VALIDATION_URL, 
                proxies=proxies, 
                timeout=VALIDATION_TIMEOUT
            )
            end_time = time.time()
            
            if response.status_code == 200:
                proxy.speed = end_time - start_time
                proxy.anonymity = "unknown"  # Skip detailed anonymity check for speed
                return True
        except:
            pass
            
        return False
    
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
        
        # Create simplified readme without detailed statistics for speed
        readme_content = f"""# Proxy List

Automatically updated repository of free public proxies. Hourly refreshed HTTP/HTTPS proxies for web scraping, cybersecurity, and testing. Raw list available.

**Last Updated:** `{now}`  
**Total Proxies:** `{total_proxies}`

## 📥 Download
```bash
curl -O https://raw.githubusercontent.com/theriturajps/proxy-list/main/proxies.txt
```
        """

        with open("README.md", "w") as f:
            f.write(readme_content)
            
        logger.info("Updated README.md with statistics")


if __name__ == "__main__":
    start_time = time.time()
    scraper = ProxyScraper()
    scraper.scrape_all_sources()
    scraper.quick_filter_proxies()  # Add quick socket check before full validation
    scraper.validate_proxies()
    scraper.save_results()
    end_time = time.time()
    logger.info(f"Total execution time: {end_time - start_time:.2f} seconds")