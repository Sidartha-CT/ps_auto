#!/usr/bin/env python3
# playstore_auto_install_and_track.py
#
# Track Google Play install/download progress and log it to CSV.
#
#   pip install --upgrade uiautomator2
#   adb must be in PATH (or edit ADB variable below)

import uiautomator2 as u2
import subprocess, time, csv, datetime, re, sys, argparse, pathlib, os

ADB = "adb"                               # full path if adb isn't in PATH
BUTTON_TEXTS = ("Update", "Install", "Open")

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def adb_shell(cmd, *, serial, user="0"):
    return subprocess.check_output(
        [ADB, "-s", serial, "shell"] + cmd,
        text=True, stderr=subprocess.DEVNULL
    )

def launch_play_details(serial, user, package):
    """
    Opens Google Play directly on the detail page of the requested package.
    """
    subprocess.check_call(
        [ADB, "-s", serial, "shell",
         "am", "start", "--user", user, "-a", "android.intent.action.VIEW",
         "-d", f"market://details?id={package}", "com.android.vending"]
    )
    d = u2.connect(serial)
    d.wait_activity("com.google.android.finsky.activities.MainActivity", timeout=10)

def tap_install_button(serial):
    """
    Presses "Install" (or "Update").  If only "Open" is found, app is already installed.
    """
    d = u2.connect(serial)
    for label in BUTTON_TEXTS:
        if d(text=label).exists:
            if label == "Open":
                print("App is already installed ‑ exiting.")
                sys.exit(0)
            d(text=label).click()
            print(f'Clicked "{label}"')
            return
    raise RuntimeError("No Install/Update/Open button found")

# ---------------------------------------------------------------------------
# Progress extraction (robust / XML‑based)
# ---------------------------------------------------------------------------

# • Captures "47" from '47%'  or ' 47 % '
PERCENT_RE = re.compile(r'(\d+)\s*%')

# • Optionally captures "84.92 MB" or "1.2 GB" if present after “of”
SIZE_RE    = re.compile(r'\bof\s+([\d.]+\s*[KMGT]?B)\b', re.I)

def get_play_store_progress(d):
    """
    Dump the current UI hierarchy XML once, then regex‑search for the first
    occurrence of "NN %" (with optional "of XX MB/GB").
    Returns (percent:int|None, size:str|None)
    """
    try:
        xml = d.dump_hierarchy(compressed=True)
    except Exception:
        return None, None   # Couldn't dump hierarchy – just skip this tick

    m_pct = PERCENT_RE.search(xml)
    if not m_pct:
        return None, None

    percent = int(m_pct.group(1))

    # Restrict search to the same small slice (±40 chars) around the % to
    # avoid random other “of … MB” strings elsewhere in the hierarchy
    start = max(m_pct.start() - 40, 0)
    end   = m_pct.end() + 40
    slice_ = xml[start:end]

    m_size = SIZE_RE.search(slice_)
    size   = m_size.group(1) if m_size else None

    return percent, size

# ---------------------------------------------------------------------------
# Tracking loop
# ---------------------------------------------------------------------------

def track_progress(serial, user, outfile):
    d = u2.connect(serial)
    last_progress = -1           # -1 so that 0 % prints the first time

    first_write = not pathlib.Path(outfile).exists() or os.path.getsize(outfile) == 0
    with pathlib.Path(outfile).open("a", newline="") as f:
        wr = csv.writer(f)
        if first_write:
            wr.writerow(["Timestamp", "Progress (%)", "Size", "Status"])

        time.sleep(2)            # let the UI draw
        while True:
            # Done?
            if d(text="Open").exists:
                wr.writerow([datetime.datetime.now().isoformat(),
                             100, "Complete", "Open button visible"])
                print("✅ Installation finished (Open button detected)")
                return

            percent, size = get_play_store_progress(d)
            if percent is None:          # nothing readable yet
                time.sleep(0.8)
                continue

            if percent != last_progress:
                status = (f"Downloading: {percent}% of {size}"
                          if size else f"Downloading: {percent}%")
                wr.writerow([datetime.datetime.now().isoformat(),
                             percent, size or "", status])
                f.flush()
                print(status)
                last_progress = percent

            time.sleep(0.8)

# ---------------------------------------------------------------------------
# CLI entry‑point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Auto‑install an app from Google Play and log download progress."
    )
    ap.add_argument("--serial", required=True, help="ADB serial of the target device")
    ap.add_argument("--user",   default="0")
    ap.add_argument("--package", default="com.instagram.android")
    ap.add_argument("--csv",    default="playstore_progress.csv")
    args = ap.parse_args()

    print("Opening Play Store...")
    launch_play_details(args.serial, args.user, args.package)

    print("Waiting for button...")
    tap_install_button(args.serial)

    print("Tracking progress...")
    track_progress(args.serial, args.user, args.csv)
