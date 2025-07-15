#!/usr/bin/env python3
# playstore_auto_install_and_track.py
#
# Dependencies:
#   pip install --upgrade uiautomator2
#   adb must be in PATH (or edit ADB variable below)

import uiautomator2 as u2
import subprocess, time, csv, datetime, re, sys, argparse, pathlib

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
# Progress extraction (robust across Play Store versions)
# ---------------------------------------------------------------------------

PERCENT_RE = re.compile(r'(\d+)\s*%')
SIZE_RE    = re.compile(r'of\s+([\d.]+\s*[MG]B)', re.I)   # “of 84.9 MB” / “of 2.3 GB”

def get_play_store_progress(d):
    """
    Searches the current UI hierarchy for any node whose TEXT contains '%'.
    Returns (percent:int|None, size:str|None).
    """
    # XPath query: every node whose @text attribute contains a %
    for node in d.xpath('//*[contains(@text,"%")]').all():
        txt = str(node.text or "")
        m_pct = PERCENT_RE.search(txt)
        if not m_pct:
            continue            # had a '%' but not in “number%” form

        percent = int(m_pct.group(1))
        m_size  = SIZE_RE.search(txt)
        size    = m_size.group(1) if m_size else None
        return percent, size

    return None, None            # nothing matched this frame

# ---------------------------------------------------------------------------
# Tracking loop
# ---------------------------------------------------------------------------

def track_progress(serial, user, outfile):
    d = u2.connect(serial)
    last_progress = -1           # -1 so that 0 % prints the first time

    with pathlib.Path(outfile).open("a", newline="") as f:
        wr = csv.writer(f)
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
                time.sleep(0.7)
                continue

            if percent != last_progress:
                status = (f"Downloading: {percent}% of {size}"
                          if size else f"Downloading: {percent}%")
                wr.writerow([datetime.datetime.now().isoformat(),
                             percent, size or "", status])
                f.flush()
                print(status)
                last_progress = percent

            time.sleep(0.7)

# ---------------------------------------------------------------------------
# CLI entry‑point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
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
    