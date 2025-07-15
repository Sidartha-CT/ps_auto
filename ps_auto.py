import subprocess
import time
import re
import csv
from datetime import datetime

def monitor_playstore_download(package_name="com.instagram.android", device_serial=None):
    # Prepare ADB command
    adb_base = ['adb']
    if device_serial:
        adb_base.extend(['-s', device_serial])
    
    # Open CSV file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"playstore_download_{timestamp}.csv"
    
    with open(csv_filename, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['Timestamp', 'Percentage', 'Downloaded', 'Total'])
        
        print(f"Monitoring {package_name} on device: {device_serial or 'default'}")
        print("Press Ctrl+C to stop...")
        
        try:
            while True:
                # Build full command
                cmd = adb_base + ['shell', 'dumpsys', 'package', 'downloads']
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Parse output
                pattern = re.compile(
                    rf'Downloading.*{package_name}.*?progress (\d+).*?(\d+)/(\d+)',
                    re.DOTALL)
                match = pattern.search(result.stdout)
                
                if match:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    row = [current_time, *match.groups()]
                    csv_writer.writerow(row)
                    print(', '.join(row))
                else:
                    print("No active download found.")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\nData saved to {csv_filename}")

if __name__ == "__main__":
    # Example usage with device serial
    monitor_playstore_download(device_serial="RZCTA09CTXF")
    
    # Or for default device
    # monitor_playstore_download()