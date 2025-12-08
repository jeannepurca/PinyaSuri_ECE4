#!/usr/bin/env python3
"""
PinyaSuri System Check Utility
Run this script to verify all components are properly configured
"""

import sys
import os
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")

def check_pass(text):
    print(f"{Colors.GREEN}✓{Colors.ENDC} {text}")

def check_fail(text):
    print(f"{Colors.RED}✗{Colors.ENDC} {text}")

def check_warn(text):
    print(f"{Colors.YELLOW}⚠{Colors.ENDC} {text}")

def check_python_version():
    """Check Python version"""
    print_header("Python Version Check")
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        check_pass(f"Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        check_fail(f"Python {version.major}.{version.minor}.{version.micro} - Need 3.9+")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    print_header("Dependency Check")
    
    packages = {
        'mavsdk': 'MAVSDK',
        'picamera2': 'Picamera2',
        'tflite_runtime.interpreter': 'TFLite Runtime',
        'PIL': 'Pillow',
        'numpy': 'NumPy'
    }
    
    all_ok = True
    for module, name in packages.items():
        try:
            __import__(module)
            check_pass(f"{name} installed")
        except ImportError:
            check_fail(f"{name} NOT installed - run: pip install {module.split('.')[0]}")
            all_ok = False
    
    return all_ok

def check_serial_device():
    """Check if serial device exists"""
    print_header("Serial Connection Check")
    
    devices = ['/dev/ttyAMA0', '/dev/serial0']
    found = False
    
    for device in devices:
        if Path(device).exists():
            check_pass(f"Found serial device: {device}")
            found = True
        else:
            check_warn(f"Device not found: {device}")
    
    if not found:
        check_fail("No serial devices found - check Pixhawk connection")
        print("   Run: ls -l /dev/ttyAMA* /dev/serial*")
    
    return found

def check_camera():
    """Check if camera is available"""
    print_header("Camera Check")
    
    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        camera_info = camera.camera_properties
        check_pass("Camera detected")
        print(f"   Model: {camera_info.get('Model', 'Unknown')}")
        return True
    except Exception as e:
        check_fail(f"Camera not available: {e}")
        print("   Run: libcamera-hello --list-cameras")
        return False

def check_config_file():
    """Check if config file exists"""
    print_header("Configuration Check")
    
    if Path('config.py').exists():
        check_pass("config.py found")
        
        # Import and check paths
        try:
            import config
            check_pass(f"Base directory: {config.BASE_DIR}")
            check_pass(f"Pixhawk address: {config.PIXHAWK_ADDRESS}")
            check_pass(f"Model path: {config.MODEL_PATH}")
            
            # Check if model exists
            if config.MODEL_PATH.exists():
                check_pass(f"Model file found: {config.MODEL_PATH}")
            else:
                check_warn(f"Model file not found: {config.MODEL_PATH}")
            
            return True
        except Exception as e:
            check_fail(f"Error loading config: {e}")
            return False
    else:
        check_fail("config.py not found")
        return False

def check_project_structure():
    """Check if all required files exist"""
    print_header("Project Structure Check")
    
    required_files = [
        'main.py',
        'main_improved.py',
        'pixhawk_interface.py',
        'image_capture.py',
        'ai_classifier.py',
        'flight_metrics.py',
        'requirements.txt'
    ]
    
    all_ok = True
    for file in required_files:
        if Path(file).exists():
            check_pass(f"{file} found")
        else:
            check_fail(f"{file} NOT found")
            all_ok = False
    
    return all_ok

def check_permissions():
    """Check if user has necessary permissions"""
    print_header("Permissions Check")
    
    # Check if user is in dialout group (for serial access)
    import subprocess
    try:
        groups = subprocess.check_output(['groups'], text=True)
        if 'dialout' in groups or 'tty' in groups:
            check_pass("User has serial port access")
            return True
        else:
            check_warn("User may not have serial access")
            print("   Run: sudo usermod -a -G dialout $USER")
            print("   Then logout and login again")
            return False
    except Exception as e:
        check_warn(f"Could not check permissions: {e}")
        return True

def generate_summary(results):
    """Generate overall system status"""
    print_header("System Check Summary")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"Checks passed: {passed}/{total}")
    
    if passed == total:
        check_pass("All checks passed! System is ready.")
        return True
    elif passed >= total * 0.7:
        check_warn("Most checks passed. Review warnings above.")
        return True
    else:
        check_fail("Several checks failed. Fix issues before running.")
        return False

def main():
    """Run all system checks"""
    print(f"\n{Colors.BOLD}PinyaSuri System Check{Colors.ENDC}")
    print(f"Verifying system configuration...\n")
    
    results = {}
    
    results['python'] = check_python_version()
    results['dependencies'] = check_dependencies()
    results['structure'] = check_project_structure()
    results['config'] = check_config_file()
    results['serial'] = check_serial_device()
    results['camera'] = check_camera()
    results['permissions'] = check_permissions()
    
    system_ready = generate_summary(results)
    
    print(f"\n{Colors.BOLD}Next Steps:{Colors.ENDC}")
    if system_ready:
        print("1. Update config.py with your specific paths")
        print("2. Place your TFLite model in the configured location")
        print("3. Test with: python3 test_flight.py")
        print("4. Run mission with: python3 main_improved.py")
    else:
        print("1. Fix the issues listed above")
        print("2. Run this script again to verify")
        print("3. See README.md for detailed setup instructions")
    
    print()
    return 0 if system_ready else 1

if __name__ == "__main__":
    sys.exit(main())
