#!/usr/bin/env python3
# playstore_auto_install_and_track.py
import uiautomator2 as u2, subprocess, time, csv, datetime, re, sys, argparse, pathlib

ADB = "adb"                       # put full path here if adb isn't in PATH
BUTTON_TEXTS = ("Update", "Install", "Open")  # Added "Open" for completion check

def adb_shell(cmd, *, serial, user="0"):
    return subprocess.check_output(
        [ADB, "-s", serial, "shell"] + cmd,
        text=True, stderr=subprocess.DEVNULL)

def launch_play_details(serial, user, package):
    # market://details?id=<pkg> opens straight on that app's detail page
    subprocess.check_call(
        [ADB, "-s", serial, "shell",
         "am", "start", "--user", user, "-a", "android.intent.action.VIEW",
         "-d", f"market://details?id={package}", "com.android.vending"])
    # Play Store can take a second to draw; wait until the title bar shows up
    d = u2.connect(serial)
    d.wait_activity("com.google.android.finsky.activities.MainActivity", timeout=10)

def tap_install_button(serial):
    d = u2.connect(serial)
    for label in BUTTON_TEXTS:
        if d(text=label).exists:
            if label == "Open":
                print("App is already installed")
                sys.exit(0)
            d(text=label).click()
            print(f'Clicked "{label}"')
            return
    raise RuntimeError("No Install/Update/Open button found")

def get_play_store_progress(d):
    """Enhanced progress detection that handles different Play Store UI versions"""
    # Try multiple possible UI element locations for progress
    progress_elements = [
        d(descriptionMatches=".*% of.*MB"),  # "13% of 84.92 MB"
        d(descriptionMatches=".*%$"),        # "13%"
        d(textMatches=".*% of.*MB"),         # Alternative text location
        d(textMatches=".*%$"),               # Just percentage
        d(className="android.widget.ProgressBar"),  # Direct progress bar access
    ]
    
    for element in progress_elements:
        if element.exists:
            # Get either contentDescription or text
            desc = element.info.get('contentDescription', '') or element.info.get('text', '')
            
            # Extract percentage
            percent_match = re.search(r'(\d+)%', desc)
            if not percent_match:
                continue
            percent = int(percent_match.group(1))
            
            # Extract size if available
            size_match = re.search(r'of ([\d.]+ \w+)', desc)
            size = size_match.group(1) if size_match else None
            
            # For progress bars, try to get the actual progress value
            if not percent and element.className == "android.widget.ProgressBar":
                percent = int(element.info.get('progress', 0))
                max_progress = int(element.info.get('max', 100))
                if max_progress > 0:
                    percent = int((percent / max_progress) * 100)
            
            return percent, size
    
    return 0, 0

PKG_RE = re.compile(r"name=com.instagram.android.*?progress=([0-9.]+)")
def track_progress(serial, user, outfile):
    d = u2.connect(serial)
    last_progress = 0
    
    with pathlib.Path(outfile).open("a", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["Timestamp", "Progress (%)", "Size", "Status"])
        
        time.sleep(2)  # Wait for UI to initialize
        while True:
            if d(text="Open").exists:
                wr.writerow([datetime.datetime.now().isoformat(), 100, "Complete", "Open button visible"])
                print("✅ Installation finished (Open button detected)")
                return
            
            percent, size = get_play_store_progress(d)
            if percent is not None:
                if percent != last_progress:
                    status = f"Downloading: {percent}% of {size}" if size else f"Downloading: {percent}%"
                    wr.writerow([datetime.datetime.now().isoformat(), percent, size or "", status])
                    f.flush()
                    print(status)
                    last_progress = percent
                if percent >= 100:
                    print("Waiting for installation to complete...")
                    time.sleep(2)
                    continue
            time.sleep(0.5)
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="RZCTA09CTXF")
    ap.add_argument("--user", default="0")
    ap.add_argument("--package", default="com.instagram.android")
    ap.add_argument("--csv", default="playstore_progress.csv")
    args = ap.parse_args()

    print("Opening Play Store...")
    launch_play_details(args.serial, args.user, args.package)
    print("Waiting for button...")
    tap_install_button(args.serial)

    print("Tracking progress (1s)...")
    track_progress(args.serial, args.user, args.csv)