#!/usr/bin/env python3
# playstore_auto_install_and_track.py
import uiautomator2 as u2, subprocess, time, csv, datetime, re, sys, argparse, pathlib

ADB = "adb"                       # put full path here if adb isn’t in PATH
BUTTON_TEXTS = ("Update", "Install")       # if your phone is in another language, localise this!

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
            d(text=label).click()
            print(f'Clicked "{label}"')
            return
    raise RuntimeError("No Install / Update button found; is the app already up‑to‑date?")

# ───────── progress tracker exactly like earlier example ──────────
PKG_RE = re.compile(r"name=com.instagram.android.*?progress=([0-9.]+)")
def check_open_button(serial):
    d = u2.connect(serial)
    return d(text="Open").exists
def track_progress(serial, user, outfile):
    with pathlib.Path(outfile).open("a", newline="") as f:
        wr = csv.writer(f)
        while True:
            out = adb_shell(["dumpsys", "packageinstaller", "--user", user], serial=serial)
            m = PKG_RE.search(out)
            
            # Check if "Open" button exists (installation complete)
            if check_open_button(serial):
                print("✅ Installation finished (Open button detected)")
                wr.writerow([datetime.datetime.now().isoformat(timespec="seconds"), 100.0])
                return
            
            # Fallback: Still track progress %
            if m:
                pct = float(m.group(1)) * 100
                ts = datetime.datetime.now().isoformat(timespec="seconds")
                wr.writerow([ts, pct])
                f.flush()
                print(f"{ts}  {pct:5.1f}%")
                if pct >= 100:
                    print("✅ Progress reached 100%")
                    return
            
            time.sleep(1)

# ───────────────────── glue everything together ────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="RZCTA09CTXF")
    ap.add_argument("--user", default="0")
    ap.add_argument("--package", default="com.instagram.android")
    ap.add_argument("--csv", default="playstore_progress.csv")
    args = ap.parse_args()

    print("Opening Play Store…")
    launch_play_details(args.serial, args.user, args.package)
    print("Waiting for button…")
    tap_install_button(args.serial)

    print("Tracking progress (1 s)…")
    track_progress(args.serial, args.user, args.csv)
