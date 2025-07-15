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
    """Extracts download progress from Play Store UI"""
    # Try different ways the progress might appear
    progress_elements = [
        d(descriptionMatches=".*% of.*"),  # "13% of 84.92 MB"
        d(textMatches=".*%$"),              # "13%"
        d(textMatches="Downloading.*")       # "Downloading..."
    ]
    
    for element in progress_elements:
        if element.exists:
            desc = element.info.get('contentDescription', '') or element.info.get('text', '')
            if '%' in desc:
                # Extract percentage and size if available
                percent = int(re.search(r'(\d+)%', desc).group(1))
                size_match = re.search(r'of ([\d.]+ \w+)', desc)
                size = size_match.group(1) if size_match else "Unknown size"
                return percent, size
    return None, None

PKG_RE = re.compile(r"name=com.instagram.android.*?progress=([0-9.]+)")
def track_progress(serial, user, outfile):
    d = u2.connect(serial)
    with pathlib.Path(outfile).open("a", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["Timestamp", "Progress (%)", "Size", "Status"])
        
        while True:
            # Check for completion first
            if d(text="Open").exists:
                wr.writerow([datetime.datetime.now().isoformat(), 100, "Complete", "Open button visible"])
                print("✅ Installation finished (Open button detected)")
                return
            
            # Try to get Play Store UI progress
            percent, size = get_play_store_progress(d)
            if percent is not None:
                status = f"Downloading: {percent}% of {size}" if size else f"Downloading: {percent}%"
                wr.writerow([datetime.datetime.now().isoformat(), percent, size or "", status])
                f.flush()
                print(status)
                time.sleep(1)
                continue
            
            # Fallback to package installer progress
            try:
                out = adb_shell(["dumpsys", "packageinstaller", "--user", user], serial=serial)
                m = PKG_RE.search(out)
                if m:
                    pct = float(m.group(1)) * 100
                    status = f"Installing: {pct:.1f}%"
                    wr.writerow([datetime.datetime.now().isoformat(), pct, "", status])
                    f.flush()
                    print(status)
                    if pct >= 100:
                        print("✅ Package installer reports 100%")
            except subprocess.CalledProcessError:
                pass
            
            time.sleep(1)

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