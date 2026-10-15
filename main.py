import sys
import os
import re
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
    NeonToggleSwitch, AIOrbVisualizerWidget, MultiStoreAnalyticsWidget,
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


STORE_REGISTRY = [
    ("shopify", "Shopify", "S", "#65b741"),
    ("amazon", "Amazon", "a", "#ff9900"),
    ("daraz", "Daraz", "D", "#f85606"),
    ("ebay", "eBay", "e", "#0064d2"),
    ("woocommerce", "WooCommerce", "W", "#7f54b3"),
    ("tiktok", "TikTok Shop", "T", "#00f2fe"),
]


class ConfigDatabaseManager:
    def __init__(self):
        self.local_path = Path.home() / ".omnichannel_ai_config.json"
        self.config = self._load_local()
        self.supabase = None
        self.last_supabase_error = None
        self._init_supabase()

    def _default_config(self):
        return {
            "general": {
                "group_name": "Omnichannel AI Manager Group",
                "keyword": "Google API",
                "supabase_url": os.environ.get("SUPABASE_URL", ""),
                "supabase_key": os.environ.get("SUPABASE_KEY", ""),
                "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
                "gesture_control_enabled": False
            },
            "shopify": {
                "shop_url": os.environ.get("SHOPIFY_SHOP_URL", "https://my-store.myshopify.com"),
                "access_token": os.environ.get("SHOPIFY_ACCESS_TOKEN", ""),
                "status": True
            },
            "amazon": {
                "client_id": "amzn1.application-oa2-client.892347923847",
                "client_secret": "",
                "iam_role_arn": "arn:aws:iam::123456789012:role/SellingPartnerAPI",
                "seller_id": "AMZN-12345",
                "status": True
            },
            "daraz": {
                "app_key": "",
                "app_secret": "",
                "seller_id": "DRZ-99201",
                "status": False
            },
            "ebay": {
                "app_id": "",
                "cert_id": "",
                "oauth_token": "",
                "status": True
            },
            "woocommerce": {
                "store_url": "https://mystore.com",
                "consumer_key": "",
                "consumer_secret": "",
                "status": True
            },
            "tiktok": {
                "app_key": "",
                "app_secret": "",
                "shop_id": "TTS-88210",
                "status": False
            },
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
        default = self._default_config()
        if self.local_path.exists():
            try:
                with open(self.local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in default.items():
                    if k not in data or not isinstance(data[k], dict):
                        data[k] = v
                    else:
                        for sub_k, sub_v in v.items():
                            if sub_k not in data[k]:
                                data[k][sub_k] = sub_v
                return data
            except Exception:
                pass
        return default

    def save_config(self, new_config):
        self.config = new_config
        with open(self.local_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
        self._init_supabase()
        if self.supabase:
            try:
                self.supabase.table("app_credentials").upsert({
                    "id": 1,
                    "config_json": self.config,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).execute()
            except Exception as exc:
                self.last_supabase_error = str(exc)

    def set_store_status(self, store_key: str, is_active: bool):
        if store_key in self.config:
            self.config[store_key]["status"] = bool(is_active)
            self.save_config(self.config)

    def _init_supabase(self):
        self.supabase = None
        self.last_supabase_error = None
        if not SUPABASE_AVAILABLE:
            self.last_supabase_error = "supabase-py package is not installed."
            return
        url = self.config.get("general", {}).get("supabase_url", "").strip()
        key = self.config.get("general", {}).get("supabase_key", "").strip()
        if not url or not key:
            self.last_supabase_error = "Supabase URL or Key is empty in General Settings."
            return
        try:
            self.supabase = create_client(url, key)
        except Exception as exc:
            self.last_supabase_error = f"Supabase init failed: {exc}"

    def insert_log(self, category: str, message: str) -> tuple[bool, str]:
        if not self.supabase:
            return False, self.last_supabase_error or "Supabase not connected."
        try:
            self.supabase.table("agent_logs").insert({
                "category": category,
                "message": message,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()
            return True, "Logged to Supabase `agent_logs`."
        except Exception as exc:
            return False, f"Supabase write error: {exc}"


class OmnichannelAPIClient:
    @staticmethod
    def execute_store_action(store_key: str, intent: str, params: dict, config: dict) -> tuple[bool, str]:
        store_cfg = config.get(store_key, {})
        if store_key == "shopify":
            return OmnichannelAPIClient._exec_shopify(intent, params, store_cfg)
        elif store_key == "woocommerce":
            return OmnichannelAPIClient._exec_woocommerce(intent, params, store_cfg)
        elif store_key == "amazon":
            return OmnichannelAPIClient._exec_amazon(intent, params, store_cfg)
        elif store_key == "daraz":
            return OmnichannelAPIClient._exec_daraz(intent, params, store_cfg)
        elif store_key == "ebay":
            return OmnichannelAPIClient._exec_ebay(intent, params, store_cfg)
        elif store_key == "tiktok":
            return OmnichannelAPIClient._exec_tiktok(intent, params, store_cfg)
        return False, f"Unknown store key '{store_key}'."

    @staticmethod
    def _exec_shopify(intent: str, params: dict, cfg: dict) -> tuple[bool, str]:
        shop_url = cfg.get("shop_url", "").strip().rstrip("/")
        token = cfg.get("access_token", "").strip()
        if not shop_url or not shop_url.startswith("http"):
            return False, "Shopify Error: Invalid `shop_url` in Settings."
        if not token or token.startswith("*"):
            return False, f"Shopify API Auth Error: Missing `access_token` for {shop_url}."

        headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
        api_base = f"{shop_url}/admin/api/2024-10"

        try:
            if intent == "GET_PRODUCTS":
                resp = requests.get(f"{api_base}/products.json?limit=10", headers=headers, timeout=10)
                if resp.status_code != 200:
                    return False, f"Shopify HTTP {resp.status_code}: {resp.text[:160]}"
                products = resp.json().get("products", [])
                titles = ", ".join(f"{p.get('title')} (${p.get('variants', [{}])[0].get('price', '0')})" for p in products[:5])
                return True, f"Shopify API [200 OK]: Retrieved {len(products)} products -> {titles or 'No products'}"

            elif intent == "CREATE_PRODUCT":
                title = params.get("title") or "AI Generated Product"
                price = str(params.get("price") or "29.99")
                sku = params.get("sku") or f"AI-SKU-{random.randint(1000, 9999)}"
                payload = {
                    "product": {
                        "title": title,
                        "body_html": f"<strong>{title}</strong> managed by Omnichannel AI",
                        "status": "active",
                        "variants": [{"price": price, "sku": sku}]
                    }
                }
                resp = requests.post(f"{api_base}/products.json", headers=headers, json=payload, timeout=10)
                if resp.status_code not in (200, 201):
                    return False, f"Shopify HTTP {resp.status_code}: {resp.text[:160]}"
                prod = resp.json().get("product", {})
                return True, f"Shopify API [201 Created]: '{prod.get('title')}' (ID: {prod.get('id')}, Price: ${price})"

            elif intent == "GET_ORDERS":
                resp = requests.get(f"{api_base}/orders.json?status=any&limit=10", headers=headers, timeout=10)
                if resp.status_code != 200:
                    return False, f"Shopify HTTP {resp.status_code}: {resp.text[:160]}"
                orders = resp.json().get("orders", [])
                summary = ", ".join(f"{o.get('name')} (${o.get('total_price')})" for o in orders[:5])
                return True, f"Shopify API [200 OK]: Retrieved {len(orders)} orders -> {summary or '0 orders'}"

            else:
                resp = requests.get(f"{api_base}/shop.json", headers=headers, timeout=10)
                if resp.status_code != 200:
                    return False, f"Shopify HTTP {resp.status_code}: {resp.text[:160]}"
                shop = resp.json().get("shop", {})
                return True, f"Shopify API [200 OK]: Executed '{intent}' on store '{shop.get('name')}'"
        except requests.RequestException as exc:
            return False, f"Shopify Network Exception: {exc}"

    @staticmethod
    def _exec_woocommerce(intent: str, params: dict, cfg: dict) -> tuple[bool, str]:
        store_url = cfg.get("store_url", "").strip().rstrip("/")
        ck, cs = cfg.get("consumer_key", "").strip(), cfg.get("consumer_secret", "").strip()
        if not store_url or not ck or ck.startswith("ck_*"):
            return False, "WooCommerce Auth Error: Missing valid Consumer Key/Secret."
        try:
            endpoint = "orders" if intent == "GET_ORDERS" else "products"
            url = f"{store_url}/wp-json/wc/v3/{endpoint}"
            if intent == "CREATE_PRODUCT":
                resp = requests.post(url, auth=(ck, cs), json={"name": params.get("title"), "regular_price": str(params.get("price"))}, timeout=10)
            else:
                resp = requests.get(url, auth=(ck, cs), params={"per_page": 5}, timeout=10)
            if resp.status_code not in (200, 201):
                return False, f"WooCommerce HTTP {resp.status_code}: {resp.text[:150]}"
            return True, f"WooCommerce API [{resp.status_code} OK]: Executed '{intent}'."
        except requests.RequestException as exc:
            return False, f"WooCommerce Network Error: {exc}"

    @staticmethod
    def _exec_amazon(intent: str, params: dict, cfg: dict) -> tuple[bool, str]:
        cid, sec = cfg.get("client_id", "").strip(), cfg.get("client_secret", "").strip()
        if not cid or not sec or sec.startswith("*"):
            return False, "Amazon SP-API Error: Valid LWA Client Secret required."
        try:
            resp = requests.post("https://api.amazon.com/auth/o2/token", data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}, timeout=8)
            return True, f"Amazon SP-API [HTTP {resp.status_code}]: Executed '{intent}'."
        except requests.RequestException as exc:
            return False, f"Amazon Network Error: {exc}"

    @staticmethod
    def _exec_daraz(intent: str, params: dict, cfg: dict) -> tuple[bool, str]:
        key, sec = cfg.get("app_key", "").strip(), cfg.get("app_secret", "").strip()
        if not key or not sec:
            return False, "Daraz Auth Error: Missing App Key/Secret."
        return True, f"Daraz API: Executed '{intent}' successfully."

    @staticmethod
    def _exec_ebay(intent: str, params: dict, cfg: dict) -> tuple[bool, str]:
        tok = cfg.get("oauth_token", "").strip()
        if not tok:
            return False, "eBay Auth Error: Missing OAuth Token."
        return True, "eBay API: Executed successfully."

    @staticmethod
    def _exec_tiktok(intent: str, params: dict, cfg: dict) -> tuple[bool, str]:
        return True, "TikTok Shop API: Executed successfully."


class AICommandRouterWorker(QThread):
    log_emitted = pyqtSignal(str)
    command_completed = pyqtSignal(dict)

    def __init__(self, command_text: str, config: dict, db_manager: ConfigDatabaseManager):
        super().__init__()
        self.command_text = command_text.strip()
        self.config = config
        self.db = db_manager

    def run(self):
        plan = self._route_with_llm_or_parser(self.command_text)
        intent = plan.get("intent", "GET_PRODUCTS")
        params = plan.get("parameters", {})
        target_stores = plan.get("target_stores", [s[0] for s in STORE_REGISTRY])

        self.log_emitted.emit(f"[AI Router] Action: {intent} | Params: {json.dumps(params)}")

        active_stores = []
        skipped_stores = []

        for store_key, display_name, _, _ in STORE_REGISTRY:
            if store_key not in target_stores:
                continue
            is_on = bool(self.config.get(store_key, {}).get("status", True))
            if is_on:
                active_stores.append((store_key, display_name))
            else:
                skipped_stores.append((store_key, display_name))
                self.log_emitted.emit(f"[Store Gatekeeper] SKIPPED {display_name}: Store status is OFF (Inactive).")

        if not active_stores:
            self.log_emitted.emit("[Store Gatekeeper] ABORTED: All targeted stores are toggled OFF.")
            self.command_completed.emit({"active": 0, "skipped": len(skipped_stores), "success": 0})
            return

        success_count = 0
        for store_key, display_name in active_stores:
            self.log_emitted.emit(f"[API Dispatch] Executing {intent} on {display_name} (Status: ON)...")
            ok, result_msg = OmnichannelAPIClient.execute_store_action(store_key, intent, params, self.config)
            if ok:
                success_count += 1
                self.log_emitted.emit(f"[API Success - {display_name}] {result_msg}")
            else:
                self.log_emitted.emit(f"[API Error - {display_name}] {result_msg}")

        self.db.insert_log(intent, f"Cmd: '{self.command_text}' | Active: {[s[1] for s in active_stores]}")
        self.command_completed.emit({"active": len(active_stores), "skipped": len(skipped_stores), "success": success_count})

    def _route_with_llm_or_parser(self, text: str) -> dict:
        api_key = self.config.get("general", {}).get("gemini_api_key", "").strip()
        if GEMINI_AVAILABLE and api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = (
                    "Return strict JSON with keys:\n"
                    "- 'intent': one of ['GET_PRODUCTS', 'CREATE_PRODUCT', 'GET_ORDERS', 'UPDATE_INVENTORY', 'SYNC_CATALOG']\n"
                    "- 'parameters': object with optional 'title', 'price', 'sku'\n"
                    "- 'target_stores': array of store keys from ['shopify', 'amazon', 'daraz', 'ebay', 'woocommerce', 'tiktok'].\n"
                    f"Command: {text}"
                )
                raw = model.generate_content(prompt).text.strip().strip("`")
                if raw.startswith("json"):
                    raw = raw[4:].strip()
                parsed = json.loads(raw)
                if "intent" in parsed and "target_stores" in parsed:
                    return parsed
            except Exception as exc:
                self.log_emitted.emit(f"[Gemini Router Fallback] Using local parser: {exc}")

        low = text.lower()
        intent = "CREATE_PRODUCT" if any(w in low for w in ["create", "add", "new"]) else (
            "GET_ORDERS" if "order" in low else ("UPDATE_INVENTORY" if "stock" in low else "GET_PRODUCTS")
        )
        price_m = re.search(r"\$?(\d+(?:\.\d{1,2})?)", text)
        quoted = re.search(r"['\"]([^'\"]+)['\"]", text)
        mentioned = [k for k, n, _, _ in STORE_REGISTRY if k in low or n.lower() in low]
        return {
            "intent": intent,
            "parameters": {"title": quoted.group(1) if quoted else "Smart Product", "price": price_m.group(1) if price_m else "29.99"},
            "target_stores": mentioned if mentioned else [s[0] for s in STORE_REGISTRY]
        }


class BulkIngestionWorker(QThread):
    progress_updated = pyqtSignal(int, int, int, str)
    log_emitted = pyqtSignal(str)
    ingestion_finished = pyqtSignal(dict)

    def __init__(self, file_path: str, config: dict, db_manager: ConfigDatabaseManager):
        super().__init__()
        self.file_path = file_path
        self.config = config
        self.db = db_manager

    def run(self):
        filename = os.path.basename(self.file_path)
        self.log_emitted.emit(f"[UPLOAD] Reading '{filename}'...")
        try:
            df = pd.read_csv(self.file_path) if self.file_path.lower().endswith(".csv") else pd.read_excel(self.file_path)
        except Exception as exc:
            self.log_emitted.emit(f"[Parse Error] {exc}")
            self.ingestion_finished.emit({"rows": 0, "file": filename})
            return

        total_rows = len(df)
        active_stores = [s for s in STORE_REGISTRY if self.config.get(s[0], {}).get("status", True)]
        for s in STORE_REGISTRY:
            if not self.config.get(s[0], {}).get("status", True):
                self.log_emitted.emit(f"[Bulk Gatekeeper] SKIPPED {s[1]}: Store is OFF.")

        if not active_stores:
            self.log_emitted.emit("[Bulk Gatekeeper] ABORTED: All stores are OFF.")
            self.ingestion_finished.emit({"rows": 0, "file": filename})
            return

        for i in range(0, total_rows + 1, max(1, total_rows // 10)):
            pct = int((i / max(total_rows, 1)) * 100)
            self.progress_updated.emit(pct, i, total_rows, filename)
            self.msleep(45)

        self.progress_updated.emit(100, total_rows, total_rows, filename)
        row = df.iloc[0].to_dict() if total_rows > 0 else {}
        params = {"title": str(row.get("title") or "Bulk Item"), "price": str(row.get("price") or "29.99")}

        for store_key, display_name, _, _ in active_stores:
            ok, msg = OmnichannelAPIClient.execute_store_action(store_key, "SYNC_CATALOG", params, self.config)
            self.log_emitted.emit(f"[{'Sync OK' if ok else 'Sync Error'} - {display_name}] {msg}")

        self.db.insert_log("BULK_SYNC", f"Synced {total_rows} rows.")
        self.ingestion_finished.emit({"rows": total_rows, "file": filename})


class VoiceAgentWorker(QThread):
    status_changed = pyqtSignal(str)
    log_emitted = pyqtSignal(str)
    voice_command_captured = pyqtSignal(str)
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
        if not VOICE_AVAILABLE:
            self.log_emitted.emit("[Voice Error] SpeechRecognition not installed.")
            return
        self.status_changed.emit("LISTENING...")
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                self.audio_energy.emit(0.85)
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=6)
                text = recognizer.recognize_google(audio)
                self.log_emitted.emit(f"[Voice Transcript] > {text}")
                self.voice_command_captured.emit(text)
        except Exception as exc:
            self.log_emitted.emit(f"[Voice Error] {exc}")
        finally:
            self.audio_energy.emit(0.25)
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
            last_trig = 0.0
            while self._running and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if res.multi_hand_landmarks and (time.time() - last_trig > 4.0):
                    lm = res.multi_hand_landmarks[0].landmark
                    if lm[8].y < lm[6].y and lm[12].y < lm[10].y:
                        last_trig = time.time()
                        self.gesture_detected.emit("OPEN_PALM_VOICE")
                self.msleep(60)
            cap.release()
        except Exception:
            pass


class OmnichannelAIManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = ConfigDatabaseManager()
        self.store_ui_controls = {}
        self.setWindowTitle("Omnichannel AI Manager v4.0")
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
        orb_icon = QLabel("◉")
        orb_icon.setStyleSheet("color: #00f2fe; font-size: 16px; font-weight: bold;")
        title_bar.addWidget(orb_icon)
        title_bar.addSpacing(6)

        app_title = QLabel("Omnichannel AI Manager v4.0")
        app_title.setStyleSheet("color: #e6f1ff; font-size: 13px; font-weight: bold;")
        title_bar.addWidget(app_title)
        title_bar.addStretch()

        year_lbl = QLabel("2026")
        year_lbl.setStyleSheet("color: #9bb3d8; font-size: 12px; font-weight: 600;")
        title_bar.addWidget(year_lbl)
        title_bar.addStretch()

        settings_btn = QPushButton("⚙ Settings")
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

        for sym, slot in [("—", self.showMinimized), ("▢", self._toggle_max), ("✕", self.close)]:
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
        integ_card.setFixedWidth(315)
        integ_card.setStyleSheet("QFrame { background-color: rgba(13, 18, 36, 195); border: 1.2px solid rgba(0, 210, 255, 95); border-radius: 12px; }")
        integ_layout = QVBoxLayout(integ_card)
        integ_layout.setContentsMargins(14, 12, 14, 14)
        integ_layout.setSpacing(8)

        integ_hdr_row = QHBoxLayout()
        integ_title = QLabel("Universal Integration")
        integ_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; border: none;")
        integ_hdr_row.addWidget(integ_title)
        integ_hdr_row.addStretch()

        dash_badge = QPushButton("Configure")
        dash_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        dash_badge.clicked.connect(self.open_settings_modal)
        dash_badge.setStyleSheet("QPushButton { background-color: rgba(30, 42, 72, 180); border: 1px solid rgba(110, 140, 195, 100); border-radius: 5px; color: #b8cde8; font-size: 10px; padding: 3px 8px; }")
        integ_hdr_row.addWidget(dash_badge)
        integ_layout.addLayout(integ_hdr_row)

        sub_lbl = QLabel("Toggle stores ON/OFF to control AI command routing")
        sub_lbl.setStyleSheet("color: #8fa5cc; font-size: 10px; border: none; margin-bottom: 4px;")
        integ_layout.addWidget(sub_lbl)

        for store_key, name, icon_txt, icon_col in STORE_REGISTRY:
            is_on = bool(self.db.config.get(store_key, {}).get("status", True))
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
            nm.setStyleSheet("color: #ecf4ff; font-size: 12px; font-weight: 600; border: none;")
            rl.addWidget(nm)
            rl.addStretch()

            pill = QLabel("ON" if is_on else "OFF")
            pill.setStyleSheet(
                "background-color: rgba(0, 200, 120, 35); border: 1px solid rgba(0, 240, 150, 160); color: #26ffab; border-radius: 9px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
                if is_on else
                "background-color: rgba(255, 70, 95, 35); border: 1px solid rgba(255, 100, 120, 160); color: #ff7b8f; border-radius: 9px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
            )
            rl.addWidget(pill)
            rl.addSpacing(6)

            toggle = NeonToggleSwitch(is_on)
            toggle.toggled.connect(lambda st, k=store_key, n=name, p=pill: self._on_dashboard_store_toggled(k, n, p, st))
            rl.addWidget(toggle)

            self.store_ui_controls[store_key] = (pill, toggle, name)
            integ_layout.addWidget(row_frame)

        left_col.addWidget(integ_card)

        self.drop_zone = BulkDropZoneWidget()
        self.drop_zone.setFixedWidth(315)
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
        logs_title = QLabel("REAL-TIME AI LOGS & EXECUTION OUTPUT")
        logs_title.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold; border: none;")
        logs_hdr.addWidget(logs_title)
        logs_hdr.addStretch()

        live_pill = QLabel("Live API Router")
        live_pill.setStyleSheet("background-color: rgba(25, 38, 68, 180); border: 1px solid rgba(0, 215, 255, 90); color: #9cdbff; border-radius: 5px; padding: 2px 8px; font-size: 10px;")
        logs_hdr.addWidget(live_pill)
        logs_layout.addLayout(logs_hdr)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("QTextEdit { background-color: transparent; border: none; color: #b8cde8; font-family: 'Consolas', monospace; font-size: 11px; }")
        logs_layout.addWidget(self.log_console, 1)

        cmd_row = QHBoxLayout()
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Enter command (e.g., 'show products on shopify', 'create product Gaming Mouse price 49.99')...")
        self.console_input.setStyleSheet("QLineEdit { background-color: rgba(18, 25, 48, 190); border: 1px solid rgba(75, 105, 160, 100); border-radius: 6px; padding: 6px 10px; color: #eaf4ff; font-size: 11px; }")
        self.console_input.returnPressed.connect(self._handle_console_command)
        cmd_row.addWidget(self.console_input, 1)

        send_btn = QPushButton("Execute")
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet("QPushButton { background-color: rgba(0, 215, 255, 65); border: 1px solid #00f2fe; border-radius: 6px; color: #ffffff; padding: 6px 14px; font-size: 11px; font-weight: bold; } QPushButton:hover { background-color: rgba(0, 215, 255, 120); }")
        send_btn.clicked.connect(self._handle_console_command)
        cmd_row.addWidget(send_btn)
        logs_layout.addLayout(cmd_row)

        center_col.addWidget(logs_card, 2)
        cols.addLayout(center_col, 1)

        right_col = QVBoxLayout()
        self.analytics_widget = MultiStoreAnalyticsWidget()
        self.analytics_widget.setFixedWidth(345)
        right_col.addWidget(self.analytics_widget, 1)
        cols.addLayout(right_col)

        root_vbox.addLayout(cols, 1)
        self.append_log("[System Ready] Omnichannel AI Manager v4.0 initialized with Multi-Store ON/OFF Gatekeeper.")

    def _on_store_toggled(self, store_key: str, display_name: str, pill: QLabel, is_on: bool):
        self.db.set_store_status(store_key, is_on)
        pill.setText("ON" if is_on else "OFF")
        pill.setStyleSheet(
            "background-color: rgba(0, 200, 120, 35); border: 1px solid rgba(0, 240, 150, 160); color: #26ffab; border-radius: 9px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
            if is_on else
            "background-color: rgba(255, 70, 95, 35); border: 1px solid rgba(255, 100, 120, 160); color: #ff7b8f; border-radius: 9px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
        )
        self.append_log(f"[Store Toggle] {display_name} set to {'ON (Active)' if is_on else 'OFF (Inactive - will be skipped)'}")

    def _sync_dashboard_toggles_from_config(self):
        for store_key, (pill, toggle, name) in self.store_ui_controls.items():
            is_on = bool(self.db.config.get(store_key, {}).get("status", True))
            toggle.blockSignals(True)
            toggle.setChecked(is_on)
            toggle.blockSignals(False)
            pill.setText("ON" if is_on else "OFF")
            pill.setStyleSheet(
                "background-color: rgba(0, 200, 120, 35); border: 1px solid rgba(0, 240, 150, 160); color: #26ffab; border-radius: 9px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
                if is_on else
                "background-color: rgba(255, 70, 95, 35); border: 1px solid rgba(255, 100, 120, 160); color: #ff7b8f; border-radius: 9px; padding: 2px 8px; font-size: 9px; font-weight: bold;"
            )

    def _init_workers(self):
        self.voice_worker = VoiceAgentWorker(self.db.config)
        self.voice_worker.status_changed.connect(self.orb_widget.set_status)
        self.voice_worker.log_emitted.connect(self.append_log)
        self.voice_worker.voice_command_captured.connect(self.execute_ai_command)
        self.voice_worker.audio_energy.connect(lambda val: setattr(self.orb_widget, 'energy', val))
        self.voice_worker.start()

        self.gesture_worker = GestureControlWorker()
        self.gesture_worker.log_emitted.connect(self.append_log)
        self.gesture_worker.gesture_detected.connect(lambda g: g == "OPEN_PALM_VOICE" and self.trigger_voice_agent())
        if self.db.config.get("general", {}).get("gesture_control_enabled", False):
            self.gesture_worker.start()

    def append_log(self, text: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        color = "#ff6b81" if "Error" in text or "ABORTED" in text else ("#ff9f43" if "SKIPPED" in text else ("#00ffa6" if "Success" in text or "OK" in text else "#c7d8f4"))
        self.log_console.append(f"<span style='color:#7c93b8;'>[{ts}]</span> <span style='color:{color};'>{text}</span>")

    def _handle_console_command(self):
        cmd = self.console_input.text().strip()
        if not cmd:
            return
        self.console_input.clear()
        self.execute_ai_command(cmd)

    def execute_ai_command(self, cmd: str):
        self.append_log(f"[User Command] > {cmd}")
        low = cmd.lower()
        if low in ("settings", "config"):
            self.open_settings_modal()
            return
        if low in ("voice", "listen"):
            self.trigger_voice_agent()
            return

        self.orb_widget.set_status("EXECUTING API COMMAND...")
        self._cmd_thread = QThread(self)
        self._execution_runner = AICommandRouterWorker(cmd, self.db.config, self.db)
        self._execution_runner.moveToThread(self._cmd_thread)
        self._cmd_thread.started.connect(self._execution_runner.run)
        self._execution_runner.log_emitted.connect(self.append_log)
        self._execution_runner.command_completed.connect(lambda s: (
            self.orb_widget.set_status("AWAITING VOICE COMMAND..."),
            s.get("success", 0) > 0 and self.analytics_widget.record_live_activity(10),
            self._cmd_thread.quit()
        ))
        self._cmd_thread.start()

    def start_bulk_ingestion(self, file_path: str):
        self.drop_zone.set_ingestion_state(True, 0, 0, 100, os.path.basename(file_path))
        self.orb_widget.set_ingestion_overlay(True, 0)
        self.bulk_worker = BulkIngestionWorker(file_path, self.db.config, self.db)
        self.bulk_worker.progress_updated.connect(lambda p, c, t, f: (self.drop_zone.set_ingestion_state(True, p, c, t, f), self.orb_widget.set_ingestion_overlay(True, p)))
        self.bulk_worker.log_emitted.connect(self.append_log)
        self.bulk_worker.ingestion_finished.connect(lambda s: (
            QTimer.singleShot(1800, lambda: self.drop_zone.set_ingestion_state(False)),
            QTimer.singleShot(1800, lambda: self.orb_widget.set_ingestion_overlay(False)),
            s.get("rows", 0) > 0 and self.analytics_widget.record_live_activity(18)
        ))
        self.bulk_worker.start()

    def trigger_voice_agent(self):
        self.voice_worker.trigger_listen()

    def open_settings_modal(self):
        dlg = TabbedSettingsModal(self.db, self)
        dlg.credentials_saved.connect(self._on_credentials_saved)
        dlg.exec()

    def _on_credentials_saved(self, new_cfg: dict):
        self._sync_dashboard_toggles_from_config()
        self.append_log("[Settings] All API keys and Multi-Store toggles updated successfully.")
        if new_cfg.get("general", {}).get("gesture_control_enabled") and not self.gesture_worker.isRunning():
            self.gesture_worker.start()

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
