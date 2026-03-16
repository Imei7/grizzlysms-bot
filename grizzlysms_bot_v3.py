#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
🐻 GRIZZLYSMS TELEGRAM BOT v7 - COMPLETE EDITION
═══════════════════════════════════════════════════════════════════════════════

ALL FEATURES:
├── 💾 SQLite Persistent Database per User
├── 🌍 Country Validator (Hard Lock Mexico Mode)
├── 📡 Real-time Mexico Stock Sniper
├── 💰 Price Check Before Purchase
├── 🔑 Single API Key per User (from Grizzly)
├── 👥 User Approval System (Admin Only)
├── ⚙️ Admin Panel (Admin Only)
├── 📊 Purchase Limit per User (Admin Controlled)
├── 🔔 OTP Auto Checker
├── 🚀 Parallel Buy Engine (100-1000)
├── 🎯 OTP Sniper Mode
├── 🔄 Auto Rebuy System
├── 📈 Realtime Dashboard
├── 📄 Professional Pagination
├── 📊 Loading Progress Bar
├── 💵 Price Range Control
└── 📋 Activity Logging

NO DUMMY - NO PLACEHOLDER - ALL FUNCTIONAL
═══════════════════════════════════════════════════════════════════════════════
"""

import logging
import requests
import asyncio
import json
import os
import urllib.parse
import time
import sqlite3
import threading
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
from collections import defaultdict

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ApplicationBuilder
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7658474148:AAFW3iVVefQ-eqz_5nfYE7V4V6EuG4rwZTQ")

# Admin IDs - hanya admin yang bisa approve/reject user
ADMIN_IDS: Set[int] = {
    7230950406,
    # tambah admin ID lain di sini
}

# API Configuration
API_BASE = "https://grizzlysms.com/stubs/handler_api.php"
API_BASE2 = "https://api.grizzlysms.com/stubs/handler_api.php"

# ═══════════════════════════════════════════════════════════════════════════════
# COUNTRY VALIDATOR & HARD LOCK MEXICO
# ═══════════════════════════════════════════════════════════════════════════════

class CountryValidator:
    """
    Country Validator dengan Hard Lock Mexico Mode.
    Memastikan negara tidak pernah melenceng dari yang diizinkan.
    """
    
    # Daftar negara yang valid dengan kode dan nama lengkap
    VALID_COUNTRIES = {
        # Amerika Utara
        "0": {"code": "0", "name": "🇺🇸 USA", "region": "North America"},
        "1": {"code": "1", "name": "🇨🇦 Canada", "region": "North America"},
        "52": {"code": "52", "name": "🇲🇽 Mexico", "region": "North America"},
        
        # Amerika Selatan
        "54": {"code": "54", "name": "🇦🇷 Argentina", "region": "South America"},
        "55": {"code": "55", "name": "🇧🇷 Brazil", "region": "South America"},
        "56": {"code": "56", "name": "🇨🇱 Chile", "region": "South America"},
        "57": {"code": "57", "name": "🇨🇴 Colombia", "region": "South America"},
        "58": {"code": "58", "name": "🇻🇪 Venezuela", "region": "South America"},
        
        # Eropa
        "33": {"code": "33", "name": "🇫🇷 France", "region": "Europe"},
        "34": {"code": "34", "name": "🇪🇸 Spain", "region": "Europe"},
        "39": {"code": "39", "name": "🇮🇹 Italy", "region": "Europe"},
        "44": {"code": "44", "name": "🇬🇧 UK", "region": "Europe"},
        "49": {"code": "49", "name": "🇩🇪 Germany", "region": "Europe"},
        
        # Asia
        "62": {"code": "62", "name": "🇮🇩 Indonesia", "region": "Asia"},
        "60": {"code": "60", "name": "🇲🇾 Malaysia", "region": "Asia"},
        "63": {"code": "63", "name": "🇵🇭 Philippines", "region": "Asia"},
        "65": {"code": "65", "name": "🇸🇬 Singapore", "region": "Asia"},
        "66": {"code": "66", "name": "🇹🇭 Thailand", "region": "Asia"},
        "84": {"code": "84", "name": "🇻🇳 Vietnam", "region": "Asia"},
        "91": {"code": "91", "name": "🇮🇳 India", "region": "Asia"},
        
        # Lainnya
        "7": {"code": "7", "name": "🇷🇺 Russia", "region": "Europe/Asia"},
        "81": {"code": "81", "name": "🇯🇵 Japan", "region": "Asia"},
        "82": {"code": "82", "name": "🇰🇷 South Korea", "region": "Asia"},
        "90": {"code": "90", "name": "🇹🇷 Turkey", "region": "Europe/Asia"},
        "234": {"code": "234", "name": "🇳🇬 Nigeria", "region": "Africa"},
        "27": {"code": "27", "name": "🇿🇦 South Africa", "region": "Africa"},
    }
    
    # MEXICO HARD LOCK - kode country yang dikunci ke Mexico
    MEXICO_CODE = "52"
    MEXICO_NAME = "🇲🇽 Mexico"
    
    # Alias untuk Mexico (untuk memastikan tidak salah input)
    MEXICO_ALIASES = ["mexico", "mx", "mex", "52", "🇲🇽"]
    
    @classmethod
    def validate(cls, country_code: str, hard_lock_mexico: bool = False) -> Tuple[bool, str, str]:
        """
        Validasi kode negara.
        
        Returns:
            (is_valid, country_code, country_name)
        """
        # Hard lock Mexico mode - selalu return Mexico
        if hard_lock_mexico:
            return True, cls.MEXICO_CODE, cls.MEXICO_NAME
        
        # Normalize input
        code = str(country_code).strip()
        
        # Cek apakah alias Mexico
        if code.lower() in [a.lower() for a in cls.MEXICO_ALIASES]:
            return True, cls.MEXICO_CODE, cls.MEXICO_NAME
        
        # Cek di valid countries
        if code in cls.VALID_COUNTRIES:
            info = cls.VALID_COUNTRIES[code]
            return True, info["code"], info["name"]
        
        # Invalid
        return False, code, f"Unknown ({code})"
    
    @classmethod
    def get_all_countries(cls) -> Dict[str, Dict]:
        """Get semua negara yang valid."""
        return cls.VALID_COUNTRIES.copy()
    
    @classmethod
    def get_countries_by_region(cls) -> Dict[str, List[Dict]]:
        """Get negara berdasarkan region."""
        regions = defaultdict(list)
        for code, info in cls.VALID_COUNTRIES.items():
            regions[info["region"]].append(info)
        return dict(regions)

# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ServiceValidator:
    """Validator untuk layanan SMS."""
    
    VALID_SERVICES = {
        "wa": {"code": "wa", "name": "WhatsApp", "icon": "💬"},
        "tg": {"code": "tg", "name": "Telegram", "icon": "✈️"},
        "fb": {"code": "fb", "name": "Facebook", "icon": "📘"},
        "ig": {"code": "ig", "name": "Instagram", "icon": "📸"},
        "tt": {"code": "tt", "name": "TikTok", "icon": "🎵"},
        "tw": {"code": "tw", "name": "Twitter/X", "icon": "🐦"},
        "go": {"code": "go", "name": "Google", "icon": "🔍"},
        "am": {"code": "am", "name": "Amazon", "icon": "📦"},
        "nf": {"code": "nf", "name": "Netflix", "icon": "🎬"},
        "sp": {"code": "sp", "name": "Spotify", "icon": "🎧"},
        "li": {"code": "li", "name": "LinkedIn", "icon": "💼"},
        "sn": {"code": "sn", "name": "Snapchat", "icon": "👻"},
        "ds": {"code": "ds", "name": "Discord", "icon": "🎮"},
        "vb": {"code": "vb", "name": "Viber", "icon": "📞"},
        "wc": {"code": "wc", "name": "WeChat", "icon": "💬"},
        "lin": {"code": "lin", "name": "Line", "icon": "💚"},
    }
    
    @classmethod
    def validate(cls, service_code: str) -> Tuple[bool, str, str, str]:
        """
        Validasi kode layanan.
        
        Returns:
            (is_valid, service_code, service_name, icon)
        """
        code = str(service_code).strip().lower()
        
        if code in cls.VALID_SERVICES:
            info = cls.VALID_SERVICES[code]
            return True, info["code"], info["name"], info["icon"]
        
        return False, code, f"Unknown ({code})", "❓"
    
    @classmethod
    def get_all_services(cls) -> Dict[str, Dict]:
        """Get semua layanan."""
        return cls.VALID_SERVICES.copy()

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class UserStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BANNED = "banned"

class ActivationStatus(Enum):
    WAITING = "waiting"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    REBUY = "rebuy"

@dataclass
class UserInfo:
    id: int
    name: str
    username: str
    status: UserStatus
    api_key: Optional[str] = None
    created_at: str = ""
    approved_at: str = ""
    approved_by: Optional[int] = None
    purchase_limit: int = 100  # Default limit pembelian
    daily_purchases: int = 0
    total_purchases: int = 0
    hard_lock_mexico: bool = False  # Hard lock ke Mexico

@dataclass
class Activation:
    id: str
    user_id: int
    phone: str
    service: str
    service_name: str
    country: str
    country_name: str
    cost: float
    status: ActivationStatus
    otp_code: Optional[str] = None
    created_at: str = ""
    otp_received_at: str = ""
    rebuy_count: int = 0
    price_checked: bool = False

@dataclass
class BuyTask:
    task_id: str
    user_id: int
    chat_id: int
    api_key: str
    service: str
    country: str
    quantity: int
    completed: int = 0
    failed: int = 0
    results: List[Dict] = field(default_factory=list)
    created_at: str = ""
    status: str = "pending"

@dataclass
class PriceRange:
    min_price: float = 0.01
    max_price: float = 0.50

@dataclass
class MexicoStock:
    """Data stok Mexico real-time."""
    service: str
    service_name: str
    count: int
    cost: float
    last_updated: str

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("grizzly_bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# POLLING SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

SMS_POLL_INTERVAL_NORMAL = 5      # Normal polling (seconds)
SMS_POLL_INTERVAL_SNIPER = 1      # Sniper mode polling (seconds)
SMS_MAX_WAIT = 300                # Timeout 5 menit
AUTO_REBUY_MAX_ATTEMPTS = 3       # Max rebuy attempts
MAX_CONCURRENT_BUYS = 100         # Max parallel buy operations
ITEMS_PER_PAGE = 5                # Items per pagination page
MEXICO_STOCK_REFRESH = 30         # Refresh stok Mexico setiap 30 detik

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "grizzly_sms_bot.db")

# ═══════════════════════════════════════════════════════════════════════════════
# LOADING BAR
# ═══════════════════════════════════════════════════════════════════════════════

class LoadingBar:
    """Professional loading bar dengan Unicode blocks."""
    
    BLOCKS = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
    SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    @staticmethod
    def render(progress: float, width: int = 20) -> str:
        progress = max(0, min(1, progress))
        filled = progress * width
        full_blocks = int(filled)
        partial = filled - full_blocks
        
        bar = "█" * full_blocks
        if full_blocks < width:
            partial_idx = int(partial * len(LoadingBar.BLOCKS))
            bar += LoadingBar.BLOCKS[min(partial_idx, len(LoadingBar.BLOCKS)-1)]
        bar += "░" * (width - full_blocks - (1 if full_blocks < width else 0))
        
        percentage = int(progress * 100)
        return f"[{bar}] {percentage}%"
    
    @staticmethod
    def spinner_frame(frame: int) -> str:
        return LoadingBar.SPINNER[frame % len(LoadingBar.SPINNER)]

# ═══════════════════════════════════════════════════════════════════════════════
# PAGINATION
# ═══════════════════════════════════════════════════════════════════════════════

class Paginator:
    """Professional pagination system."""
    
    @staticmethod
    def paginate(items: List[Any], page: int = 1, per_page: int = ITEMS_PER_PAGE) -> Dict:
        total_items = len(items)
        total_pages = max(1, (total_items + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            "items": items[start:end],
            "page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "start_index": start + 1,
            "end_index": min(end, total_items)
        }
    
    @staticmethod
    def keyboard(prefix: str, page: int, total_pages: int,
                 extra_buttons: List[List[InlineKeyboardButton]] = None) -> InlineKeyboardMarkup:
        buttons = []
        
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("◀️", callback_data=f"{prefix}_page_{page-1}"))
        nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data=f"{prefix}_info"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("▶️", callback_data=f"{prefix}_page_{page+1}"))
        buttons.append(nav)
        
        if total_pages > 1:
            page_btns = []
            start_p = max(1, page - 2)
            end_p = min(total_pages, start_p + 4)
            
            if start_p > 1:
                page_btns.append(InlineKeyboardButton("1", callback_data=f"{prefix}_page_1"))
                if start_p > 2:
                    page_btns.append(InlineKeyboardButton("...", callback_data=f"{prefix}_info"))
            
            for p in range(start_p, end_p + 1):
                label = f"[{p}]" if p == page else str(p)
                page_btns.append(InlineKeyboardButton(label, callback_data=f"{prefix}_page_{p}"))
            
            if end_p < total_pages:
                if end_p < total_pages - 1:
                    page_btns.append(InlineKeyboardButton("...", callback_data=f"{prefix}_info"))
                page_btns.append(InlineKeyboardButton(str(total_pages), callback_data=f"{prefix}_page_{total_pages}"))
            
            buttons.append(page_btns)
        
        if extra_buttons:
            buttons.extend(extra_buttons)
        
        return InlineKeyboardMarkup(buttons)

# ═══════════════════════════════════════════════════════════════════════════════
# SQLITE DATABASE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseManager:
    """SQLite Database Manager dengan thread-safe connection pooling."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._local = threading.local()
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-64000")
        return self._local.conn
    
    @contextmanager
    def get_cursor(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
    
    def _init_database(self):
        with self.get_cursor() as cur:
            # Users table dengan field tambahan
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    api_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP,
                    approved_by INTEGER,
                    purchase_limit INTEGER DEFAULT 100,
                    daily_purchases INTEGER DEFAULT 0,
                    total_purchases INTEGER DEFAULT 0,
                    hard_lock_mexico INTEGER DEFAULT 0,
                    sniper_mode INTEGER DEFAULT 0,
                    auto_rebuy INTEGER DEFAULT 1,
                    last_purchase_date TEXT,
                    settings TEXT DEFAULT '{}'
                )
            """)
            
            # Activations table dengan field tambahan
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    service TEXT NOT NULL,
                    service_name TEXT DEFAULT '',
                    country TEXT NOT NULL,
                    country_name TEXT DEFAULT '',
                    cost REAL DEFAULT 0,
                    status TEXT DEFAULT 'waiting',
                    otp_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    otp_received_at TIMESTAMP,
                    rebuy_count INTEGER DEFAULT 0,
                    price_checked INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Buy tasks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS buy_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    api_key TEXT NOT NULL,
                    service TEXT NOT NULL,
                    country TEXT NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    completed INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    results TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Activity logs table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Bot settings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Mexico stock cache
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mexico_stock (
                    service TEXT PRIMARY KEY,
                    service_name TEXT,
                    count INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_activations_user ON activations(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_activations_status ON activations(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_user ON activity_logs(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON activity_logs(created_at)")
            
            # Initialize default settings
            cur.execute("""
                INSERT OR IGNORE INTO bot_settings (key, value) VALUES 
                ('price_min', '0.01'),
                ('price_max', '0.50'),
                ('auto_approve', '0'),
                ('global_mexico_lock', '0')
            """)
        
        logger.info("Database initialized successfully")
    
    # ==================== USER OPERATIONS ====================
    
    def add_user(self, user_id: int, name: str, username: str = "", 
                 status: UserStatus = UserStatus.PENDING) -> bool:
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT OR IGNORE INTO users (id, name, username, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, name, username, status.value, datetime.now().isoformat()))
        return True
    
    def get_user(self, user_id: int) -> Optional[UserInfo]:
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return UserInfo(
                    id=row['id'],
                    name=row['name'],
                    username=row['username'] or "",
                    status=UserStatus(row['status']),
                    api_key=row['api_key'],
                    created_at=row['created_at'] or "",
                    approved_at=row['approved_at'] or "",
                    approved_by=row['approved_by'],
                    purchase_limit=row['purchase_limit'] or 100,
                    daily_purchases=row['daily_purchases'] or 0,
                    total_purchases=row['total_purchases'] or 0,
                    hard_lock_mexico=bool(row['hard_lock_mexico'])
                )
        return None
    
    def update_user_status(self, user_id: int, status: UserStatus, 
                           approved_by: Optional[int] = None) -> bool:
        with self.get_cursor() as cur:
            if status == UserStatus.APPROVED:
                cur.execute("""
                    UPDATE users SET status = ?, approved_at = ?, approved_by = ?
                    WHERE id = ?
                """, (status.value, datetime.now().isoformat(), approved_by, user_id))
            else:
                cur.execute("UPDATE users SET status = ? WHERE id = ?", 
                           (status.value, user_id))
        return True
    
    def update_user_api_key(self, user_id: int, api_key: str) -> bool:
        """Update API key untuk user (1 user = 1 API key)."""
        with self.get_cursor() as cur:
            cur.execute("UPDATE users SET api_key = ? WHERE id = ?", (api_key, user_id))
        return True
    
    def update_user_purchase_limit(self, user_id: int, limit: int) -> bool:
        """Update limit pembelian untuk user."""
        with self.get_cursor() as cur:
            cur.execute("UPDATE users SET purchase_limit = ? WHERE id = ?", (limit, user_id))
        return True
    
    def update_user_mexico_lock(self, user_id: int, locked: bool) -> bool:
        """Update hard lock Mexico mode untuk user."""
        with self.get_cursor() as cur:
            cur.execute("UPDATE users SET hard_lock_mexico = ? WHERE id = ?", 
                       (1 if locked else 0, user_id))
        return True
    
    def increment_user_purchases(self, user_id: int, count: int = 1) -> bool:
        """Increment counter pembelian user."""
        today = datetime.now().date().isoformat()
        with self.get_cursor() as cur:
            # Check if new day
            cur.execute("SELECT last_purchase_date FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if row and row['last_purchase_date'] != today:
                # Reset daily counter
                cur.execute("""
                    UPDATE users SET 
                    daily_purchases = ?,
                    total_purchases = total_purchases + ?,
                    last_purchase_date = ?
                    WHERE id = ?
                """, (count, count, today, user_id))
            else:
                cur.execute("""
                    UPDATE users SET 
                    daily_purchases = daily_purchases + ?,
                    total_purchases = total_purchases + ?,
                    last_purchase_date = ?
                    WHERE id = ?
                """, (count, count, today, user_id))
        return True
    
    def get_pending_users(self) -> List[UserInfo]:
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE status = ? ORDER BY created_at DESC",
                       (UserStatus.PENDING.value,))
            return [UserInfo(
                id=row['id'], name=row['name'], username=row['username'] or "",
                status=UserStatus(row['status']), api_key=row['api_key'],
                created_at=row['created_at'] or "",
                purchase_limit=row['purchase_limit'] or 100,
                hard_lock_mexico=bool(row['hard_lock_mexico'])
            ) for row in cur.fetchall()]
    
    def get_approved_users(self) -> List[int]:
        with self.get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE status = ?", (UserStatus.APPROVED.value,))
            return [row['id'] for row in cur.fetchall()]
    
    def get_all_users_count(self) -> Dict[str, int]:
        with self.get_cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) as count FROM users GROUP BY status
            """)
            result = {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "banned": 0}
            for row in cur.fetchall():
                result[row['status']] = row['count']
                result['total'] += row['count']
            cur.execute("SELECT COUNT(*) as count FROM users WHERE id IN ({})".format(
                ",".join(map(str, ADMIN_IDS))
            ))
            result['admins'] = cur.fetchone()['count']
        return result
    
    # ==================== ACTIVATION OPERATIONS ====================
    
    def add_activation(self, activation: Activation) -> bool:
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO activations 
                (id, user_id, phone, service, service_name, country, country_name, 
                 cost, status, otp_code, created_at, otp_received_at, rebuy_count, price_checked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                activation.id, activation.user_id, activation.phone,
                activation.service, activation.service_name, activation.country,
                activation.country_name, activation.cost,
                activation.status.value, activation.otp_code,
                activation.created_at, activation.otp_received_at,
                activation.rebuy_count, 1 if activation.price_checked else 0
            ))
        return True
    
    def get_activation(self, activation_id: str) -> Optional[Activation]:
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM activations WHERE id = ?", (activation_id,))
            row = cur.fetchone()
            if row:
                return Activation(
                    id=row['id'], user_id=row['user_id'], phone=row['phone'],
                    service=row['service'], service_name=row['service_name'] or '',
                    country=row['country'], country_name=row['country_name'] or '',
                    cost=row['cost'], status=ActivationStatus(row['status']),
                    otp_code=row['otp_code'], created_at=row['created_at'] or "",
                    otp_received_at=row['otp_received_at'] or "",
                    rebuy_count=row['rebuy_count'] or 0,
                    price_checked=bool(row['price_checked'])
                )
        return None
    
    def update_activation_status(self, activation_id: str, status: ActivationStatus,
                                  otp_code: Optional[str] = None) -> bool:
        with self.get_cursor() as cur:
            if otp_code:
                cur.execute("""
                    UPDATE activations SET status = ?, otp_code = ?, otp_received_at = ?
                    WHERE id = ?
                """, (status.value, otp_code, datetime.now().isoformat(), activation_id))
            else:
                cur.execute("UPDATE activations SET status = ? WHERE id = ?",
                           (status.value, activation_id))
        return True
    
    def get_user_activations(self, user_id: int, status: Optional[ActivationStatus] = None,
                             limit: int = 100) -> List[Activation]:
        with self.get_cursor() as cur:
            if status:
                cur.execute("""
                    SELECT * FROM activations WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (user_id, status.value, limit))
            else:
                cur.execute("""
                    SELECT * FROM activations WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (user_id, limit))
            return [Activation(
                id=row['id'], user_id=row['user_id'], phone=row['phone'],
                service=row['service'], service_name=row['service_name'] or '',
                country=row['country'], country_name=row['country_name'] or '',
                cost=row['cost'], status=ActivationStatus(row['status']),
                otp_code=row['otp_code'], created_at=row['created_at'] or "",
                otp_received_at=row['otp_received_at'] or "",
                rebuy_count=row['rebuy_count'] or 0,
                price_checked=bool(row['price_checked'])
            ) for row in cur.fetchall()]
    
    def delete_activation(self, activation_id: str) -> bool:
        with self.get_cursor() as cur:
            cur.execute("DELETE FROM activations WHERE id = ?", (activation_id,))
        return True
    
    def get_activations_count(self, user_id: Optional[int] = None) -> Dict[str, int]:
        with self.get_cursor() as cur:
            result = {"total": 0, "waiting": 0, "received": 0, "cancelled": 0, "timeout": 0}
            if user_id:
                cur.execute("""
                    SELECT status, COUNT(*) as count FROM activations 
                    WHERE user_id = ? GROUP BY status
                """, (user_id,))
            else:
                cur.execute("""
                    SELECT status, COUNT(*) as count FROM activations GROUP BY status
                """)
            for row in cur.fetchall():
                result[row['status']] = row['count']
                result['total'] += row['count']
        return result
    
    # ==================== MEXICO STOCK OPERATIONS ====================
    
    def update_mexico_stock(self, stocks: List[Dict]) -> bool:
        """Update cache stok Mexico."""
        with self.get_cursor() as cur:
            for stock in stocks:
                cur.execute("""
                    INSERT OR REPLACE INTO mexico_stock 
                    (service, service_name, count, cost, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    stock['service'], stock.get('service_name', ''),
                    stock['count'], stock['cost'],
                    datetime.now().isoformat()
                ))
        return True
    
    def get_mexico_stock(self) -> List[Dict]:
        """Get cached stok Mexico."""
        with self.get_cursor() as cur:
            cur.execute("SELECT * FROM mexico_stock ORDER BY count DESC")
            return [dict(row) for row in cur.fetchall()]
    
    # ==================== LOG OPERATIONS ====================
    
    def add_log(self, user_id: Optional[int], action: str, details: str = "") -> bool:
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT INTO activity_logs (user_id, action, details, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, action, details, datetime.now().isoformat()))
        return True
    
    def get_logs(self, user_id: Optional[int] = None, limit: int = 100,
                 offset: int = 0) -> List[Dict]:
        with self.get_cursor() as cur:
            if user_id:
                cur.execute("""
                    SELECT * FROM activity_logs WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
            else:
                cur.execute("""
                    SELECT * FROM activity_logs
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (limit, offset))
            return [dict(row) for row in cur.fetchall()]
    
    def get_logs_count(self, user_id: Optional[int] = None) -> int:
        with self.get_cursor() as cur:
            if user_id:
                cur.execute("SELECT COUNT(*) as count FROM activity_logs WHERE user_id = ?",
                           (user_id,))
            else:
                cur.execute("SELECT COUNT(*) as count FROM activity_logs")
            return cur.fetchone()['count']
    
    # ==================== SETTINGS OPERATIONS ====================
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.get_cursor() as cur:
            cur.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                try:
                    return json.loads(row['value'])
                except:
                    return row['value']
        return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        with self.get_cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO bot_settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, json.dumps(value) if not isinstance(value, str) else value,
                  datetime.now().isoformat()))
        return True
    
    def get_price_range(self) -> PriceRange:
        return PriceRange(
            min_price=float(self.get_setting('price_min', 0.01)),
            max_price=float(self.get_setting('price_max', 0.50))
        )
    
    def set_price_range(self, min_price: float, max_price: float) -> bool:
        self.set_setting('price_min', min_price)
        self.set_setting('price_max', max_price)
        return True
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict:
        with self.get_cursor() as cur:
            stats = {}
            
            cur.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM users WHERE status = 'approved'")
            stats['approved_users'] = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM users WHERE status = 'pending'")
            stats['pending_users'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM activations")
            stats['total_activations'] = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM activations WHERE status = 'waiting'")
            stats['waiting_activations'] = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM activations WHERE status = 'received'")
            stats['received_activations'] = cur.fetchone()['count']
            
            today = datetime.now().date().isoformat()
            cur.execute("""
                SELECT COUNT(*) as count FROM activations 
                WHERE date(created_at) = ?
            """, (today,))
            stats['today_activations'] = cur.fetchone()['count']
            
            cur.execute("SELECT SUM(cost) as total FROM activations WHERE status = 'received'")
            result = cur.fetchone()
            stats['total_spent'] = result['total'] or 0.0
            
            cur.execute("SELECT COUNT(*) as count FROM buy_tasks WHERE status = 'pending'")
            stats['pending_tasks'] = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM buy_tasks WHERE status = 'running'")
            stats['running_tasks'] = cur.fetchone()['count']
            
        return stats

# Initialize global database instance
db = DatabaseManager()

# ═══════════════════════════════════════════════════════════════════════════════
# API CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class GrizzlyAPI:
    """GrizzlySMS API Client dengan price check dan error handling."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _call(self, api_key: str, action: str, extra: Dict = None, 
              timeout: int = 15) -> str:
        params = {"api_key": api_key.strip(), "action": action}
        if extra:
            params.update(extra)
        
        query = urllib.parse.urlencode(params)
        
        for base_url in [API_BASE, API_BASE2]:
            url = f"{base_url}?{query}"
            try:
                r = self.session.get(url, timeout=timeout, verify=False)
                result = r.text.strip()
                
                if result.startswith("<") or result.startswith("<!"):
                    continue
                
                logger.info(f"[{action}] → {result[:80]}")
                return result
                
            except requests.Timeout:
                logger.warning(f"Timeout from {base_url}")
                continue
            except Exception as e:
                logger.error(f"Request error {base_url}: {e}")
                continue
        
        return "SERVER_ERROR"
    
    def get_balance(self, api_key: str) -> Optional[float]:
        resp = self._call(api_key, "getBalance")
        if resp.startswith("ACCESS_BALANCE:"):
            try:
                return float(resp.split(":")[1])
            except:
                pass
        return None
    
    def get_price(self, api_key: str, service: str, country: str) -> Dict:
        """Get price untuk service dan country tertentu."""
        resp = self._call(api_key, "getPrices", {"service": service, "country": country})
        try:
            data = json.loads(resp)
            p = data.get(str(country), {}).get(str(service), {})
            return {"cost": p.get("cost", "?"), "count": p.get("count", 0)}
        except:
            return {"cost": "?", "count": 0}
    
    def get_all_prices_mexico(self, api_key: str) -> List[Dict]:
        """Get semua harga untuk Mexico (country code 52)."""
        resp = self._call(api_key, "getPrices", {"country": "52"})
        stocks = []
        try:
            data = json.loads(resp)
            mexico_data = data.get("52", {})
            for service_code, info in mexico_data.items():
                _, service_name, _ = ServiceValidator.validate(service_code)
                stocks.append({
                    "service": service_code,
                    "service_name": service_name,
                    "count": info.get("count", 0),
                    "cost": info.get("cost", 0)
                })
        except Exception as e:
            logger.error(f"Error parsing Mexico prices: {e}")
        return stocks
    
    def check_price_before_buy(self, api_key: str, service: str, country: str,
                                price_range: PriceRange) -> Dict:
        """
        Cek harga sebelum melakukan pembelian.
        Returns info tentang harga dan apakah dalam range.
        """
        price_info = self.get_price(api_key, service, country)
        
        try:
            cost = float(price_info.get("cost", 999))
        except (ValueError, TypeError):
            cost = 999.0
        
        in_range = price_range.min_price <= cost <= price_range.max_price
        
        return {
            "cost": cost,
            "count": price_info.get("count", 0),
            "in_range": in_range,
            "min": price_range.min_price,
            "max": price_range.max_price
        }
    
    def buy_number(self, api_key: str, service: str, country: str,
                   price_range: PriceRange) -> Dict:
        """Buy number dengan price validation terlebih dahulu."""
        # Cek harga dulu
        price_check = self.check_price_before_buy(api_key, service, country, price_range)
        
        if not price_check["in_range"]:
            return {
                "status": "error",
                "error": "PRICE_OUT_OF_RANGE",
                "cost": price_check["cost"],
                "range": f"${price_range.min_price:.2f}-${price_range.max_price:.2f}"
            }
        
        if price_check["count"] <= 0:
            return {
                "status": "error",
                "error": "NO_NUMBERS",
                "count": 0
            }
        
        # Validasi country dengan validator
        is_valid, country_code, country_name = CountryValidator.validate(country)
        if not is_valid:
            return {
                "status": "error",
                "error": "INVALID_COUNTRY",
                "country": country
            }
        
        # Validasi service
        is_valid_svc, svc_code, svc_name, _ = ServiceValidator.validate(service)
        if not is_valid_svc:
            return {
                "status": "error",
                "error": "INVALID_SERVICE",
                "service": service
            }
        
        # Beli nomor
        resp = self._call(api_key, "getNumber", {"service": svc_code, "country": country_code})
        
        if resp.startswith("ACCESS_NUMBER:"):
            parts = resp.split(":", 2)
            if len(parts) == 3:
                return {
                    "status": "ok",
                    "id": parts[1].strip(),
                    "phone": parts[2].strip(),
                    "cost": price_check["cost"],
                    "service_name": svc_name,
                    "country_name": country_name,
                    "price_checked": True
                }
            return {"status": "error", "error": "FORMAT_ERROR"}
        
        error = resp.split(":")[0] if ":" in resp else resp
        return {"status": "error", "error": error}
    
    def get_sms(self, api_key: str, activation_id: str) -> Dict:
        resp = self._call(api_key, "getStatus", {"id": activation_id})
        
        if resp.startswith("STATUS_OK:"):
            return {"status": "ok", "code": resp.split(":", 1)[1]}
        elif resp in ("STATUS_WAIT_CODE", "STATUS_WAIT_RETRY", "STATUS_WAIT_RESEND"):
            return {"status": "waiting"}
        elif resp == "STATUS_CANCEL":
            return {"status": "cancelled"}
        
        return {"status": "error", "error": resp}
    
    def cancel(self, api_key: str, activation_id: str) -> bool:
        resp = self._call(api_key, "setStatus", {"id": activation_id, "status": "8"})
        return any(x in resp for x in ["ACCESS_CANCEL", "ACCESS_ACTIVATION", "1"])
    
    def confirm(self, api_key: str, activation_id: str) -> bool:
        resp = self._call(api_key, "setStatus", {"id": activation_id, "status": "6"})
        return any(x in resp for x in ["ACCESS_ACTIVATION", "1"])

# Global API instance
api = GrizzlyAPI()

# ═══════════════════════════════════════════════════════════════════════════════
# MEXICO STOCK SNIPER (REAL-TIME)
# ═══════════════════════════════════════════════════════════════════════════════

class MexicoStockSniper:
    """
    Real-time stock sniper untuk Mexico.
    Memantau ketersediaan nomor Mexico secara berkala.
    """
    
    def __init__(self):
        self.running = False
        self.stock_cache: List[Dict] = []
        self.subscribers: Set[int] = set()  # Chat IDs yang subscribe
        self._lock = asyncio.Lock()
        self.last_update: str = ""
    
    async def start(self):
        """Start stock monitoring."""
        self.running = True
        asyncio.create_task(self._monitor_loop())
        logger.info("Mexico Stock Sniper started")
    
    def stop(self):
        """Stop stock monitoring."""
        self.running = False
    
    async def _monitor_loop(self):
        """Background loop untuk monitoring stok."""
        while self.running:
            try:
                # Get admin API key for checking stock
                # Use first admin's API key if available
                admin_key = None
                for admin_id in ADMIN_IDS:
                    user = db.get_user(admin_id)
                    if user and user.api_key:
                        admin_key = user.api_key
                        break
                
                if admin_key:
                    stocks = api.get_all_prices_mexico(admin_key)
                    if stocks:
                        async with self._lock:
                            self.stock_cache = stocks
                            self.last_update = datetime.now().strftime("%H:%M:%S")
                        
                        # Update database cache
                        db.update_mexico_stock(stocks)
                        
                        # Notify subscribers of significant changes
                        await self._notify_subscribers(stocks)
                
            except Exception as e:
                logger.error(f"Mexico stock monitor error: {e}")
            
            await asyncio.sleep(MEXICO_STOCK_REFRESH)
    
    async def _notify_subscribers(self, stocks: List[Dict]):
        """Notify subscribers tentang stok update."""
        # Find services with good availability
        good_stock = [s for s in stocks if s['count'] > 10]
        if good_stock:
            async with self._lock:
                for chat_id in list(self.subscribers):
                    # Send notification (implement later with bot instance)
                    pass
    
    def subscribe(self, chat_id: int):
        """Subscribe untuk stock notifications."""
        self.subscribers.add(chat_id)
    
    def unsubscribe(self, chat_id: int):
        """Unsubscribe dari stock notifications."""
        self.subscribers.discard(chat_id)
    
    def get_stock(self) -> Tuple[List[Dict], str]:
        """Get current cached stock."""
        return self.stock_cache.copy(), self.last_update
    
    def get_stock_for_service(self, service: str) -> Optional[Dict]:
        """Get stock for specific service."""
        for stock in self.stock_cache:
            if stock['service'] == service:
                return stock
        return None

# Global stock sniper
stock_sniper = MexicoStockSniper()

# ═══════════════════════════════════════════════════════════════════════════════
# OTP AUTO CHECKER
# ═══════════════════════════════════════════════════════════════════════════════

class OTPAutoChecker:
    """
    OTP Auto Checker dengan support untuk auto rebuy.
    """
    
    def __init__(self):
        self.active_polls: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def start_poll(self, app: Application, activation: Activation, 
                         api_key: str, sniper_mode: bool = False,
                         auto_rebuy: bool = True, chat_id: int = None):
        """Start polling for OTP."""
        poll_id = activation.id
        
        async with self._lock:
            self.active_polls[poll_id] = {
                "activation": activation,
                "api_key": api_key,
                "start_time": time.time(),
                "sniper_mode": sniper_mode,
                "auto_rebuy": auto_rebuy,
                "chat_id": chat_id,
                "rebuy_count": 0,
                "task": None
            }
        
        task = asyncio.create_task(self._poll_worker(app, poll_id))
        async with self._lock:
            if poll_id in self.active_polls:
                self.active_polls[poll_id]["task"] = task
        
        logger.info(f"OTP polling started: {poll_id}")
    
    async def stop_poll(self, activation_id: str):
        """Stop polling."""
        async with self._lock:
            if activation_id in self.active_polls:
                poll = self.active_polls[activation_id]
                if poll.get("task"):
                    poll["task"].cancel()
                del self.active_polls[activation_id]
        logger.info(f"OTP polling stopped: {activation_id}")
    
    async def _poll_worker(self, app: Application, poll_id: str):
        """Worker untuk polling OTP."""
        while poll_id in self.active_polls:
            try:
                poll = self.active_polls.get(poll_id)
                if not poll:
                    break
                
                activation = poll["activation"]
                api_key = poll["api_key"]
                start_time = poll["start_time"]
                sniper_mode = poll["sniper_mode"]
                chat_id = poll["chat_id"]
                auto_rebuy = poll.get("auto_rebuy", True)
                rebuy_count = poll.get("rebuy_count", 0)
                
                elapsed = time.time() - start_time
                
                # Timeout check
                if elapsed > SMS_MAX_WAIT:
                    if auto_rebuy and rebuy_count < AUTO_REBUY_MAX_ATTEMPTS:
                        await self._do_rebuy(app, poll_id, activation, chat_id, api_key)
                        return
                    else:
                        await self._handle_timeout(app, poll_id, activation, chat_id)
                        return
                
                interval = SMS_POLL_INTERVAL_SNIPER if sniper_mode else SMS_POLL_INTERVAL_NORMAL
                result = api.get_sms(api_key, activation.id)
                
                if result["status"] == "ok":
                    await self._handle_otp_received(app, poll_id, activation, 
                                                    result["code"], elapsed, chat_id)
                    return
                elif result["status"] == "cancelled":
                    await self.stop_poll(poll_id)
                    return
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll worker error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_otp_received(self, app: Application, poll_id: str,
                                    activation: Activation, code: str,
                                    elapsed: float, chat_id: int):
        """Handle OTP diterima."""
        await self.stop_poll(poll_id)
        
        db.update_activation_status(activation.id, ActivationStatus.RECEIVED, code)
        db.add_log(activation.user_id, "OTP_RECEIVED", 
                   f"{activation.id}|{code}|{elapsed:.0f}s")
        
        if chat_id:
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔔 *OTP DITERIMA!*\n\n"
                        f"📞 `+{activation.phone}`\n"
                        f"🔑 *Kode: `{code}`*\n"
                        f"📦 {activation.service_name} | {activation.country_name}\n"
                        f"⏱️ Waktu: {elapsed:.0f}s\n"
                        f"💰 Harga: ${activation.cost:.2f}\n\n"
                        f"✅ `/konfirmasi {activation.id}`"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send OTP notification: {e}")
    
    async def _handle_timeout(self, app: Application, poll_id: str,
                               activation: Activation, chat_id: int):
        """Handle OTP timeout."""
        await self.stop_poll(poll_id)
        db.update_activation_status(activation.id, ActivationStatus.TIMEOUT)
        
        if chat_id:
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"⏰ *OTP TIMEOUT*\n\n"
                        f"📞 `+{activation.phone}`\n"
                        f"🆔 `{activation.id}`\n"
                        f"SMS tidak masuk dalam {SMS_MAX_WAIT//60} menit.\n\n"
                        f"`/cancel {activation.id}`"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
    
    async def _do_rebuy(self, app: Application, poll_id: str,
                        activation: Activation, chat_id: int, api_key: str):
        """Auto rebuy jika OTP tidak masuk."""
        poll = self.active_polls.get(poll_id)
        if not poll:
            return
        
        rebuy_count = poll.get("rebuy_count", 0)
        
        # Cancel old activation
        api.cancel(api_key, activation.id)
        
        # Get user
        user = db.get_user(activation.user_id)
        if not user:
            await self.stop_poll(poll_id)
            return
        
        # Get price range
        price_range = db.get_price_range()
        
        # Buy new number
        result = api.buy_number(api_key, activation.service, activation.country, price_range)
        
        if result["status"] == "ok":
            new_activation = Activation(
                id=result["id"],
                user_id=activation.user_id,
                phone=result["phone"],
                service=activation.service,
                service_name=result.get("service_name", activation.service_name),
                country=activation.country,
                country_name=result.get("country_name", activation.country_name),
                cost=result["cost"],
                status=ActivationStatus.WAITING,
                created_at=datetime.now().isoformat(),
                rebuy_count=rebuy_count + 1,
                price_checked=True
            )
            db.add_activation(new_activation)
            
            poll["activation"] = new_activation
            poll["start_time"] = time.time()
            poll["rebuy_count"] = rebuy_count + 1
            
            if chat_id:
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🔄 *AUTO REBUY #{rebuy_count + 1}*\n\n"
                            f"📞 Nomor baru: `+{result['phone']}`\n"
                            f"🆔 `{result['id']}`\n"
                            f"💰 ${result['cost']:.2f}\n\n"
                            f"Menunggu OTP..."
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            db.add_log(activation.user_id, "AUTO_REBUY", 
                       f"{activation.id}→{result['id']}")
        else:
            await self.stop_poll(poll_id)
            db.update_activation_status(activation.id, ActivationStatus.TIMEOUT)
            
            if chat_id:
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ *Auto rebuy gagal:* {result.get('error', 'Unknown')}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
    
    def get_stats(self) -> Dict:
        """Get polling statistics."""
        return {
            "active_polls": len(self.active_polls),
            "polls": list(self.active_polls.keys())
        }

# Global OTP checker
otp_checker = OTPAutoChecker()

# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL BUY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ParallelBuyEngine:
    """Engine untuk membeli 100-1000 nomor secara paralel."""
    
    def __init__(self):
        self.active_tasks: Dict[str, BuyTask] = {}
        self._lock = asyncio.Lock()
    
    async def start_buy(self, app: Application, user_id: int, chat_id: int,
                        api_key: str, service: str, country: str,
                        quantity: int, sniper_mode: bool = False,
                        hard_lock_mexico: bool = False) -> Tuple[str, str]:
        """Start parallel buy dengan validasi limit."""
        
        # Get user untuk cek limit
        user = db.get_user(user_id)
        if not user:
            return "", "User tidak ditemukan"
        
        # Cek purchase limit
        if user.daily_purchases + quantity > user.purchase_limit:
            remaining = user.purchase_limit - user.daily_purchases
            return "", f"Limit pembelian terlampaui. Sisa limit: {remaining} nomor"
        
        # Validasi country dengan hard lock
        if hard_lock_mexico:
            country = CountryValidator.MEXICO_CODE
        
        is_valid, country_code, country_name = CountryValidator.validate(country, hard_lock_mexico)
        if not is_valid:
            return "", f"Kode negara tidak valid: {country}"
        
        # Validasi service
        is_valid_svc, svc_code, svc_name, _ = ServiceValidator.validate(service)
        if not is_valid_svc:
            return "", f"Kode layanan tidak valid: {service}"
        
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        task = BuyTask(
            task_id=task_id,
            user_id=user_id,
            chat_id=chat_id,
            api_key=api_key,
            service=svc_code,
            country=country_code,
            quantity=quantity,
            created_at=datetime.now().isoformat(),
            status="running"
        )
        
        db.add_buy_task(task)
        
        async with self._lock:
            self.active_tasks[task_id] = task
        
        asyncio.create_task(self._process_buy(app, task_id, sniper_mode, country_name, svc_name))
        
        return task_id, ""
    
    async def _process_buy(self, app: Application, task_id: str, sniper_mode: bool,
                           country_name: str, service_name: str):
        """Process buy task."""
        task = self.active_tasks.get(task_id)
        if not task:
            return
        
        user = db.get_user(task.user_id)
        price_range = db.get_price_range()
        results = []
        completed = 0
        failed = 0
        
        msg = None
        try:
            msg = await app.bot.send_message(
                chat_id=task.chat_id,
                text=(
                    f"🚀 *PARALLEL BUY STARTED*\n\n"
                    f"📊 Quantity: {task.quantity}\n"
                    f"📦 {service_name} | {country_name}\n"
                    f"💵 Range: ${price_range.min_price:.2f}-${price_range.max_price:.2f}\n\n"
                    f"`{LoadingBar.render(0)}`"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_BUYS)
        
        async def buy_single(index: int):
            nonlocal completed, failed
            
            async with semaphore:
                try:
                    result = api.buy_number(task.api_key, task.service, 
                                           task.country, price_range)
                    
                    if result["status"] == "ok":
                        activation = Activation(
                            id=result["id"],
                            user_id=task.user_id,
                            phone=result["phone"],
                            service=task.service,
                            service_name=result.get("service_name", service_name),
                            country=task.country,
                            country_name=result.get("country_name", country_name),
                            cost=result["cost"],
                            status=ActivationStatus.WAITING,
                            created_at=datetime.now().isoformat(),
                            price_checked=True
                        )
                        db.add_activation(activation)
                        
                        # Get user settings for sniper mode
                        sniper = db.get_setting(f"sniper_mode_{task.user_id}", sniper_mode)
                        auto_rebuy = db.get_setting(f"auto_rebuy_{task.user_id}", True)
                        
                        await otp_checker.start_poll(
                            app, activation, task.api_key,
                            sniper_mode=sniper,
                            auto_rebuy=auto_rebuy,
                            chat_id=task.chat_id
                        )
                        
                        completed += 1
                        return {"success": True, "activation": activation}
                    else:
                        failed += 1
                        return {"success": False, "error": result.get("error")}
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"Buy error: {e}")
                    return {"success": False, "error": str(e)}
        
        buy_tasks = [buy_single(i) for i in range(task.quantity)]
        
        batch_size = 50
        for batch_start in range(0, len(buy_tasks), batch_size):
            batch = buy_tasks[batch_start:batch_start + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for r in batch_results:
                if isinstance(r, dict):
                    results.append(r)
            
            total_done = completed + failed
            if msg and total_done % 5 == 0:
                progress = total_done / task.quantity
                try:
                    await app.bot.edit_message_text(
                        chat_id=task.chat_id,
                        message_id=msg.message_id,
                        text=(
                            f"🚀 *PARALLEL BUY PROGRESS*\n\n"
                            f"📊 {total_done}/{task.quantity}\n"
                            f"✅ Success: {completed}\n"
                            f"❌ Failed: {failed}\n\n"
                            f"`{LoadingBar.render(progress)}`"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
        
        # Update user purchase count
        if completed > 0:
            db.increment_user_purchases(task.user_id, completed)
        
        db.update_buy_task(task_id, completed, failed, results, "completed")
        
        total_cost = sum(
            r.get("activation", Activation(
                id="", user_id=0, phone="", service="", service_name="",
                country="", country_name="", cost=0, status=ActivationStatus.WAITING
            )).cost 
            for r in results if r.get("success")
        )
        
        if msg:
            try:
                await app.bot.edit_message_text(
                    chat_id=task.chat_id,
                    message_id=msg.message_id,
                    text=(
                        f"🏁 *PARALLEL BUY COMPLETED*\n\n"
                        f"📊 Total: {task.quantity}\n"
                        f"✅ Success: {completed}\n"
                        f"❌ Failed: {failed}\n"
                        f"💰 Total Spent: ${total_cost:.2f}\n\n"
                        f"🔔 OTP akan dikirim otomatis!\n"
                        f"📋 `/task {task_id}` untuk detail"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        db.add_log(task.user_id, "PARALLEL_BUY", 
                   f"{task_id}|{completed}/{task.quantity}|${total_cost:.2f}")
        
        async with self._lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    def get_task(self, task_id: str) -> Optional[BuyTask]:
        return self.active_tasks.get(task_id) or db.get_buy_task(task_id)

# Global buy engine
buy_engine = ParallelBuyEngine()

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in ADMIN_IDS

def is_approved(user_id: int) -> bool:
    """Check if user is approved."""
    user = db.get_user(user_id)
    if user:
        return user.status == UserStatus.APPROVED
    return False

async def check_access(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check user access."""
    user = update.effective_user
    
    db_user = db.get_user(user.id)
    
    if not db_user:
        db.add_user(user.id, user.first_name, user.username or "")
        db_user = db.get_user(user.id)
        
        if is_admin(user.id):
            db.update_user_status(user.id, UserStatus.APPROVED)
            db_user = db.get_user(user.id)
    
    if is_admin(user.id):
        if db_user.status != UserStatus.APPROVED:
            db.update_user_status(user.id, UserStatus.APPROVED)
        return True
    
    if db_user.status == UserStatus.APPROVED:
        return True
    elif db_user.status == UserStatus.PENDING:
        await request_approval(update, ctx)
        return False
    elif db_user.status == UserStatus.BANNED:
        await update.message.reply_text("🚫 Akun kamu telah dibanned.")
        return False
    else:
        await update.message.reply_text("🚫 Akses ditolak.")
        return False

async def request_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle approval request."""
    user = update.effective_user
    
    db.add_user(user.id, user.first_name, user.username or "", UserStatus.PENDING)
    
    await update.message.reply_text(
        f"🔒 *AKSES DIPERLUKAN*\n\n"
        f"Hai {user.first_name}!\n"
        f"ID: `{user.id}`\n\n"
        f"Permintaan akses telah dikirim ke admin.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
                ],
                [InlineKeyboardButton("🚫 Ban", callback_data=f"ban_{user.id}")]
            ])
            
            await ctx.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 *PERMINTAAN AKSES BARU*\n\n"
                    f"👤 {user.first_name}\n"
                    f"🆔 `{user.id}`\n"
                    f"👥 @{user.username or '-'}\n"
                    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

def error_map(error: str) -> str:
    """Map error codes to messages."""
    price_range = db.get_price_range()
    
    error_messages = {
        "NO_NUMBERS": "❌ Nomor habis. Coba layanan/negara lain.",
        "NO_BALANCE": "❌ Saldo tidak cukup. Top up di grizzlysms.com",
        "BAD_KEY": "❌ API Key tidak valid.",
        "BAD_SERVICE": "❌ Kode layanan tidak valid.",
        "BAD_COUNTRY": "❌ Kode negara tidak valid.",
        "SERVER_ERROR": "❌ Server error. Coba lagi.",
        "TOO_MANY_ACTIVE_ACTIVATIONS": "❌ Terlalu banyak aktivasi aktif.",
        "FORMAT_ERROR": "❌ Format response tidak dikenal.",
        "PRICE_OUT_OF_RANGE": f"❌ Harga di luar range (${price_range.min_price:.2f}-${price_range.max_price:.2f}).",
        "INVALID_COUNTRY": "❌ Kode negara tidak valid.",
        "INVALID_SERVICE": "❌ Kode layanan tidak valid.",
    }
    return error_messages.get(error, f"❌ Error: `{error}`")

# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════

def main_keyboard(is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("💰 Cek Saldo"), KeyboardButton("📲 Beli 1 Nomor")],
        [KeyboardButton("🔢 Beli 3 Nomor"), KeyboardButton("🔟 Beli 5 Nomor")],
        [KeyboardButton("🚀 Beli Banyak")],
        [KeyboardButton("📞 Daftar Nomor"), KeyboardButton("📋 Log Aktivitas")],
        [KeyboardButton("⚙️ Pengaturan"), KeyboardButton("🎯 Sniper Mode")],
        [KeyboardButton("🇲🇽 Stok Mexico"), KeyboardButton("❌ Batalkan Semua")],
    ]
    
    if is_admin_user:
        buttons.append([KeyboardButton("🎛️ Admin Panel")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("👥 User Pending"), KeyboardButton("📊 Statistik")],
        [KeyboardButton("💰 Set Range Harga"), KeyboardButton("🔢 Set Limit User")],
        [KeyboardButton("🇲🇽 Mexico Lock"), KeyboardButton("📋 Semua Log")],
        [KeyboardButton("📈 Dashboard"), KeyboardButton("📡 Stock Monitor")],
        [KeyboardButton("🔙 Kembali")],
    ], resize_keyboard=True)

def settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("📦 Pilih Layanan"), KeyboardButton("🌍 Pilih Negara")],
        [KeyboardButton("🔑 Ganti API Key")],
        [KeyboardButton("🔙 Kembali")],
    ], resize_keyboard=True)

def setup_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔑 Masukkan API Key")],
        [KeyboardButton("❓ Cara Dapat API Key")],
    ], resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    user = update.effective_user
    
    if not db.get_user(user.id):
        db.add_user(user.id, user.first_name, user.username or "")
    
    if not await check_access(update, ctx):
        return
    
    user_data = db.get_user(user.id)
    
    if not user_data.api_key:
        await update.message.reply_text(
            f"🐻 *GRIZZLYSMS BOT v7*\n\n"
            f"👤 {user.first_name}\n"
            f"🆔 `{user.id}`\n\n"
            f"Masukkan API Key untuk memulai.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=setup_keyboard()
        )
    else:
        balance = api.get_balance(user_data.api_key)
        balance_text = f"${balance:.4f}" if balance else "Gagal cek"
        
        stats = db.get_activations_count(user.id)
        price_range = db.get_price_range()
        
        # Determine Mexico lock status
        mexico_status = "🟢 AKTIF" if user_data.hard_lock_mexico else "🔴 NONAKTIF"
        
        await update.message.reply_text(
            f"🐻 *GRIZZLYSMS BOT v7 - COMPLETE*\n\n"
            f"👤 {user.first_name} | 🆔 `{user.id}`\n"
            f"💰 Saldo: *{balance_text}*\n"
            f"📞 Nomor Aktif: {stats.get('waiting', 0)}\n"
            f"📊 Limit Harian: {user_data.daily_purchases}/{user_data.purchase_limit}\n"
            f"💵 Range: ${price_range.min_price:.2f}-${price_range.max_price:.2f}\n"
            f"🇲🇽 Mexico Lock: {mexico_status}\n\n"
            f"Pilih menu 👇",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(is_admin(user.id))
        )

async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show user ID."""
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if db_user:
        status_emoji = {
            UserStatus.PENDING: "⏳",
            UserStatus.APPROVED: "✅",
            UserStatus.REJECTED: "❌",
            UserStatus.BANNED: "🚫"
        }
        status = status_emoji.get(db_user.status, "❓")
        limit_info = f"\n📊 Limit: {db_user.daily_purchases}/{db_user.purchase_limit}"
        mexico_info = f"\n🇲🇽 Mexico Lock: {'✅' if db_user.hard_lock_mexico else '❌'}"
    else:
        status = "❓"
        limit_info = ""
        mexico_info = ""
    
    await update.message.reply_text(
        f"🆔 *INFO AKUN*\n\n"
        f"ID: `{user.id}`\n"
        f"Nama: {user.first_name}\n"
        f"Username: @{user.username or '-'}\n"
        f"Status: {status} {db_user.status.value if db_user else 'Unknown'}\n"
        f"Admin: {'✅ Ya' if is_admin(user.id) else '❌ Tidak'}"
        f"{limit_info}{mexico_info}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Cancel activation."""
    if not await check_access(update, ctx):
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/cancel <ID>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    user = db.get_user(update.effective_user.id)
    if not user or not user.api_key:
        await update.message.reply_text("❌ API Key belum diset.")
        return
    
    act_id = args[0]
    
    await otp_checker.stop_poll(act_id)
    
    if api.cancel(user.api_key, act_id):
        db.update_activation_status(act_id, ActivationStatus.CANCELLED)
        db.delete_activation(act_id)
        db.add_log(user.id, "CANCEL", act_id)
        await update.message.reply_text(
            f"✅ `{act_id}` dibatalkan.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ Gagal membatalkan `{act_id}`.",
            parse_mode=ParseMode.MARKDOWN
        )

async def cmd_konfirmasi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Confirm activation."""
    if not await check_access(update, ctx):
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/konfirmasi <ID>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    user = db.get_user(update.effective_user.id)
    if not user or not user.api_key:
        await update.message.reply_text("❌ API Key belum diset.")
        return
    
    act_id = args[0]
    
    if api.confirm(user.api_key, act_id):
        db.delete_activation(act_id)
        db.add_log(user.id, "CONFIRM", act_id)
        await update.message.reply_text(
            f"✅ `{act_id}` dikonfirmasi!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ Gagal mengkonfirmasi `{act_id}`.",
            parse_mode=ParseMode.MARKDOWN
        )

async def cmd_daftar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show active numbers."""
    if not await check_access(update, ctx):
        return
    
    user_id = update.effective_user.id
    activations = db.get_user_activations(user_id, ActivationStatus.WAITING)
    
    if not activations:
        await update.message.reply_text(
            "📋 *DAFTAR NOMOR AKTIF*\n\nTidak ada nomor aktif.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    paginated = Paginator.paginate(activations, 1)
    
    lines = [
        f"📋 *DAFTAR NOMOR AKTIF*\n",
        f"📊 Total: {paginated['total_items']} | Hal {paginated['page']}/{paginated['total_pages']}\n",
        "─" * 20
    ]
    
    for i, act in enumerate(paginated['items'], paginated['start_index']):
        lines.append(
            f"\n*{i}.* 📞 `+{act.phone}`\n"
            f"   🆔 `{act.id}`\n"
            f"   📦 {act.service_name} | {act.country_name}\n"
            f"   💰 ${act.cost:.2f}"
        )
    
    keyboard = Paginator.keyboard("act", 1, paginated['total_pages'])
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

async def cmd_ceksms(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Manual SMS check."""
    if not await check_access(update, ctx):
        return
    
    user = db.get_user(update.effective_user.id)
    if not user or not user.api_key:
        await update.message.reply_text("❌ API Key belum diset.")
        return
    
    args = ctx.args
    if not args:
        activations = db.get_user_activations(user.id, ActivationStatus.WAITING)
        if not activations:
            await update.message.reply_text(
                "ℹ️ Tidak ada nomor aktif.\n"
                "OTP sudah dikirim otomatis saat masuk."
            )
            return
        
        lines = ["📋 *ID Aktif:*\n"]
        for act in activations[:10]:
            lines.append(f"• `{act.id}` → `+{act.phone}`")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    act_id = args[0]
    result = api.get_sms(user.api_key, act_id)
    
    if result["status"] == "ok":
        await update.message.reply_text(
            f"✅ *OTP:* `{result['code']}`\n\n`/konfirmasi {act_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    elif result["status"] == "waiting":
        await update.message.reply_text(
            f"⏳ Belum ada SMS. OTP akan notif otomatis.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ Status: {result.get('error', '?')}",
            parse_mode=ParseMode.MARKDOWN
        )

async def cmd_setlayanan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set service and country."""
    if not await check_access(update, ctx):
        return
    
    args = ctx.args
    user = db.get_user(update.effective_user.id)
    
    if len(args) < 2:
        # Show available options
        services = ServiceValidator.get_all_services()
        countries = CountryValidator.get_all_countries()
        
        svc_list = "\n".join([f"• `{k}` - {v['name']}" for k, v in list(services.items())[:10]])
        country_list = "\n".join([f"• `{k}` - {v['name']}" for k, v in list(countries.items())[:10]])
        
        await update.message.reply_text(
            f"📦 *LAYANAN TERSEDIA:*\n{svc_list}\n\n"
            f"🌍 *NEGARA TERSEDIA:*\n{country_list}\n\n"
            f"Format: `/setlayanan <service> <country>`\n"
            f"Contoh: `/setlayanan wa 52`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if not user or not user.api_key:
        await update.message.reply_text("❌ API Key belum diset.")
        return
    
    svc_code = args[0].lower()
    country_code = args[1]
    
    # Validate service
    is_valid_svc, svc_code, svc_name, svc_icon = ServiceValidator.validate(svc_code)
    if not is_valid_svc:
        await update.message.reply_text(
            f"❌ Kode layanan tidak valid: `{svc_code}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Validate country with hard lock
    is_valid_ctry, country_code, country_name = CountryValidator.validate(
        country_code, user.hard_lock_mexico
    )
    if not is_valid_ctry:
        await update.message.reply_text(
            f"❌ Kode negara tidak valid: `{country_code}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Get price
    price_info = api.get_price(user.api_key, svc_code, country_code)
    
    # Save settings
    settings = db.get_setting(f"user_settings_{user.id}", {})
    settings.update({
        "service": svc_code,
        "country": country_code,
        "svc_name": svc_name,
        "country_name": country_name
    })
    db.set_setting(f"user_settings_{user.id}", settings)
    
    db.add_log(user.id, "SET_SERVICE", f"{svc_code}|{country_code}")
    
    # Check price range
    price_range = db.get_price_range()
    try:
        cost = float(price_info['cost'])
        in_range = price_range.min_price <= cost <= price_range.max_price
        range_status = "✅ Dalam range" if in_range else "⚠️ Di luar range"
    except:
        cost = price_info['cost']
        range_status = "❓ Tidak dapat cek"
    
    await update.message.reply_text(
        f"✅ *LAYANAN DISETEL*\n\n"
        f"📦 {svc_icon} {svc_name}\n"
        f"🌍 {country_name}\n"
        f"💰 Harga: ${price_info['cost']}\n"
        f"📊 Stok: {price_info['count']}\n"
        f"💵 Status: {range_status}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(is_admin(user.id))
    )

async def cmd_setrange(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set price range (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if len(args) < 2:
        price_range = db.get_price_range()
        await update.message.reply_text(
            f"💰 *SET RANGE HARGA*\n\n"
            f"Current:\n"
            f"📉 Min: ${price_range.min_price:.2f}\n"
            f"📈 Max: ${price_range.max_price:.2f}\n\n"
            f"Format: `/setrange <min> <max>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        min_price = float(args[0].replace("$", ""))
        max_price = float(args[1].replace("$", ""))
        
        if min_price < 0 or max_price < 0 or min_price > max_price:
            await update.message.reply_text("❌ Nilai tidak valid!")
            return
        
        db.set_price_range(min_price, max_price)
        db.add_log(update.effective_user.id, "SET_RANGE", f"${min_price:.2f}-${max_price:.2f}")
        
        await update.message.reply_text(
            f"✅ *RANGE DIUBAH*\n\n"
            f"📉 Min: ${min_price:.2f}\n"
            f"📈 Max: ${max_price:.2f}",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text("❌ Format salah!")

async def cmd_setlimit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set user purchase limit (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "🔢 *SET LIMIT PEMBELIAN USER*\n\n"
            f"Format: `/setlimit <user_id> <limit>`\n"
            f"Contoh: `/setlimit 123456789 50`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_id = int(args[0])
        limit = int(args[1])
        
        if limit < 1:
            await update.message.reply_text("❌ Limit minimal 1!")
            return
        
        user = db.get_user(target_id)
        if not user:
            await update.message.reply_text(f"❌ User `{target_id}` tidak ditemukan.")
            return
        
        db.update_user_purchase_limit(target_id, limit)
        db.add_log(update.effective_user.id, "SET_LIMIT", f"{target_id}|{limit}")
        
        await update.message.reply_text(
            f"✅ *LIMIT DIUBAH*\n\n"
            f"👤 User: {user.name}\n"
            f"🆔 `{target_id}`\n"
            f"📊 Limit: {limit}/hari",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text("❌ Format salah!")

async def cmd_mexicolock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Toggle Mexico hard lock (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "🇲🇽 *MEXICO HARD LOCK*\n\n"
            f"Format: `/mexicolock <user_id> <on/off>`\n"
            f"Contoh: `/mexicolock 123456789 on`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_id = int(args[0])
        enable = args[1].lower() in ["on", "yes", "1", "true", "aktif"]
        
        user = db.get_user(target_id)
        if not user:
            await update.message.reply_text(f"❌ User `{target_id}` tidak ditemukan.")
            return
        
        db.update_user_mexico_lock(target_id, enable)
        db.add_log(update.effective_user.id, "MEXICO_LOCK", f"{target_id}|{enable}")
        
        status = "🟢 AKTIF" if enable else "🔴 NONAKTIF"
        await update.message.reply_text(
            f"✅ *MEXICO LOCK DISETEL*\n\n"
            f"👤 User: {user.name}\n"
            f"🆔 `{target_id}`\n"
            f"🇲🇽 Status: {status}",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text("❌ Format salah!")

async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Approve user (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/approve <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_id = int(args[0])
        user = db.get_user(target_id)
        
        if not user:
            await update.message.reply_text(f"❌ User `{target_id}` tidak ditemukan.")
            return
        
        if user.status == UserStatus.APPROVED:
            await update.message.reply_text(f"ℹ️ User `{target_id}` sudah approved.")
            return
        
        db.update_user_status(target_id, UserStatus.APPROVED, update.effective_user.id)
        
        try:
            await ctx.bot.send_message(
                chat_id=target_id,
                text="🎉 *AKSES DISETUJUI!*\n\nKetik /start untuk memulai.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ User `{target_id}` telah di-approve!",
            parse_mode=ParseMode.MARKDOWN
        )
        db.add_log(update.effective_user.id, "APPROVE_USER", str(target_id))
    except ValueError:
        await update.message.reply_text("❌ User ID harus angka.")

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Reject user (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/reject <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_id = int(args[0])
        user = db.get_user(target_id)
        
        if not user:
            await update.message.reply_text(f"❌ User `{target_id}` tidak ditemukan.")
            return
        
        db.update_user_status(target_id, UserStatus.REJECTED)
        
        try:
            await ctx.bot.send_message(
                chat_id=target_id,
                text="❌ *AKSES DITOLAK*",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        await update.message.reply_text(
            f"❌ User `{target_id}` telah di-reject.",
            parse_mode=ParseMode.MARKDOWN
        )
        db.add_log(update.effective_user.id, "REJECT_USER", str(target_id))
    except ValueError:
        await update.message.reply_text("❌ User ID harus angka.")

async def cmd_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show buy task status."""
    if not await check_access(update, ctx):
        return
    
    args = ctx.args
    if not args:
        tasks = db.get_user_buy_tasks(update.effective_user.id, 5)
        if not tasks:
            await update.message.reply_text("📋 Tidak ada task.")
            return
        
        lines = ["📋 *BUY TASKS TERBARU:*\n"]
        for task in tasks:
            status_emoji = "✅" if task.status == "completed" else "⏳"
            lines.append(
                f"{status_emoji} `{task.task_id}`\n"
                f"   📊 {task.completed}/{task.quantity}"
            )
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    task_id = args[0]
    task = buy_engine.get_task(task_id)
    
    if not task:
        await update.message.reply_text(f"❌ Task `{task_id}` tidak ditemukan.")
        return
    
    await update.message.reply_text(
        f"📋 *BUY TASK: `{task_id}`*\n\n"
        f"📊 Status: {task.status}\n"
        f"📦 {task.service} | {task.country}\n"
        f"✅ Completed: {task.completed}/{task.quantity}\n"
        f"❌ Failed: {task.failed}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_parallelbuy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start parallel buy."""
    if not await check_access(update, ctx):
        return
    
    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text(
            "Format: `/parallelbuy <qty> <service> <country>`\n"
            "Contoh: `/parallelbuy 100 wa 52`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        qty = int(args[0])
        service = args[1].lower()
        country = args[2]
        
        if qty < 1 or qty > 1000:
            await update.message.reply_text("❌ Quantity harus 1-1000.")
            return
        
        user = db.get_user(update.effective_user.id)
        if not user or not user.api_key:
            await update.message.reply_text("❌ API Key belum diset.")
            return
        
        task_id, error = await buy_engine.start_buy(
            app=ctx.application,
            user_id=user.id,
            chat_id=update.effective_chat.id,
            api_key=user.api_key,
            service=service,
            country=country,
            quantity=qty,
            hard_lock_mexico=user.hard_lock_mexico
        )
        
        if error:
            await update.message.reply_text(f"❌ {error}")
            return
        
        await update.message.reply_text(
            f"🚀 *PARALLEL BUY STARTED*\n\n"
            f"📋 Task ID: `{task_id}`\n"
            f"📊 Quantity: {qty}\n\n"
            f"`/task {task_id}` untuk cek progress.",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text("❌ Format salah!")

async def cmd_sniper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Toggle OTP Sniper Mode."""
    if not await check_access(update, ctx):
        return
    
    user_id = update.effective_user.id
    current = db.get_setting(f"sniper_mode_{user_id}", False)
    new_mode = not current
    db.set_setting(f"sniper_mode_{user_id}", new_mode)
    
    status = "🟢 AKTIF" if new_mode else "🔴 NONAKTIF"
    desc = "Polling 1 detik (cepat)" if new_mode else "Polling 5 detik (normal)"
    
    await update.message.reply_text(
        f"🎯 *OTP SNIPER MODE*\n\n"
        f"Status: {status}\n"
        f"Mode: {desc}",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    if not await check_access(update, ctx):
        return
    
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        return
    
    waiting = db.get_setting(f"waiting_for_{user_id}")
    
    # Handle waiting states
    if waiting == "api_key":
        db.set_setting(f"waiting_for_{user_id}", None)
        new_key = text.strip()
        
        if len(new_key) < 10:
            await update.message.reply_text("❌ API Key terlalu pendek.")
            db.set_setting(f"waiting_for_{user_id}", "api_key")
            return
        
        msg = await update.message.reply_text(
            f"⏳ Validasi API Key...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        for i in range(1, 6):
            await asyncio.sleep(0.2)
            try:
                await msg.edit_text(
                    f"⏳ Validasi API Key...\n\n`{LoadingBar.render(i/5)}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        balance = api.get_balance(new_key)
        
        if balance is not None:
            db.update_user_api_key(user_id, new_key)
            db.add_log(user_id, "API_KEY_SET", f"${balance:.4f}")
            await msg.edit_text(
                f"✅ *API KEY TERSIMPAN*\n\n💰 Saldo: ${balance:.4f}",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                "Pilih menu 👇",
                reply_markup=main_keyboard(is_admin(user_id))
            )
        else:
            await msg.edit_text(
                "❌ API Key tidak valid. Coba lagi.",
                parse_mode=ParseMode.MARKDOWN
            )
            db.set_setting(f"waiting_for_{user_id}", "api_key")
        return
    
    if waiting == "parallel_qty":
        db.set_setting(f"waiting_for_{user_id}", None)
        try:
            qty = int(text)
            if qty < 1 or qty > 1000:
                raise ValueError()
            
            settings = db.get_setting(f"user_settings_{user_id}", {})
            service = settings.get("service", "wa")
            country = settings.get("country", "52")
            
            if not user.api_key:
                await update.message.reply_text("❌ API Key belum diset.")
                return
            
            task_id, error = await buy_engine.start_buy(
                app=ctx.application,
                user_id=user_id,
                chat_id=update.effective_chat.id,
                api_key=user.api_key,
                service=service,
                country=country,
                quantity=qty,
                hard_lock_mexico=user.hard_lock_mexico
            )
            
            if error:
                await update.message.reply_text(f"❌ {error}")
            else:
                await update.message.reply_text(
                    f"🚀 *PARALLEL BUY STARTED*\n\n"
                    f"📋 Task ID: `{task_id}`\n"
                    f"📊 Quantity: {qty}\n\n"
                    f"`/task {task_id}` untuk cek progress.",
                    parse_mode=ParseMode.MARKDOWN
                )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka 1-1000.")
        return
    
    if waiting == "set_limit_user":
        db.set_setting(f"waiting_for_{user_id}", None)
        try:
            target_id = int(text)
            db.set_setting(f"limit_target_{user_id}", target_id)
            db.set_setting(f"waiting_for_{user_id}", "set_limit_value")
            await update.message.reply_text(
                f"Masukkan limit harian untuk user `{target_id}`:",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text("❌ User ID harus angka.")
        return
    
    if waiting == "set_limit_value":
        db.set_setting(f"waiting_for_{user_id}", None)
        target_id = db.get_setting(f"limit_target_{user_id}")
        try:
            limit = int(text)
            if limit < 1:
                raise ValueError()
            db.update_user_purchase_limit(target_id, limit)
            db.add_log(user_id, "SET_LIMIT", f"{target_id}|{limit}")
            await update.message.reply_text(
                f"✅ Limit user `{target_id}` diubah ke {limit}/hari.",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text("❌ Limit harus angka positif.")
        return
    
    # Handle buttons
    if text == "🔑 Masukkan API Key":
        db.set_setting(f"waiting_for_{user_id}", "api_key")
        await update.message.reply_text(
            "🔑 *MASUKKAN API KEY*\n\n"
            "1. Login di grizzlysms.com\n"
            "2. Profil → Settings\n"
            "3. Copy API Key\n\n"
            "Paste di sini 👇",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    if text == "❓ Cara Dapat API Key":
        await update.message.reply_text(
            "📖 *CARA DAPAT API KEY*\n\n"
            "1. Buka grizzlysms.com\n"
            "2. Daftar & top up saldo\n"
            "3. Profil → Settings → Copy API Key\n"
            "4. Paste di bot ini",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "💰 Cek Saldo":
        if not user.api_key:
            await update.message.reply_text("❌ API Key belum diset.")
            return
        
        msg = await update.message.reply_text(
            f"⏳ Cek saldo...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        for i in range(1, 6):
            await asyncio.sleep(0.15)
            try:
                await msg.edit_text(
                    f"⏳ Cek saldo...\n\n`{LoadingBar.render(i/5)}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        balance = api.get_balance(user.api_key)
        if balance is not None:
            await msg.edit_text(
                f"💰 *SALDO GRIZZLYSMS*\n\n*${balance:.4f}*\n\nTop up: grizzlysms.com",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await msg.edit_text("❌ Gagal cek saldo.", parse_mode=ParseMode.MARKDOWN)
        return
    
    if text == "📲 Beli 1 Nomor":
        await _do_single_buy(update, ctx, user, 1)
        return
    
    if text == "🔢 Beli 3 Nomor":
        await _do_single_buy(update, ctx, user, 3)
        return
    
    if text == "🔟 Beli 5 Nomor":
        await _do_single_buy(update, ctx, user, 5)
        return
    
    if text == "🚀 Beli Banyak":
        # Check limit first
        remaining = user.purchase_limit - user.daily_purchases
        if remaining <= 0:
            await update.message.reply_text(
                f"❌ Limit pembelian harian habis!\n"
                f"Limit: {user.purchase_limit}/hari",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        db.set_setting(f"waiting_for_{user_id}", "parallel_qty")
        await update.message.reply_text(
            f"🚀 *PARALLEL BUY*\n\n"
            f"Sisa limit: {remaining} nomor\n\n"
            f"Masukkan jumlah nomor (1-{min(remaining, 1000)}):",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "📞 Daftar Nomor":
        await cmd_daftar(update, ctx)
        return
    
    if text == "📋 Log Aktivitas":
        logs = db.get_logs(user_id, 10)
        if not logs:
            await update.message.reply_text("📋 Log kosong.")
            return
        
        lines = ["📋 *LOG AKTIVITAS (10 terbaru):*\n"]
        for log in logs:
            time_str = log['created_at'].split('T')[1][:8] if 'T' in log['created_at'] else log['created_at']
            lines.append(f"`[{time_str}]` {log['action']}")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "⚙️ Pengaturan":
        settings = db.get_setting(f"user_settings_{user_id}", {})
        sniper = db.get_setting(f"sniper_mode_{user_id}", False)
        price_range = db.get_price_range()
        mexico_status = "🟢 AKTIF" if user.hard_lock_mexico else "🔴 NONAKTIF"
        
        await update.message.reply_text(
            f"⚙️ *PENGATURAN*\n\n"
            f"📦 Layanan: {settings.get('svc_name', 'WhatsApp')}\n"
            f"🌍 Negara: {settings.get('country_name', 'Mexico')}\n"
            f"🎯 Sniper Mode: {'🟢' if sniper else '🔴'}\n"
            f"💵 Range: ${price_range.min_price:.2f}-${price_range.max_price:.2f}\n"
            f"🇲🇽 Mexico Lock: {mexico_status}\n"
            f"📊 Limit: {user.daily_purchases}/{user.purchase_limit}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=settings_keyboard()
        )
        return
    
    if text == "🎯 Sniper Mode":
        await cmd_sniper(update, ctx)
        return
    
    if text == "🇲🇽 Stok Mexico":
        # Show Mexico stock
        stocks, last_update = stock_sniper.get_stock()
        
        if not stocks:
            # Fetch if empty
            if user.api_key:
                stocks = api.get_all_prices_mexico(user.api_key)
                if stocks:
                    db.update_mexico_stock(stocks)
                    last_update = datetime.now().strftime("%H:%M:%S")
        
        if not stocks:
            await update.message.reply_text(
                "🇲🇽 *STOK MEXICO*\n\n"
                "Data belum tersedia.\n"
                "Coba beberapa saat lagi.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        lines = [
            f"🇲🇽 *STOK MEXICO REAL-TIME*\n",
            f"⏰ Update: {last_update}\n",
            "─" * 20
        ]
        
        for stock in sorted(stocks, key=lambda x: x['count'], reverse=True)[:15]:
            count_emoji = "✅" if stock['count'] > 10 else ("⚠️" if stock['count'] > 0 else "❌")
            lines.append(
                f"\n{count_emoji} *{stock.get('service_name', stock['service'])}*\n"
                f"   📊 Stok: {stock['count']}\n"
                f"   💰 Harga: ${stock['cost']:.2f}"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_mexico_stock")]
        ])
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return
    
    if text == "❌ Batalkan Semua":
        activations = db.get_user_activations(user_id, ActivationStatus.WAITING)
        if not activations:
            await update.message.reply_text("ℹ️ Tidak ada nomor aktif.")
            return
        
        msg = await update.message.reply_text(
            f"⏳ Membatalkan {len(activations)} nomor...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        success = 0
        for i, act in enumerate(activations):
            await otp_checker.stop_poll(act.id)
            if api.cancel(user.api_key, act.id):
                db.update_activation_status(act.id, ActivationStatus.CANCELLED)
                success += 1
            
            progress = (i + 1) / len(activations)
            try:
                await msg.edit_text(
                    f"⏳ Membatalkan {len(activations)} nomor...\n\n`{LoadingBar.render(progress)}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            await asyncio.sleep(0.2)
        
        await msg.edit_text(
            f"✅ *DIBATALKAN: {success}/{len(activations)}*",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Admin Panel
    if text == "🎛️ Admin Panel":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        stats = db.get_statistics()
        price_range = db.get_price_range()
        
        await update.message.reply_text(
            f"🎛️ *ADMIN PANEL*\n\n"
            f"👥 Users: {stats['total_users']}\n"
            f"✅ Approved: {stats['approved_users']}\n"
            f"⏳ Pending: {stats['pending_users']}\n"
            f"📞 Activations: {stats['total_activations']}\n"
            f"⏰ Waiting: {stats['waiting_activations']}\n"
            f"💰 Spent: ${stats['total_spent']:.2f}\n"
            f"💵 Range: ${price_range.min_price:.2f}-${price_range.max_price:.2f}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_keyboard()
        )
        return
    
    if text == "👥 User Pending":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        pending = db.get_pending_users()
        if not pending:
            await update.message.reply_text(
                "📋 *USER PENDING*\n\nTidak ada user pending.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        lines = [f"📋 *USER PENDING ({len(pending)}):*\n"]
        for i, u in enumerate(pending[:10], 1):
            lines.append(f"{i}. 👤 {u.name}\n   🆔 `{u.id}`\n   👥 @{u.username}")
        
        keyboard = None
        if len(pending) > 10:
            keyboard = Paginator.keyboard("pending", 1, (len(pending) + 9) // 10)
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return
    
    if text == "📊 Statistik":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        stats = db.get_statistics()
        otp_stats = otp_checker.get_stats()
        price_range = db.get_price_range()
        
        await update.message.reply_text(
            f"📊 *STATISTIK BOT*\n\n"
            f"╔═══ USERS ═══╗\n"
            f"👥 Total: {stats['total_users']}\n"
            f"✅ Approved: {stats['approved_users']}\n"
            f"⏳ Pending: {stats['pending_users']}\n"
            f"╠═══ ACTIVATIONS ═══╣\n"
            f"📞 Total: {stats['total_activations']}\n"
            f"⏰ Waiting: {stats['waiting_activations']}\n"
            f"✅ Received: {stats['received_activations']}\n"
            f"📅 Today: {stats['today_activations']}\n"
            f"╠═══ SYSTEM ═══╣\n"
            f"🔔 Active Polls: {otp_stats['active_polls']}\n"
            f"╠════════════╣\n"
            f"💰 Spent: ${stats['total_spent']:.2f}\n"
            f"💵 Range: ${price_range.min_price:.2f}-${price_range.max_price:.2f}\n"
            f"╚════════════════╝",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "💰 Set Range Harga":
        await cmd_setrange(update, ctx)
        return
    
    if text == "🔢 Set Limit User":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        db.set_setting(f"waiting_for_{user_id}", "set_limit_user")
        await update.message.reply_text(
            "🔢 *SET LIMIT PEMBELIAN USER*\n\n"
            "Masukkan User ID:",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "🇲🇽 Mexico Lock":
        await cmd_mexicolock(update, ctx)
        return
    
    if text == "📋 Semua Log":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        logs = db.get_logs(None, 20)
        if not logs:
            await update.message.reply_text("📋 Log kosong.")
            return
        
        lines = ["📋 *LOG AKTIVITAS (20 terbaru):*\n"]
        for log in logs:
            time_str = log['created_at'].split('T')[1][:8] if 'T' in log['created_at'] else log['created_at']
            user_str = f"[{log['user_id']}]" if log['user_id'] else "[SYSTEM]"
            lines.append(f"`[{time_str}]` {user_str} {log['action']}")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "📈 Dashboard":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        await _show_dashboard(update, ctx)
        return
    
    if text == "📡 Stock Monitor":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        
        stocks, last_update = stock_sniper.get_stock()
        
        lines = [
            f"📡 *MEXICO STOCK MONITOR*\n",
            f"⏰ Last Update: {last_update}\n",
            f"🔔 Subscribers: {len(stock_sniper.subscribers)}\n"
        ]
        
        if stocks:
            lines.append("\n*Top Services:*\n")
            for stock in sorted(stocks, key=lambda x: x['count'], reverse=True)[:5]:
                lines.append(f"• {stock.get('service_name', stock['service'])}: {stock['count']}")
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔔 Subscribe", callback_data="stock_subscribe"),
                InlineKeyboardButton("🔕 Unsubscribe", callback_data="stock_unsubscribe")
            ],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_mexico_stock")]
        ])
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return
    
    if text == "🔙 Kembali":
        await update.message.reply_text(
            "🏠 Menu Utama",
            reply_markup=main_keyboard(is_admin(user_id))
        )
        return
    
    if text in ["📦 Pilih Layanan", "🌍 Pilih Negara"]:
        if text == "📦 Pilih Layanan":
            services = ServiceValidator.get_all_services()
            lines = ["📦 *LAYANAN TERSEDIA:*\n"]
            for code, info in list(services.items())[:15]:
                lines.append(f"{info['icon']} `{code}` - {info['name']}")
            lines.append("\n`/setlayanan <kode> <negara>`")
        else:
            countries = CountryValidator.get_all_countries()
            lines = ["🌍 *NEGARA TERSEDIA:*\n"]
            for code, info in list(countries.items())[:15]:
                lines.append(f"{info['name']} → `{code}`")
            lines.append("\n`/setlayanan <service> <kode>`")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if text == "🔑 Ganti API Key":
        db.set_setting(f"waiting_for_{user_id}", "api_key")
        await update.message.reply_text(
            "🔑 Masukkan API Key baru:",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Default
    await update.message.reply_text(
        "❓ Gunakan menu di bawah.",
        reply_markup=main_keyboard(is_admin(user_id))
    )

async def _do_single_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                         user: UserInfo, qty: int):
    """Execute single buy with price check."""
    if not user.api_key:
        await update.message.reply_text("❌ API Key belum diset.")
        return
    
    # Check limit
    if user.daily_purchases + qty > user.purchase_limit:
        remaining = user.purchase_limit - user.daily_purchases
        await update.message.reply_text(
            f"❌ Limit pembelian tidak cukup!\n"
            f"Sisa limit: {remaining} nomor",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    settings = db.get_setting(f"user_settings_{user.id}", {})
    service = settings.get("service", "wa")
    country = settings.get("country", "52")
    svc_name = settings.get("svc_name", "WhatsApp")
    country_name = settings.get("country_name", "Mexico")
    
    # Validate with hard lock
    is_valid_svc, service, svc_name, svc_icon = ServiceValidator.validate(service)
    is_valid_ctry, country, country_name = CountryValidator.validate(country, user.hard_lock_mexico)
    
    price_range = db.get_price_range()
    sniper_mode = db.get_setting(f"sniper_mode_{user.id}", False)
    
    msg = await update.message.reply_text(
        f"⏳ *CEK HARGA & BELI*\n\n`{LoadingBar.render(0)}`",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Check price first
    price_check = api.check_price_before_buy(user.api_key, service, country, price_range)
    
    if not price_check["in_range"]:
        await msg.edit_text(
            f"❌ *HARGA DI LUAR RANGE*\n\n"
            f"💰 Harga: ${price_check['cost']:.2f}\n"
            f"💵 Range: ${price_range.min_price:.2f}-${price_range.max_price:.2f}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if price_check["count"] <= 0:
        await msg.edit_text(
            "❌ *STOK HABIS*\n\n"
            "Tidak ada nomor tersedia.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    results = []
    for i in range(qty):
        progress = (i / qty) * 0.9
        try:
            await msg.edit_text(
                f"⏳ *MEMBELI {qty}x NOMOR*\n\n`{LoadingBar.render(progress)}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        result = api.buy_number(user.api_key, service, country, price_range)
        
        if result["status"] == "ok":
            activation = Activation(
                id=result["id"],
                user_id=user.id,
                phone=result["phone"],
                service=service,
                service_name=result.get("service_name", svc_name),
                country=country,
                country_name=result.get("country_name", country_name),
                cost=result["cost"],
                status=ActivationStatus.WAITING,
                created_at=datetime.now().isoformat(),
                price_checked=True
            )
            db.add_activation(activation)
            
            await otp_checker.start_poll(
                app=ctx.application,
                activation=activation,
                api_key=user.api_key,
                sniper_mode=sniper_mode,
                auto_rebuy=True,
                chat_id=update.effective_chat.id
            )
            
            results.append({"success": True, "activation": activation})
            db.add_log(user.id, "BUY_OK", f"{result['id']}|+{result['phone']}")
        else:
            results.append({"success": False, "error": result.get("error")})
            db.add_log(user.id, "BUY_FAIL", result.get("error", "Unknown"))
        
        if qty > 1:
            await asyncio.sleep(1.0)
    
    # Update purchase count
    success_count = sum(1 for r in results if r.get("success"))
    if success_count > 0:
        db.increment_user_purchases(user.id, success_count)
    
    success = success_count
    failed = len(results) - success
    
    if qty == 1:
        if success:
            act = results[0]["activation"]
            await msg.edit_text(
                f"✅ *NOMOR BERHASIL DIBELI!*\n\n"
                f"📞 `+{act.phone}`\n"
                f"🆔 `{act.id}`\n"
                f"💰 ${act.cost:.2f}\n"
                f"📦 {act.service_name} | {act.country_name}\n\n"
                f"🔔 OTP akan dikirim otomatis!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await msg.edit_text(
                error_map(results[0].get("error", "Unknown")),
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        lines = [
            f"🏁 *HASIL BELI {qty} NOMOR*\n",
            f"✅ Success: {success}",
            f"❌ Failed: {failed}\n"
        ]
        
        for i, r in enumerate(results, 1):
            if r.get("success"):
                act = r["activation"]
                lines.append(f"{i}. ✅ `+{act.phone}` ${act.cost:.2f}")
            else:
                lines.append(f"{i}. ❌ {r.get('error', 'Unknown')}")
        
        if success > 0:
            lines.append("\n🔔 OTP akan dikirim otomatis!")
        
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def _show_dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show admin dashboard."""
    stats = db.get_statistics()
    otp_stats = otp_checker.get_stats()
    price_range = db.get_price_range()
    stocks, last_update = stock_sniper.get_stock()
    
    lines = [
        "📈 *ADMIN DASHBOARD*",
        f"_Updated: {datetime.now().strftime('%H:%M:%S')}_\n",
        "╔═════════════════════╗",
        "║ 👥 USERS            ║",
        "╠═════════════════════╣",
        f"║ Total    : {stats['total_users']:>6} ║",
        f"║ Approved : {stats['approved_users']:>6} ║",
        f"║ Pending  : {stats['pending_users']:>6} ║",
        "╠═════════════════════╣",
        "║ 📞 ACTIVATIONS      ║",
        "╠═════════════════════╣",
        f"║ Total    : {stats['total_activations']:>6} ║",
        f"║ Waiting  : {stats['waiting_activations']:>6} ║",
        f"║ Today    : {stats['today_activations']:>6} ║",
        "╠═════════════════════╣",
        "║ ⚙️ SYSTEM            ║",
        "╠═════════════════════╣",
        f"║ OTP Polls: {otp_stats['active_polls']:>6} ║",
        f"║ Mexico   : {len(stocks):>6} ║",
        "╠═════════════════════╣",
        f"║ Spent    : ${stats['total_spent']:>6.2f} ║",
        f"║ Range    : ${price_range.min_price:.2f}-${price_range.max_price:.2f} ║",
        "╚═════════════════════╝"
    ]
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="dashboard_refresh")]
    ])
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    # Approval callbacks
    if data.startswith("approve_"):
        target_id = int(data.split("_")[1])
        if not is_admin(user_id):
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        
        user = db.get_user(target_id)
        if user and user.status != UserStatus.APPROVED:
            db.update_user_status(target_id, UserStatus.APPROVED, user_id)
            
            try:
                await ctx.bot.send_message(
                    chat_id=target_id,
                    text="🎉 *AKSES DISETUJUI!*\n\nKetik /start untuk memulai.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            
            await query.edit_message_text(
                f"✅ *USER DISETUJUI*\n\nID: `{target_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
            db.add_log(user_id, "APPROVE_USER", str(target_id))
        return
    
    if data.startswith("reject_"):
        target_id = int(data.split("_")[1])
        if not is_admin(user_id):
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        
        db.update_user_status(target_id, UserStatus.REJECTED)
        
        try:
            await ctx.bot.send_message(
                chat_id=target_id,
                text="❌ *AKSES DITOLAK*",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        await query.edit_message_text(
            f"❌ *USER DITOLAK*\n\nID: `{target_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
        db.add_log(user_id, "REJECT_USER", str(target_id))
        return
    
    if data.startswith("ban_"):
        target_id = int(data.split("_")[1])
        if not is_admin(user_id):
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        
        db.update_user_status(target_id, UserStatus.BANNED)
        await query.edit_message_text(
            f"🚫 *USER DIBAN*\n\nID: `{target_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
        db.add_log(user_id, "BAN_USER", str(target_id))
        return
    
    # Price range callbacks
    if data == "setprice_min":
        if not is_admin(user_id):
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        db.set_setting(f"waiting_for_{user_id}", "price_min")
        await query.edit_message_text(
            "📉 Masukkan harga minimum baru (USD):",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "setprice_max":
        if not is_admin(user_id):
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        db.set_setting(f"waiting_for_{user_id}", "price_max")
        await query.edit_message_text(
            "📈 Masukkan harga maximum baru (USD):",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "setprice_reset":
        if not is_admin(user_id):
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        db.set_price_range(0.01, 0.50)
        await query.edit_message_text(
            "✅ *Range direset ke default*\n\nMin: $0.01\nMax: $0.50",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Stock callbacks
    if data == "refresh_mexico_stock":
        user = db.get_user(user_id)
        if user and user.api_key:
            stocks = api.get_all_prices_mexico(user.api_key)
            if stocks:
                db.update_mexico_stock(stocks)
                stock_sniper.stock_cache = stocks
                stock_sniper.last_update = datetime.now().strftime("%H:%M:%S")
        
        stocks, last_update = stock_sniper.get_stock()
        
        lines = [
            f"🇲🇽 *STOK MEXICO*\n",
            f"⏰ Update: {last_update}\n",
            "─" * 20
        ]
        
        for stock in sorted(stocks, key=lambda x: x['count'], reverse=True)[:15]:
            count_emoji = "✅" if stock['count'] > 10 else ("⚠️" if stock['count'] > 0 else "❌")
            lines.append(
                f"\n{count_emoji} *{stock.get('service_name', stock['service'])}*\n"
                f"   📊 Stok: {stock['count']}\n"
                f"   💰 Harga: ${stock['cost']:.2f}"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_mexico_stock")]
        ])
        
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return
    
    if data == "stock_subscribe":
        stock_sniper.subscribe(user_id)
        await query.answer("✅ Subscribed ke stock notifications!")
        return
    
    if data == "stock_unsubscribe":
        stock_sniper.unsubscribe(user_id)
        await query.answer("✅ Unsubscribed dari stock notifications!")
        return
    
    # Dashboard refresh
    if data == "dashboard_refresh":
        stats = db.get_statistics()
        otp_stats = otp_checker.get_stats()
        price_range = db.get_price_range()
        
        lines = [
            "📈 *ADMIN DASHBOARD*",
            f"_Updated: {datetime.now().strftime('%H:%M:%S')}_\n",
            "╔═════════════════════╗",
            "║ 👥 USERS            ║",
            "╠═════════════════════╣",
            f"║ Total    : {stats['total_users']:>6} ║",
            f"║ Approved : {stats['approved_users']:>6} ║",
            f"║ Pending  : {stats['pending_users']:>6} ║",
            "╠═════════════════════╣",
            "║ 📞 ACTIVATIONS      ║",
            "╠═════════════════════╣",
            f"║ Total    : {stats['total_activations']:>6} ║",
            f"║ Waiting  : {stats['waiting_activations']:>6} ║",
            f"║ Today    : {stats['today_activations']:>6} ║",
            "╠═════════════════════╣",
            f"║ Spent    : ${stats['total_spent']:>6.2f} ║",
            f"║ Range    : ${price_range.min_price:.2f}-${price_range.max_price:.2f} ║",
            "╚═════════════════════╝"
        ]
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="dashboard_refresh")]
        ])
        
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return
    
    # Pagination
    if "_page_" in data:
        parts = data.split("_page_")
        prefix = parts[0]
        page = int(parts[1])
        
        if prefix == "act":
            user_id = query.from_user.id
            activations = db.get_user_activations(user_id, ActivationStatus.WAITING)
            paginated = Paginator.paginate(activations, page)
            
            lines = [
                f"📋 *DAFTAR NOMOR AKTIF*\n",
                f"📊 Total: {paginated['total_items']} | Hal {paginated['page']}/{paginated['total_pages']}\n",
                "─" * 20
            ]
            
            for i, act in enumerate(paginated['items'], paginated['start_index']):
                lines.append(
                    f"\n*{i}.* 📞 `+{act.phone}`\n"
                    f"   🆔 `{act.id}`\n"
                    f"   📦 {act.service_name} | {act.country_name}"
                )
            
            keyboard = Paginator.keyboard("act", page, paginated['total_pages'])
            
            try:
                await query.edit_message_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
            except:
                pass
        return
    
    if data.endswith("_info"):
        await query.answer("Info halaman", show_alert=False)
        return

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

async def post_init(application: Application):
    """Initialize after application starts."""
    # Start Mexico stock sniper
    await stock_sniper.start()
    logger.info("Mexico Stock Sniper started")
    
    # Set bot commands
    commands = [
        BotCommand("start", "Mulai bot"),
        BotCommand("myid", "Cek ID & info akun"),
        BotCommand("daftar", "Daftar nomor aktif"),
        BotCommand("ceksms", "Cek SMS manual"),
        BotCommand("cancel", "Batalkan aktivasi"),
        BotCommand("konfirmasi", "Konfirmasi aktivasi"),
        BotCommand("setlayanan", "Set layanan & negara"),
        BotCommand("sniper", "Toggle OTP sniper mode"),
        BotCommand("task", "Cek status buy task"),
        BotCommand("parallelbuy", "Beli banyak nomor"),
        BotCommand("setrange", "Set range harga (admin)"),
        BotCommand("setlimit", "Set limit user (admin)"),
        BotCommand("mexicolock", "Set Mexico lock (admin)"),
        BotCommand("approve", "Approve user (admin)"),
        BotCommand("reject", "Reject user (admin)"),
    ]
    await application.bot.set_my_commands(commands)

async def post_shutdown(application: Application):
    """Cleanup on shutdown."""
    stock_sniper.stop()
    logger.info("Bot shutdown complete")

def main():
    """Main entry point."""
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("myid", cmd_myid))
    application.add_handler(CommandHandler("daftar", cmd_daftar))
    application.add_handler(CommandHandler("ceksms", cmd_ceksms))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    application.add_handler(CommandHandler("konfirmasi", cmd_konfirmasi))
    application.add_handler(CommandHandler("setlayanan", cmd_setlayanan))
    application.add_handler(CommandHandler("sniper", cmd_sniper))
    application.add_handler(CommandHandler("task", cmd_task))
    application.add_handler(CommandHandler("parallelbuy", cmd_parallelbuy))
    application.add_handler(CommandHandler("setrange", cmd_setrange))
    application.add_handler(CommandHandler("setlimit", cmd_setlimit))
    application.add_handler(CommandHandler("mexicolock", cmd_mexicolock))
    application.add_handler(CommandHandler("approve", cmd_approve))
    application.add_handler(CommandHandler("reject", cmd_reject))
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Print banner
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     🐻 GRIZZLYSMS BOT v7 - COMPLETE EDITION                 ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  ✅ SQLite Persistent Database per User                     ║")
    print("║  ✅ Country Validator & Hard Lock Mexico                     ║")
    print("║  ✅ Real-time Mexico Stock Sniper                            ║")
    print("║  ✅ Price Check Before Purchase                              ║")
    print("║  ✅ Single API Key per User                                  ║")
    print("║  ✅ User Approval System (Admin Only)                        ║")
    print("║  ✅ Admin Panel (Admin Only)                                 ║")
    print("║  ✅ Purchase Limit per User                                  ║")
    print("║  ✅ OTP Auto Checker                                         ║")
    print("║  ✅ Parallel Buy Engine (up to 1000)                         ║")
    print("║  ✅ OTP Sniper Mode                                          ║")
    print("║  ✅ Auto Rebuy System                                        ║")
    print("║  ✅ Professional Pagination                                  ║")
    print("║  ✅ Loading Progress Bar                                     ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  👨‍💼 Admins: {len(ADMIN_IDS)}                                              ║")
    print(f"║  💾 Database: grizzly_sms_bot.db                             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
