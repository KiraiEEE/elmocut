from PyQt5.QtWidgets import QMainWindow, QSpinBox, QLabel, QPushButton, QCheckBox, QHBoxLayout, QVBoxLayout, QWidget, QGroupBox
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt, QByteArray
from networking.nicknames import Nicknames
from ui.ui_device import Ui_MainWindow
from assets import device_icon

class DeviceWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, elmocut, icon):
        super().__init__()
        self.elmocut = elmocut
        self.device = None
        self.current_row = -1
        self.__nicknames = Nicknames()

        # Setup UI with device icon
        self.device_window_icon = self.processIcon(device_icon)
        self.icon = icon
        self.setWindowIcon(self.device_window_icon)
        self.setupUi(self)
        
        # Add bandwidth limiting controls
        self.setup_bandwidth_controls()
        
        self.setPlaceholderColor()
        
        self.btnChange.clicked.connect(self.changeName)
        self.btnReset.clicked.connect(self.resetName)
        # On Enter Pressed
        self.txtNickname.returnPressed.connect(self.changeName)
    
    def setup_bandwidth_controls(self):
        """Add bandwidth limiting controls to device window"""
        # Create bandwidth group box
        bandwidth_group = QGroupBox("Bandwidth Limiting")
        bandwidth_layout = QVBoxLayout()
        
        # Speed presets
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Quick Presets:")
        self.btn_slow = QPushButton("Slow (128KB/s)")
        self.btn_medium = QPushButton("Medium (512KB/s)")
        self.btn_fast = QPushButton("Fast (2MB/s)")
        
        self.btn_slow.setMaximumWidth(120)
        self.btn_medium.setMaximumWidth(140)
        self.btn_fast.setMaximumWidth(120)
        
        self.btn_slow.clicked.connect(lambda: self.apply_preset(128, 128))
        self.btn_medium.clicked.connect(lambda: self.apply_preset(512, 512))
        self.btn_fast.clicked.connect(lambda: self.apply_preset(2048, 2048))
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.btn_slow)
        preset_layout.addWidget(self.btn_medium)
        preset_layout.addWidget(self.btn_fast)
        preset_layout.addStretch()
        
        # Download limit
        dl_layout = QHBoxLayout()
        self.chk_limit_download = QCheckBox("Download:")
        self.spin_download = QSpinBox()
        self.spin_download.setRange(1, 100000)
        self.spin_download.setValue(512)
        self.spin_download.setSuffix(" KB/s")
        self.spin_download.setEnabled(False)
        self.chk_limit_download.toggled.connect(lambda checked: self.spin_download.setEnabled(checked))
        dl_layout.addWidget(self.chk_limit_download)
        dl_layout.addWidget(self.spin_download)
        dl_layout.addStretch()
        
        # Upload limit
        ul_layout = QHBoxLayout()
        self.chk_limit_upload = QCheckBox("Upload:")
        self.spin_upload = QSpinBox()
        self.spin_upload.setRange(1, 100000)
        self.spin_upload.setValue(512)
        self.spin_upload.setSuffix(" KB/s")
        self.spin_upload.setEnabled(False)
        self.chk_limit_upload.toggled.connect(lambda checked: self.spin_upload.setEnabled(checked))
        ul_layout.addWidget(self.chk_limit_upload)
        ul_layout.addWidget(self.spin_upload)
        ul_layout.addStretch()
        
        # Apply button
        btn_layout = QHBoxLayout()
        self.btn_apply_bandwidth = QPushButton("Apply Limits")
        self.btn_remove_bandwidth = QPushButton("Remove")
        self.btn_apply_bandwidth.clicked.connect(self.apply_bandwidth_limits)
        self.btn_remove_bandwidth.clicked.connect(self.remove_bandwidth_limits)
        self.btn_apply_bandwidth.setStyleSheet("background-color: #4CAF50; font-weight: bold;")
        self.btn_remove_bandwidth.setStyleSheet("background-color: #f44336; font-weight: bold;")
        btn_layout.addWidget(self.btn_apply_bandwidth)
        btn_layout.addWidget(self.btn_remove_bandwidth)
        
        # Add to layout
        bandwidth_layout.addLayout(preset_layout)
        bandwidth_layout.addLayout(dl_layout)
        bandwidth_layout.addLayout(ul_layout)
        bandwidth_layout.addLayout(btn_layout)
        bandwidth_group.setLayout(bandwidth_layout)
        
        # Add to main horizontal layout with 35% width (stretch factor 35)
        if hasattr(self, 'centralWidget'):
            main_layout = self.centralWidget().layout()
            if main_layout:
                main_layout.addWidget(bandwidth_group, 35)
        
        self.bandwidth_group = bandwidth_group
    
    def load(self, device, current_row):
        self.lblIP.setText(device.ip)
        self.lblMAC.setText(device.mac)
        if device.name != '-':
            self.txtNickname.setText(device.name)
        else:
            self.txtNickname.setText('')
        self.current_row = current_row
        self.device = device

    def setPlaceholderColor(self):
        pal = self.txtNickname.palette()
        pal.setColor(QPalette.PlaceholderText, QColor('#B5B5B5'))
        self.txtNickname.setPalette(pal)
        
    def changeName(self):
        name = self.txtNickname.text().strip()
        if not name or name == '-':
            name = self.device.name
            return self.instantApplyChanges(name)
        self.__nicknames.set_name(self.device.mac, name)
        self.instantApplyChanges(name)
    
    def resetName(self):
        name = '-'
        self.__nicknames.reset_name(self.device.mac)
        self.txtNickname.setText('')
        self.instantApplyChanges(name)

    def instantApplyChanges(self, name):
        self.device.name = name
        self.elmocut.fillTableRow(self.current_row, self.device)
        self.close()
    
    def apply_preset(self, download_kb, upload_kb):
        """Apply a bandwidth preset"""
        self.chk_limit_download.setChecked(True)
        self.chk_limit_upload.setChecked(True)
        self.spin_download.setValue(download_kb)
        self.spin_upload.setValue(upload_kb)
        self.apply_bandwidth_limits()
    
    def apply_bandwidth_limits(self):
        """Apply bandwidth limits to the device (auto-kills if needed)"""
        if not self.device or self.device.admin:
            self.elmocut.log('Cannot limit admin devices', 'orange')
            return
        
        if not self.chk_limit_download.isChecked() and not self.chk_limit_upload.isChecked():
            self.elmocut.log('Please enable at least one limit', 'orange')
            return
        
        download_limit = self.spin_download.value() if self.chk_limit_download.isChecked() else None
        upload_limit = self.spin_upload.value() if self.chk_limit_upload.isChecked() else None
        
        success = self.elmocut.killer.limit_bandwidth(
            self.device,
            download_kbps=download_limit,
            upload_kbps=upload_limit
        )
        
        if success:
            limit_text = []
            if download_limit:
                limit_text.append(f"↓{download_limit}KB/s")
            if upload_limit:
                limit_text.append(f"↑{upload_limit}KB/s")
            
            self.elmocut.log(f'Limited {self.device.ip}: {", ".join(limit_text)}', 'cyan')
            self.elmocut.showDevices()  # Refresh table to show limited status
    
    def remove_bandwidth_limits(self):
        """Remove bandwidth limits from the device"""
        if not self.device:
            return
        
        self.elmocut.killer.remove_bandwidth_limit(self.device)
        self.elmocut.log(f'Limits removed from {self.device.ip}', 'lime')
        self.elmocut.showDevices()  # Refresh table
        
        # Reset checkboxes
        self.chk_limit_download.setChecked(False)
        self.chk_limit_upload.setChecked(False)

    @staticmethod
    def processIcon(icon_data):
        """Convert icon byte data to QIcon"""
        byte_array = QByteArray(icon_data)
        pixmap = QPixmap()
        pixmap.loadFromData(byte_array)
        icon = QIcon()
        icon.addPixmap(pixmap)
        return icon
    
    def showEvent(self, event):
        self.setStyleSheet(self.elmocut.styleSheet())
        
        # Load current bandwidth limits if any
        limits = self.elmocut.killer.get_bandwidth_limits()
        if self.device and self.device.mac in limits:
            limit_info = limits[self.device.mac]
            if limit_info.get('download') and limit_info['download'] != float('inf'):
                self.chk_limit_download.setChecked(True)
                self.spin_download.setValue(int(limit_info['download'] / 1024))
            if limit_info.get('upload') and limit_info['upload'] != float('inf'):
                self.chk_limit_upload.setChecked(True)
                self.spin_upload.setValue(int(limit_info['upload'] / 1024))
        
        event.accept()