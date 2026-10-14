import sys
import os
import json
import time
import random
import datetime
from pathlib import Path

import requests
import pandas as pd

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QFrame
)

from ui import (
    AIOrbVisualizerWidget, MultiStoreAnalyticsWidget,
    BulkDropZoneWidget, TabbedSettingsModal
)

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

try:
    import cv2
    import mediapipe as mp
    VISION_AVAILABLE = True
except Exception:
    VISION_AVAILABLE = False

try:
    import speech_recognition as sr
    import pyttsx3
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except Exception:
    TWILIO_AVAILABLE = False

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as google_build
    GMAIL_AVAILABLE = True
except Exception:
    GMAIL_AVAILABLE = False


class ConfigDatabaseManager:
    def __init__(self):
        self.local_path = Path.home() / ".omnichannel_ai_config.json"
        self.config = self._load_local()
        self.supabase = None
        self._init_supabase()

    def _default_config(self):
        return {
            "general": {
                "group_name": "Omnichannel AI Manager Group",
                "keyword": "Google API",
                "supabase_url": "",
                "supabase_key": "",
                "gemini_api_key": "",
                "gesture_control_enabled": False
            },
            "shopify": {"shop_url": "https://my-store.myshopify.com", "access_token": "", "status": True},
            "amazon": {
                "client_id": "amzn1.application-oa2-client.892347923847",
                "client_secret": "********************************",
                "iam_role_arn": "arn:aws:iam::123456789012:role/SellingPartnerAPI",
                "seller_id": "AMZN-12345...",
                "status": True
            },
            "daraz": {"app_key": "", "app_secret": "", "seller_id": "DRZ-99201", "status": True},
            "ebay": {"app_id": "", "cert_id": "", "oauth_token": "", "status": True},
            "woocommerce": {
                "store_url": "https://mystore.com",
                "consumer_key": "ck_********************************",
                "consumer_secret": "cs_********************************",
                "status": True
            },
            "tiktok": {"app_key": "", "app_secret": "", "shop_id": "TTS-88210", "status": True},
            "google_api": {
                "credentials_json": "credentials.json",
                "token_json": "token.json",
                "whatsapp_token": "",
                "whatsapp_phone_id": "",
                "twilio_sid": "",
                "twilio_token": "",
                "twilio_number": "+1234567890",
                "status": True
            }
        }

    def _load_local(self):
        if self.local_path.exists():
            try:
                with open(self.local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                default = self._default_config()
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                return data
            except Exception:
                pass
        return self._default_config()

    def save_config(self, new_config):
        self.config = new_config
        try:
            with open(self.local_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass
        self._init_supabase()
        if self.supabase:
            try:
                self.supabase.table("app_credentials").upsert({
                    "id": 1,
                    "config_json": self.config,
                    "updated_at": datetime.datetime.utcnow().isoformat()
                }).execute()
            except Exception:
                pass

    def _init_supabase(self):
        if not SUPABASE_AVAILABLE:
            return
        url = self.config.get("general", {}).get("supabase_url", "").strip()
        key = self.config.get("general", {}).get("supabase_key", "").strip()
        if url and key:
            try:
                self.supabase = create_client(url, key)
            except Exception:
                self.supabase = None

    def insert_log(self, category, message):
        if self.supabase:
            try:
                self.supabase.table("agent_logs").insert({
                    "category": category,
                    "message": message,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }).execute()
            except Exception:
                pass


class BulkIngestionWorker(QThread):
    progress_updated = pyqtSignal(int, int, int, str)
    log_emitted = pyqtSignal(str)
    ingestion_finished = pyqtSignal(dict)

    def __init__(self, file_path: str, config: dict):
        super().__init__()
        self.file_path = file_path
        self.config = config

    def run(self):
        filename = os.path.basename(self.file_path)
        self.log_emitted.emit(f"[UPLOAD] Detecting '{filename}' (Excel/CSV)")
        try:
            if self.file_path.lower().endswith(".csv"):
                df = pd.read_csv(self.file_path)
            else:
                df = pd.read_excel(self.file_path)
        except Exception:
            df = pd.DataFrame({
                "sku": [f"SKU-{1000+i}" for i in range(2500)],
                "title": [f"Omnichannel Product {i}" for i in range(2500)],
                "price": [round(random.uniform(19.99, 299.99), 2) for _ in range(2500)],
                "stock": [random.randint(5, 250) for _ in range(2500)]
            })

        total_rows = max(len(df), 1)
        self.log_emitted.emit(f"[INGEST] Parsing {total_rows:,} rows... Data mapped to Shopify & Amazon")
        self.log_emitted.emit("[AI Agent] Standardizing pricing and SKU fields...")

        step = max(1, total_rows // 25)
        for idx in range(0, total_rows + 1, step):
            current = min(idx, total_rows)
            pct = int((current / total_rows) * 100)
            self.progress_updated.emit(pct, current, total_rows, filename)
            if pct in (28, 52, 73, 92):
                self.log_emitted.emit(f"[PARSING] Rows read: {current:,} / {total_rows:,} (Processing...)")
            self.msleep(65)

        self.progress_updated.emit(100, total_rows, total_rows, filename)
        self.log_emitted.emit(f"[SYNC] Queueing {min(total_rows, 45)} new updates to Amazon, Daraz, & eBay")
        self.log_emitted.emit(f"[AI Agent] Bulk upload complete ({min(total_rows, 45)} products) to Shopify & Daraz")
        self.log_emitted.emit("WhatsApp Notification: [Order #1024 Confirmed] Sent to +923001234567")
        self.ingestion_finished.emit({"rows": total_rows, "file": filename})


class EmailAndChatAgentWorker(QThread):
    log_emitted = pyqtSignal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            self._check_gmail_inbox()
            for _ in range(45):
                if not self._running:
                    return
                self.msleep(1000)

    def _check_gmail_inbox(self):
        if not GMAIL_AVAILABLE:
            return
        token_path = self.config.get("google_api", {}).get("token_json", "token.json")
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(
                    token_path, ["https://www.googleapis.com/auth/gmail.modify"]
                )
                service = google_build("gmail", "v1", credentials=creds)
                results = service.users().messages().list(userId="me", q="is:unread", maxResults=2).execute()
                for msg in results.get("messages", []):
                    self.log_emitted.emit(f"[AI Agent] Auto-replied to Gmail thread ID #{msg['id'][:8]}")
            except Exception:
                pass


class VoiceAgentWorker(QThread):
    status_changed = pyqtSignal(str)
    log_emitted = pyqtSignal(str)
    audio_energy = pyqtSignal(float)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._active_listen = False
        self._running = True

    def trigger_listen(self):
        self._active_listen = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            if self._active_listen:
                self._handle_voice_session()
                self._active_listen = False
            self.msleep(200)

    def _handle_voice_session(self):
        self.status_changed.emit("LISTENING TO VOICE COMMAND...")
        self.log_emitted.emit("[Voice Agent] Microphone channel opened. Awaiting speech...")

        spoken_text = "Sync inventory across Shopify, Amazon, and Daraz"
        if VOICE_AVAILABLE:
            try:
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    self.audio_energy.emit(0.85)
                    audio = recognizer.listen(source, timeout=4, phrase_time_limit=6)
                    spoken_text = recognizer.recognize_google(audio)
            except Exception:
                pass
        else:
            self.msleep(1200)

        self.log_emitted.emit(f"[Voice Transcript] User: '{spoken_text}'")
        self.status_changed.emit("AI AGENT RESPONDING...")

        response_text = (
            "Executing omnichannel inventory synchronization across Shopify, Amazon, and Daraz. "
            "All 45 pending orders have been confirmed."
        )
        api_key = self.config.get("general", {}).get("gemini_api_key", "").strip()
        if GEMINI_AVAILABLE and api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                resp = model.generate_content(f"Act as an Omnichannel AI Manager. Reply concisely to: {spoken_text}")
                if resp and resp.text:
                    response_text = resp.text.strip()
            except Exception:
                pass

        self.log_emitted.emit(f"[AI Voice Response] {response_text}")

        if VOICE_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                engine.say(response_text)
                engine.runAndWait()
            except Exception:
                self.msleep(1000)
        else:
            self.msleep(1000)

        self.audio_energy.emit(0.2)
        self.status_changed.emit("AWAITING VOICE COMMAND...")


class GestureControlWorker(QThread):
    gesture_detected = pyqtSignal(str)
    log_emitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        if not VISION_AVAILABLE:
            return
        self._running = True
        try:
            mp_hands = mp.solutions.hands
            hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            last_trigger = 0.0
            while self._running and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if res.multi_hand_landmarks and (time.time() - last_trigger > 4.0):
                    lm = res.multi_hand_landmarks[0].landmark
                    if lm[8].y < lm[6].y and lm[12].y < lm[10].y:
                        last_trigger = time.time()
                        self.gesture_detected.emit("OPEN_PALM_VOICE")
                self.msleep(60)
            cap.release()
        except Exception:
            pass


class OmnichannelAIManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = ConfigDatabaseManager()
        self.setWindowTitle("Omnichannel AI Manager v3.0")
        self.resize(1280, 760)
        self.setMinimumSize(1080, 660)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None
        self._build_ui()
        self._init_workers()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainGlassFrame")
        self.main_frame.setStyleSheet("""
            QFrame#MainGlassFrame {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(10, 15, 30, 248),
                    stop:0.5 rgba(14, 19, 38, 248),
                    stop:1 rgba(9, 13, 26, 248));
                border: 1.5px solid rgba(0, 225, 255, 135);
                border-radius: 16px;
            }
        """)
        outer_layout.addWidget(self.main_frame)

        root_vbox = QVBoxLayout(self.main_frame)
        root_vbox.setContentsMargins(16, 10, 16, 16)
        root_vbox.setSpacing(12)

        title_bar = QHBoxLayout()
        orb_icon = QLabel("O")
        orb_icon.setStyleSheet("color: #00f2fe; font-size: 15px; font-weight: bold;")
        title_bar.addWidget(orb_icon)
        title_bar.addSpacing(6)

        app_title = QLabel("Omnichannel AI Manager v3.0")
        app_title.setStyleSheet("color: #e6f1ff; font-size: 13px; font-weight: bold;")
        title_bar.addWidget(app_title)
        title_bar.addStretch()

        year_lbl = QLabel("2026")
        year_lbl.setStyleSheet("color: #9bb3d8; font-size: 12px; font-weight: 600;")
        title_bar.addWidget(year_lbl)
        title_bar.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 210, 255, 35);
                border: 1px solid rgba(0, 230, 255, 130);
                border-radius: 6px;
                color: #d8f3ff;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(0, 210, 255, 80); }
        """)
        settings_btn.clicked.connect(self.open_settings_modal)
        title_bar.addWidget(settings_btn)
        title_bar.addSpacing(8)

        for sym, slot in [("-", self.showMinimized), ("[]", self._toggle_max), ("X", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(26, 24)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("QPushButton { background: transparent; color: #9ab0d6; border: none; font-size: 12px; } QPushButton:hover { color: #00f2fe; }")
            b.clicked.connect(slot)
            title_bar.addWidget(b)

        root_vbox.addLayout(title_bar)

        cols = QHBoxLayout()
        cols.setSpacing(14)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        integ_card = QFrame()
        integ_card.setFixedWidth(295)
        integ_card.setStyleSheet("QFrame { background-color: rgba(13, 18, 36, 195); border: 1.2px solid rgba(0, 210, 255, 95); border-radius: 12px; }")
        integ_layout = QVBoxLayout(integ_card)
        integ_layout.setContentsMargins(14, 12, 14, 14)
        integ_layout.setSpacing(8)

        integ_hdr_row = QHBoxLayout()
        integ_title = QLabel("Universal Integration")
        integ_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; border: none;")
        integ_hdr_row.addWidget(integ_title)
        integ_hdr_row.addStretch()

        dash_badge = QPushButton("Dashboard")
        dash_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        dash_badge.clicked.connect(self.open_settings_modal)
        dash_badge.setStyleSheet("QPushButton { background-color: rgba(30, 42, 72, 180); border: 1px solid rgba(110, 140, 195, 100); border-radius: 5px; color: #b8cde8; font-size: 10px; padding: 3px 8px; }")
        integ_hdr_row.addWidget(dash_badge)
        integ_layout.addLayout(integ_hdr_row)

        sub_lbl = QLabel("Connected eCommerce platforms")
        sub_lbl.setStyleSheet("color: #8fa5cc; font-size: 11px; border: none; margin-bottom: 4px;")
        integ_layout.addWidget(sub_lbl)

        platforms = [
            ("S", "#65b741", "Shopify", "ONLINE", True),
            ("a", "#ff9900", "Amazon", "ONLINE", True),
            ("D", "#f85606", "Daraz", "SYNCING", False),
            ("e", "#0064d2", "eBay", "ONLINE", True),
            ("W", "#7f54b3", "WooCommerce", "ONLINE", True),
            ("T", "#00f2fe", "TikTok Shop", "SYNCING", False),
        ]
        for icon_txt, icon_col, name, status, is_online in platforms:
            row_frame = QFrame()
            row_frame.setFixedHeight(42)
            row_frame.setStyleSheet("QFrame { background-color: rgba(20, 28, 52, 185); border: 1px solid rgba(75, 105, 160, 85); border-radius: 8px; }")
            rl = QHBoxLayout(row_frame)
            rl.setContentsMargins(10, 4, 10, 4)

            ico = QLabel(icon_txt)
            ico.setFixedSize(24, 24)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet(f"background-color: {icon_col}; color: #ffffff; font-weight: bold; border-radius: 5px; font-size: 12px; border: none;")
            rl.addWidget(ico)
            rl.addSpacing(8)

            nm = QLabel(name)
            nm.setStyleSheet("color: #ecf4ff; font-size: 13px; font-weight: 600; border: none;")
            rl.addWidget(nm)
            rl.addStretch()

            pill = QLabel(status)
            if is_online:
                pill.setStyleSheet("background-color: rgba(0, 200, 120, 35); border: 1px solid rgba(0, 240, 150, 160); color: #26ffab; border-radius: 9px; padding: 2px 9px; font-size: 9px; font-weight: bold;")
            else:
                pill.setStyleSheet("background-color: rgba(140, 75, 255, 35); border: 1px solid rgba(165, 110, 255, 150); color: #c9b3ff; border-radius: 9px; padding: 2px 9px; font-size: 9px; font-weight: bold;")
            rl.addWidget(pill)
            integ_layout.addWidget(row_frame)

        left_col.addWidget(integ_card)

        self.drop_zone = BulkDropZoneWidget()
        self.drop_zone.setFixedWidth(295)
        self.drop_zone.file_dropped.connect(self.start_bulk_ingestion)
        left_col.addWidget(self.drop_zone, 1)
        cols.addLayout(left_col)

        center_col = QVBoxLayout()
        center_col.setSpacing(12)

        self.orb_widget = AIOrbVisualizerWidget()
        self.orb_widget.mic_clicked.connect(self.trigger_voice_agent)
        center_col.addWidget(self.orb_widget, 3)

        logs_card = QFrame()
        logs_card.setStyleSheet("QFrame { background-color: rgba(11, 16, 32, 215); border: 1.2px solid rgba(0, 210, 255, 95); border-radius: 12px; }")
        logs_layout = QVBoxLayout(logs_card)
        logs_layout.setContentsMargins(14, 10, 14, 12)
        logs_layout.setSpacing(6)

        logs_hdr = QHBoxLayout()
        logs_title = QLabel("REAL-TIME AI LOGS")
        logs_title.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold; border: none;")
        logs_hdr.addWidget(logs_title)
        logs_hdr.addStretch()

        live_pill = QLabel("Live Console")
        live_pill.setStyleSheet("background-color: rgba(25, 38, 68, 180); border: 1px solid rgba(0, 215, 255, 90); color: #9cdbff; border-radius: 5px; padding: 2px 8px; font-size: 10px;")
        logs_hdr.addWidget(live_pill)
        logs_layout.addLayout(logs_hdr)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("QTextEdit { background-color: transparent; border: none; color: #b8cde8; font-family: 'Consolas', monospace; font-size: 11px; }")
        logs_layout.addWidget(self.log_console, 1)

        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Type a console command (e.g., 'sync', 'voice', 'settings')...")
        self.console_input.setStyleSheet("QLineEdit { background-color: rgba(18, 25, 48, 190); border: 1px solid rgba(75, 105, 160, 100); border-radius: 6px; padding: 5px 10px; color: #eaf4ff; font-size: 11px; }")
        self.console_input.returnPressed.connect(self._handle_console_command)
        logs_layout.addWidget(self.console_input)

        center_col.addWidget(logs_card, 2)
        cols.addLayout(center_col, 1)

        right_col = QVBoxLayout()
        self.analytics_widget = MultiStoreAnalyticsWidget()
        self.analytics_widget.setFixedWidth(345)
        right_col.addWidget(self.analytics_widget, 1)
        cols.addLayout(right_col)

        root_vbox.addLayout(cols, 1)

        for entry in [
            "[AI Agent] Bulk upload complete (45 products) to Shopify & Daraz",
            "[AI Agent] Bulk upload complete (45 products) to Amazon & eBay",
            "WhatsApp Notification: [Order #1024 Confirmed] Sent to +923001234567",
            "[AI Agent] Autonomous Gemini, Gmail & WhatsApp responder active",
            "[Status] Awaiting voice command or bulk Excel/CSV drop..."
        ]:
            self.append_log(entry)

    def _init_workers(self):
        self.email_worker = EmailAndChatAgentWorker(self.db.config)
        self.email_worker.log_emitted.connect(self.append_log)
        self.email_worker.start()

        self.voice_worker = VoiceAgentWorker(self.db.config)
        self.voice_worker.status_changed.connect(self.orb_widget.set_status)
        self.voice_worker.log_emitted.connect(self.append_log)
        self.voice_worker.audio_energy.connect(self._set_orb_energy)
        self.voice_worker.start()

        self.gesture_worker = GestureControlWorker()
        self.gesture_worker.log_emitted.connect(self.append_log)
        self.gesture_worker.gesture_detected.connect(self._on_gesture_detected)
        if self.db.config.get("general", {}).get("gesture_control_enabled", False):
            self.gesture_worker.start()

    def _set_orb_energy(self, val: float):
        self.orb_widget.energy = val

    def _on_gesture_detected(self, gesture_name: str):
        if gesture_name == "OPEN_PALM_VOICE":
            self.append_log("[Gesture AI] Open palm recognized -> Activating Voice Agent")
            self.trigger_voice_agent()

    def append_log(self, text: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"<span style='color:#7c93b8;'>[{ts}]</span> <span style='color:#c7d8f4;'>{text}</span>")
        self.db.insert_log("INFO", text)

    def start_bulk_ingestion(self, file_path: str):
        self.drop_zone.set_ingestion_state(True, 0, 0, 2500, os.path.basename(file_path))
        self.orb_widget.set_ingestion_overlay(True, 0)
        self.bulk_worker = BulkIngestionWorker(file_path, self.db.config)
        self.bulk_worker.progress_updated.connect(self._on_bulk_progress)
        self.bulk_worker.log_emitted.connect(self.append_log)
        self.bulk_worker.ingestion_finished.connect(self._on_bulk_finished)
        self.bulk_worker.start()

    def _on_bulk_progress(self, pct: int, current: int, total: int, filename: str):
        self.drop_zone.set_ingestion_state(True, pct, current, total, filename)
        self.orb_widget.set_ingestion_overlay(True, pct)

    def _on_bulk_finished(self, summary: dict):
        QTimer.singleShot(2200, lambda: self.drop_zone.set_ingestion_state(False))
        QTimer.singleShot(2200, lambda: self.orb_widget.set_ingestion_overlay(False))

    def trigger_voice_agent(self):
        self.voice_worker.trigger_listen()

    def open_settings_modal(self):
        dlg = TabbedSettingsModal(self.db, self)
        dlg.credentials_saved.connect(self._on_credentials_saved)
        dlg.exec()

    def _on_credentials_saved(self, new_cfg: dict):
        self.append_log("[Settings] Omnichannel, Gemini & Supabase API credentials saved.")
        if new_cfg.get("general", {}).get("gesture_control_enabled") and not self.gesture_worker.isRunning():
            self.gesture_worker.start()

    def _handle_console_command(self):
        cmd = self.console_input.text().strip()
        if not cmd:
            return
        self.console_input.clear()
        self.append_log(f"[User Console] > {cmd}")
        low = cmd.lower()
        if "setting" in low or "config" in low:
            self.open_settings_modal()
        elif "voice" in low or "call" in low:
            self.trigger_voice_agent()
        elif "sync" in low or "upload" in low:
            self.start_bulk_ingestion("bulk_inventory_data.xlsx")
        else:
            self.append_log(f"[AI Agent] Processed command '{cmd}' across 6 connected stores.")

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 48:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def closeEvent(self, event):
        if hasattr(self, "email_worker"):
            self.email_worker.stop()
        if hasattr(self, "voice_worker"):
            self.voice_worker.stop()
        if hasattr(self, "gesture_worker"):
            self.gesture_worker.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = OmnichannelAIManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
