"""
elmoCut v1.0.8-kiraieee
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ANSI color codes for Windows
try:
    import colorama
    colorama.init()
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False

class Colors:
    if COLORS_AVAILABLE:
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        RESET = '\033[0m'
        BOLD = '\033[1m'
    else:
        GREEN = YELLOW = RED = BLUE = CYAN = RESET = BOLD = ''

def print_colored(text, color=''):
    """Print colored text"""
    print(f"{color}{text}{Colors.RESET}")

def print_header(text):
    """Print a header"""
    print()
    print_colored("="*60, Colors.CYAN)
    print_colored(f"  {text}", Colors.CYAN + Colors.BOLD)
    print_colored("="*60, Colors.CYAN)
    print()

def print_success(text):
    """Print success message"""
    print_colored(f"[OK] {text}", Colors.GREEN)

def print_error(text):
    """Print error message"""
    print_colored(f"[ERROR] {text}", Colors.RED)

def print_warning(text):
    """Print warning message"""
    print_colored(f"[WARNING] {text}", Colors.YELLOW)

def print_info(text):
    """Print info message"""
    print_colored(f"[INFO] {text}", Colors.BLUE)

def run_command(command, capture_output=True, shell=True):
    """Run a command and return success status"""
    try:
        if capture_output:
            result = subprocess.run(command, shell=shell, capture_output=True, text=True)
            return result.returncode == 0, result.stdout, result.stderr
        else:
            result = subprocess.run(command, shell=shell)
            return result.returncode == 0, "", ""
    except Exception as e:
        return False, "", str(e)

def check_python_version():
    """Check if Python version is adequate"""
    print_info("Checking Python version...")
    version = sys.version_info
    
    if version.major >= 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} is too old (need 3.8+)")
        print_error("Download from: https://www.python.org/downloads/")
        return False

def check_pip():
    """Check if pip is available"""
    print_info("Checking pip...")
    success, _, _ = run_command("pip --version")
    if success:
        print_success("pip is available")
        return True
    else:
        print_error("pip not found")
        return False

def install_colorama():
    """Install colorama for colored output"""
    print_info("Installing colorama for better output...")
    success, _, _ = run_command("pip install colorama")
    if success:
        print_success("colorama installed")
        return True
    return False

def check_and_install_dependencies():
    """Check and install required dependencies"""
    print_info("Checking dependencies...")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print_error("requirements.txt not found!")
        return False
    
    # Check if packages are installed
    print_info("Verifying installed packages...")
    success, stdout, _ = run_command("pip list")
    
    required_packages = ['PyQt5', 'scapy', 'qdarkstyle', 'pyperclip', 'manuf', 'requests']
    missing_packages = []
    
    for package in required_packages:
        if package.lower() not in stdout.lower():
            missing_packages.append(package)
    
    if missing_packages:
        print_warning(f"Missing packages: {', '.join(missing_packages)}")
        print_info("Installing dependencies (this may take a few minutes)...")
        
        success, _, stderr = run_command("pip install -r requirements.txt --upgrade")
        if success:
            print_success("All dependencies installed")
            return True
        else:
            print_error("Failed to install some dependencies")
            print_error(stderr)
            return False
    else:
        print_success("All dependencies are installed")
        return True

def check_npcap():
    """Check if Npcap is installed"""
    print_info("Checking for Npcap...")
    
    npcap_paths = [
        Path("C:/Windows/SysWOW64/Npcap/wpcap.dll"),
        Path("C:/Windows/System32/Npcap/wpcap.dll"),
    ]
    
    for path in npcap_paths:
        if path.exists():
            print_success("Npcap is installed")
            return True
    
    print_warning("Npcap not found")
    print_warning("Npcap is required for packet capture")
    print()
    print_colored("Download from: https://nmap.org/npcap/", Colors.YELLOW)
    print()
    
    response = input("Open download page? (Y/N): ").strip().lower()
    if response in ['y', 'yes']:
        run_command('start "" "https://nmap.org/npcap/"', capture_output=False)
        print()
        print_warning("Please install Npcap and run this script again")
        return False
    
    return False

def compile_ui_files():
    """Compile Qt UI files to Python"""
    print_info("Checking UI files...")
    
    ui_files = [
        ('exe/ui_main.ui', 'src/ui/ui_main.py'),
        ('exe/ui_about.ui', 'src/ui/ui_about.py'),
        ('exe/ui_device.ui', 'src/ui/ui_device.py'),
        ('exe/ui_settings.ui', 'src/ui/ui_settings.py'),
    ]
    
    needs_compilation = False
    for ui_file, py_file in ui_files:
        ui_path = Path(ui_file)
        py_path = Path(py_file)
        
        if not ui_path.exists():
            print_warning(f"UI file not found: {ui_file}")
            continue
        
        # Check if compilation is needed
        if not py_path.exists() or ui_path.stat().st_mtime > py_path.stat().st_mtime:
            needs_compilation = True
            break
    
    if not needs_compilation:
        print_success("UI files are up to date")
        return True
    
    print_info("Compiling UI files...")
    
    # Check if pyuic5 is available
    success, _, _ = run_command("pyuic5 --version")
    if not success:
        print_warning("pyuic5 not found, installing PyQt5-tools...")
        run_command("pip install pyqt5-tools")
    
    # Compile each UI file
    compiled_count = 0
    for ui_file, py_file in ui_files:
        ui_path = Path(ui_file)
        if not ui_path.exists():
            continue
        
        py_path = Path(py_file)
        py_path.parent.mkdir(parents=True, exist_ok=True)
        
        success, _, stderr = run_command(f'pyuic5 "{ui_file}" -o "{py_file}"')
        if success:
            compiled_count += 1
        else:
            print_error(f"Failed to compile {ui_file}")
    
    if compiled_count > 0:
        print_success(f"Compiled {compiled_count} UI files")
        return True
    else:
        print_warning("No UI files compiled")
        return True  # Don't fail if UI files already exist

def check_directory_structure():
    """Ensure necessary directories exist"""
    print_info("Checking directory structure...")
    
    directories = [
        'src',
        'src/ui',
        'src/gui',
        'src/networking',
        'src/models',
        'src/tools',
        'exe',
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print_success("Directory structure OK")
    return True

def check_admin():
    """Check if running as administrator"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_application():
    """Run the elmoCut application"""
    print_header("Starting elmoCut")
    
    if not check_admin():
        print()
        print_warning("="*60)
        print_warning("NOT RUNNING AS ADMINISTRATOR!")
        print_warning("Some features may not work properly.")
        print_warning("Right-click START.bat and select 'Run as administrator'")
        print_warning("="*60)
        print()
        
        response = input("Continue anyway? (Y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print_info("Cancelled. Please run as Administrator.")
            return False
    
    print_colored("\nStarting application...\n", Colors.CYAN)
    print()
    
    # Change to src directory and run
    src_path = Path("src/elmocut.py")
    if not src_path.exists():
        print_error("elmocut.py not found!")
        return False
    
    # Run the application
    try:
        subprocess.run([sys.executable, str(src_path)], check=False)
        return True
    except KeyboardInterrupt:
        print()
        print_info("Application closed by user")
        return True
    except Exception as e:
        print_error(f"Error running application: {e}")
        return False

def show_menu():
    """Show interactive menu"""
    print_header("elmoCut Launcher v1.0.8")
    
    print("1. Run elmoCut")
    print("2. Install/Update Dependencies")
    print("3. Compile UI Files")
    print("4. Check System Requirements")
    print("5. Exit")
    print()
    
    choice = input("Select option (1-5): ").strip()
    return choice

def main():
    """Main entry point"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print_colored("""
    ================================================
                elmoCut Launcher                
           All-in-One Startup Script            
    ================================================
    """, Colors.CYAN)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Install colorama if not available
    if not COLORS_AVAILABLE:
        install_colorama()
        print_info("Please restart this script for colored output")
    
    # Quick mode - check everything and run
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        print_header("Quick Start Mode")
        
        if not check_python_version():
            return 1
        
        if not check_pip():
            return 1
        
        check_directory_structure()
        
        if not check_and_install_dependencies():
            print_error("Cannot continue without dependencies")
            return 1
        
        if not check_npcap():
            print_error("Cannot continue without Npcap")
            return 1
        
        compile_ui_files()
        
        run_application()
        return 0
    
    # Interactive mode
    while True:
        choice = show_menu()
        
        if choice == '1':
            # Run application with full checks
            print_header("Pre-flight Checks")
            
            all_ok = True
            
            if not check_python_version():
                all_ok = False
            
            if not check_pip():
                all_ok = False
            
            check_directory_structure()
            
            if not check_and_install_dependencies():
                all_ok = False
            
            if not check_npcap():
                print_warning("Npcap not installed - application may not work")
                response = input("Continue anyway? (Y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    all_ok = False
            
            compile_ui_files()
            
            if all_ok:
                run_application()
            else:
                print_error("Please fix the issues above before running")
            
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            print_header("Installing Dependencies")
            check_and_install_dependencies()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            print_header("Compiling UI Files")
            compile_ui_files()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            print_header("System Requirements Check")
            check_python_version()
            check_pip()
            check_and_install_dependencies()
            check_npcap()
            check_directory_structure()
            compile_ui_files()
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            print()
            print_success("Goodbye!")
            return 0
        
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_info("Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)
