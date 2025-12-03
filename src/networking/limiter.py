"""
Bandwidth Limiter for Windows using Scapy packet manipulation
This module provides upload and download speed limiting for network devices
"""

from scapy.all import sniff, send, IP, TCP, UDP, Raw
from threading import Thread, Event
from time import time, sleep
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class BandwidthLimiter:
    """
    Controls bandwidth for specific devices by intercepting and rate-limiting packets
    """
    
    def __init__(self, iface):
        self.iface = iface
        self.limited_devices = {}  # {mac: {'download': kb/s, 'upload': kb/s}}
        self.packet_queues = defaultdict(list)  # {mac: [packets]}
        self.byte_counters = defaultdict(lambda: {'sent': 0, 'time': time()})
        self.running = False
        self.threads = {}
        self.stop_events = {}
        
    def limit_device(self, victim_ip, victim_mac, download_kbps=None, upload_kbps=None):
        """
        Apply bandwidth limits to a device
        
        Args:
            victim_ip: Target device IP
            victim_mac: Target device MAC
            download_kbps: Download speed limit in KB/s (None = unlimited)
            upload_kbps: Upload speed limit in KB/s (None = unlimited)
        """
        if victim_mac in self.limited_devices:
            logger.warning(f'{victim_mac} already has bandwidth limits')
            return
        
        self.limited_devices[victim_mac] = {
            'ip': victim_ip,
            'mac': victim_mac,
            'download': download_kbps * 1024 if download_kbps else None,  # Convert to bytes/s
            'upload': upload_kbps * 1024 if upload_kbps else None,
        }
        
        # Start limiter thread for this device
        stop_event = Event()
        self.stop_events[victim_mac] = stop_event
        
        limiter_thread = Thread(
            target=self._limit_worker,
            args=(victim_mac, stop_event),
            daemon=True
        )
        self.threads[victim_mac] = limiter_thread
        limiter_thread.start()
        
        logger.info(f'Bandwidth limiter started for {victim_ip} ({victim_mac}): '
                   f'Download={download_kbps}KB/s, Upload={upload_kbps}KB/s')
    
    def unlimit_device(self, victim_mac):
        """
        Remove bandwidth limits from a device
        """
        if victim_mac not in self.limited_devices:
            logger.warning(f'{victim_mac} has no bandwidth limits')
            return
        
        # Stop the limiter thread
        if victim_mac in self.stop_events:
            self.stop_events[victim_mac].set()
        
        # Clean up
        self.limited_devices.pop(victim_mac, None)
        self.packet_queues.pop(victim_mac, None)
        self.byte_counters.pop(victim_mac, None)
        self.threads.pop(victim_mac, None)
        self.stop_events.pop(victim_mac, None)
        
        logger.info(f'Bandwidth limits removed for {victim_mac}')
    
    def _limit_worker(self, victim_mac, stop_event):
        """
        Worker thread that enforces bandwidth limits for a specific device
        """
        device_info = self.limited_devices.get(victim_mac)
        if not device_info:
            return
        
        victim_ip = device_info['ip']
        download_limit = device_info['download']
        upload_limit = device_info['upload']
        
        # Sniff filter for this specific device
        filter_str = f'host {victim_ip}'
        
        def packet_handler(packet):
            """Process each packet for rate limiting"""
            if stop_event.is_set():
                return True  # Stop sniffing
            
            if IP in packet:
                # Determine if packet is download (to victim) or upload (from victim)
                is_download = packet[IP].dst == victim_ip
                is_upload = packet[IP].src == victim_ip
                
                packet_size = len(packet)
                current_time = time()
                
                mac_key = victim_mac
                counter = self.byte_counters[mac_key]
                
                # Reset counter every second
                if current_time - counter['time'] >= 1.0:
                    counter['sent'] = 0
                    counter['time'] = current_time
                
                # Check if we should rate limit
                should_limit = False
                
                if is_download and download_limit:
                    if counter['sent'] + packet_size > download_limit:
                        should_limit = True
                elif is_upload and upload_limit:
                    if counter['sent'] + packet_size > upload_limit:
                        should_limit = True
                
                if should_limit:
                    # Drop packet (don't forward it)
                    logger.debug(f'Rate limiting packet for {victim_mac}')
                    return
                else:
                    # Update counter and forward packet
                    counter['sent'] += packet_size
        
        try:
            # Start sniffing for this device
            sniff(
                filter=filter_str,
                prn=packet_handler,
                iface=self.iface.name,
                store=0,
                stop_filter=lambda x: stop_event.is_set()
            )
        except Exception as e:
            logger.error(f'Error in bandwidth limiter for {victim_mac}: {e}')
    
    def get_limited_devices(self):
        """
        Get list of devices with bandwidth limits
        """
        return dict(self.limited_devices)
    
    def stop_all(self):
        """
        Stop all bandwidth limiting
        """
        for mac in list(self.limited_devices.keys()):
            self.unlimit_device(mac)
        
        logger.info('All bandwidth limits stopped')


class SimpleBandwidthLimiter:
    """
    Simplified bandwidth limiter that works alongside ARP spoofing
    Packets are forwarded with delays to simulate bandwidth limits
    """
    
    def __init__(self):
        self.limits = {}  # {mac: {'download_kbps': X, 'upload_kbps': Y}}
        self.last_reset = defaultdict(lambda: time())
        self.bytes_sent = defaultdict(int)
    
    def set_limit(self, mac, download_kbps=None, upload_kbps=None):
        """Set bandwidth limit for a MAC address"""
        self.limits[mac] = {
            'download': download_kbps * 1024 if download_kbps else float('inf'),
            'upload': upload_kbps * 1024 if upload_kbps else float('inf')
        }
        logger.info(f'Bandwidth limit set for {mac}: DL={download_kbps}KB/s, UL={upload_kbps}KB/s')
    
    def remove_limit(self, mac):
        """Remove bandwidth limit for a MAC address"""
        if mac in self.limits:
            del self.limits[mac]
            logger.info(f'Bandwidth limit removed for {mac}')
    
    def should_forward_packet(self, mac, packet_size, direction='download'):
        """
        Check if packet should be forwarded based on bandwidth limits
        
        Returns:
            tuple: (should_forward: bool, delay: float)
        """
        if mac not in self.limits:
            return True, 0
        
        current_time = time()
        limit_key = f'{mac}_{direction}'
        
        # Reset counter every second
        if current_time - self.last_reset[limit_key] >= 1.0:
            self.bytes_sent[limit_key] = 0
            self.last_reset[limit_key] = current_time
        
        # Get the appropriate limit
        limit = self.limits[mac].get(direction, float('inf'))
        
        # Check if we've exceeded the limit
        if self.bytes_sent[limit_key] + packet_size > limit:
            # Calculate delay needed
            time_until_reset = 1.0 - (current_time - self.last_reset[limit_key])
            return False, max(0, time_until_reset)
        
        # Update counter
        self.bytes_sent[limit_key] += packet_size
        return True, 0
    
    def get_limits(self):
        """Get all current limits"""
        return dict(self.limits)
