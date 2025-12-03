from concurrent.futures.thread import ThreadPoolExecutor
from scapy.all import arping, sr1, ARP, Ether
from time import sleep, time
import logging
from networking.nicknames import Nicknames
from tools.utils import *
from constants import *
from models.device import Device
from enums import DeviceType

logger = logging.getLogger(__name__)

class Scanner():
    def __init__(self):
        self.iface = get_default_iface()
        self.device_count = 255  # Full subnet scan
        self.max_threads = 32  # Increased for better performance
        self.__ping_done = 0
        self.devices = []
        self.old_ips = {}
        self.router = {}
        self.ips = []
        self.me = {}
        self.perfix = None
        self.qt_progress_signal = int
        self.qt_log_signal = print
        self._device_cache = {}  # Cache for faster lookups
    
    def generate_ips(self):
        self.ips = [f'{self.perfix}.{i}' for i in range(1, self.device_count)]

    def init(self):
        """
        Intializing Scanner
        """
        self.iface = get_iface_by_name(self.iface.name)
        self.devices = []

        self.router_ip = get_gateway_ip(self.iface.name)
        self.router_mac = get_gateway_mac(self.iface.ip, self.router_ip)

        self.my_ip = get_my_ip(self.iface.name)
        self.my_mac = good_mac(self.iface.mac)
        
        self.perfix = self.my_ip.rsplit(".", 1)[0]
        self.generate_ips()
    
    def flush_arp(self):
        """
        Flush ARP cache
        """
        arp_cmd = terminal(CMD_ARP_CACHE_FLUSH)
        # Fix: Some systems has older versions of arp.exe
        # We use netsh instead
        if 'The parameter is incorrect' in arp_cmd:
            terminal(CMD_ARP_CACHE_FLUSH_NEW)

    def add_me(self):
        """
        Get My info and append to self.devices
        """
        self.me = Device(
            ip = self.my_ip,
            mac = self.my_mac,
            vendor = get_vendor(self.my_mac),
            dtype = DeviceType.OWNER,
            name = '',
            admin = True
        )
        
        self.devices.insert(0, self.me)

    def add_router(self):
        """
        Get Gateway info and append to self.devices
        """
        self.router = Device(
            ip = self.router_ip,
            mac = self.router_mac,
            vendor = get_vendor(self.router_mac),
            dtype = DeviceType.ROUTER,
            name = '',
            admin = True
        )

        self.devices.insert(0, self.router)

    def devices_appender(self, scan_result):
        """
        Optimized device list builder with caching
        """
        nicknames = Nicknames()

        self.devices = []
        unique = set()  # Use set for O(1) lookups

        # Sort by last part of ip xxx.xxx.x.y
        scan_result = sorted(
            scan_result,
            key=lambda i: int(i[0].split('.')[-1]) if i[0].count('.') == 3 else 0
        )
        
        for ip, mac in scan_result:
            mac = good_mac(mac)

            # Skip me, router, and duplicated devices
            if ip in [self.router_ip, self.my_ip] or mac in unique:
                continue
            
            unique.add(mac)
            
            # Update same device with new IP (IP changed detection)
            if self.old_ips.get(mac, ip) != ip:
                logger.info(f'Device {mac} changed IP from {self.old_ips.get(mac, "unknown")} to {ip}')
                self.old_ips[mac] = ip
            
            # Use cache for vendor lookup
            if mac not in self._device_cache:
                self._device_cache[mac] = get_vendor(mac)
            
            self.devices.append(
                Device(
                    ip=ip,
                    mac=mac,
                    vendor=self._device_cache[mac],
                    dtype=DeviceType.USER,
                    name=nicknames.get_name(mac),
                    admin=False
                )
            )
        
        # Re-create devices old ips dict
        self.old_ips = {d.mac: d.ip for d in self.devices}

        self.add_me()
        self.add_router()

        # Clear arp cache to avoid duplicates next time
        if unique:
            self.flush_arp()
        
        logger.info(f'Processed {len(self.devices)} devices (including router and self)')
    
    def arping_cache(self):
        """
        Showing system arp cache after pinging
        """
        # Correct scan result when working with specific interface
        scan_result = terminal(CMD_ARP_CACHE(self.my_ip))
        
        if not scan_result:
            print('ARP error has been caught!')
            self.devices_appender([])
            return

        clean_result = [line.split()[:2] for line in scan_result.split('\n') if line.split()]
        self.devices_appender(clean_result)
    
    def arp_scan(self):
        """
        Fast ARP scan using Scapy with optimized speed settings
        """
        self.init()
        logger.info(f'Starting ARP scan on {self.router_ip}/24')
        
        start_time = time()
        
        # Use arping with optimized parameters
        self.generate_ips()
        
        try:
            # Single fast pass with aggressive timing
            scan_result = arping(
                f"{self.router_ip}/24",
                iface=self.iface.name,
                verbose=0,
                timeout=1,    # Fast timeout
                inter=0.01,   # Very small interval for speed
                retry=1       # Single retry only
            )
            
            clean_result = [(item[1].psrc, item[1].src) for item in scan_result[0]]
            logger.info(f'ARP scan completed in {time() - start_time:.2f}s, found {len(clean_result)} devices')
            
        except Exception as e:
            logger.error(f'ARP scan failed: {e}')
            clean_result = []

        self.devices_appender(clean_result)

    def ping_scan(self):
        """
        Optimized ping scan with better thread management
        """
        self.init()
        self.__ping_done = 0
        logger.info(f'Starting ping scan with {self.max_threads} threads')
        
        start_time = time()
        
        self.generate_ips()
        self.ping_thread_pool()
        
        # Progress monitoring with timeout
        timeout = 90  # Increased timeout for slow networks
        last_progress = 0
        stall_time = 0
        
        while self.__ping_done < self.device_count - 1:
            if time() - start_time > timeout:
                logger.warning('Ping scan timeout reached')
                break
            
            # Detect stalls (no progress for 10 seconds)
            if self.__ping_done == last_progress:
                stall_time += 0.01
                if stall_time > 10:
                    logger.warning(f'Ping scan stalled at {self.__ping_done}/{self.device_count - 1}')
                    break
            else:
                last_progress = self.__ping_done
                stall_time = 0
            
            # Reduced sleep for faster UI updates
            sleep(.01)
            self.qt_progress_signal(self.__ping_done)
        
        logger.info(f'Ping scan completed in {time() - start_time:.2f}s, pinged {self.__ping_done} IPs')
        return True
    
    @threaded
    def ping_thread_pool(self):
        """
        Control maximum threads running at once with better resource management
        """
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # Submit all ping tasks
            futures = [executor.submit(self.ping, ip) for ip in self.ips]
            
            # Wait for completion
            for future in futures:
                try:
                    future.result(timeout=5)
                except Exception as e:
                    logger.debug(f'Ping task failed: {e}')

    def ping(self, ip):
        """
        Optimized ping with faster timeout and better error handling
        """
        try:
            # Use faster ping with minimal timeout
            result = terminal(CMD_PING_DEVICE(ip), decode=False)
            # Log successful pings for debugging
            if result and 'ttl=' in str(result).lower():
                logger.debug(f'Ping successful: {ip}')
        except Exception as e:
            logger.debug(f'Ping failed for {ip}: {e}')
        finally:
            self.__ping_done += 1