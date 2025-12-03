import sys
import os
from pathlib import Path

# Add src directory to path if needed
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from sys import argv, exit
from PyQt5.QtWidgets import QApplication
import logging

# Try to import logging_config, use basic config if not available
try:
    from logging_config import setup_logging
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False
    logging.basicConfig(level=logging.INFO)

from tools.utils import goto
from tools.utils_gui import npcap_exists, duplicate_elmocut, repair_settings, migrate_settings_file
from tools.qtools import msg_box, Buttons, MsgIcon

from gui.main import ElmoCut

from assets import app_icon
from constants import *

# import debug.test

if __name__ == "__main__":
    # Initialize logging first
    if LOGGING_AVAILABLE:
        setup_logging(logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f'Starting elmoCut v{VERSION}')
    
    app = QApplication(argv)
    icon = ElmoCut.processIcon(app_icon)

    # Check if Npcap is installed
    if not npcap_exists():
        if msg_box('elmoCut', 'Npcap is not installed\n\nClick OK to download',
                    MsgIcon.CRITICAL, icon, Buttons.OK | Buttons.CANCEL) == Buttons.OK:
            goto(NPCAP_URL)
    
    # Check if another elmoCut process is running
    elif duplicate_elmocut():
        msg_box('elmoCut', 'elmoCut is already running!', MsgIcon.WARN, icon)
    
    # Run the GUI
    else:
        migrate_settings_file()
        repair_settings()
        GUI = ElmoCut()
        GUI.show()
        GUI.resizeEvent()
        GUI.scanner.init()
        GUI.scanner.flush_arp()
        # Set attacker's MAC to prevent self-targeting
        GUI.killer.set_my_mac(GUI.scanner.my_mac)
        GUI.scanEasy()
        # Bring window to top on startup
        GUI.activateWindow()
        exit(app.exec_())