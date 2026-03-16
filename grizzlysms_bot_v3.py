#!/usr/bin/env python3
"""
🐻 GrizzlySMS Telegram Bot v5 - ENHANCED VERSION
CHANGELOG v5:
- [FITUR BARU] Set Range Harga: Admin bisa set min/max harga pembelian
- [FITUR BARU] Sistem Approve/Reject User dengan tombol inline
- [FITUR BARU] Loading Bar Profesional dengan animasi progress
- [FITUR BARU] Pagination Profesional untuk daftar nomor, log, dan user
- [IMPROVEMENT] UI/UX lebih profesional dan informatif
"""

import logging
import requests
import asyncio
import json
import os
import urllib.parse
import time
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURASI
# ═══════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7658474148:AAEhKWWaf7_fdP3jAoIYiUnda1bwkOrCVZs")

# Admin IDs - yang bisa approve/reject user dan set range harga
ADMIN_IDS = [
    7230950406,
    # tambah admin ID lain di sini
]

# User yang sudah di-approve (akan diupdate saat runtime)
APPROVED_USERS = set(ADMIN_IDS)  # Admin auto-approved

# User yang pending approval
PENDING_USERS = {}  # {user_id: {"name": str, "username": str, "time": str}}

# Range harga default (dalam USD)
PRICE_RANGE = {
    "min": 0.01,
    "max": 0.50
}

API_BASE  = "https://grizzlysms.com/stubs/handler_api.php"
API_BASE2 = "https://api.grizzlysms.com/stubs/handler_api.php"

DEFAULT_SERVICE  = "wa"
DEFAULT_COUNTRY  = "57"
DEFAULT_SVC_NAME = "WhatsApp"
DEFAULT_CTR_NAME = "🇲🇽 Mexico"

SMS_POLL_INTERVAL = 5    # detik antar cek OTP
SMS_MAX_WAIT      = 300  # timeout 5 menit

# Items per page untuk pagination
ITEMS_PER_PAGE = 5

# Storage background polling {activation_id: {chat_id, api_key, phone, ...}}
AUTO_POLL_JOBS: dict = {}

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# LOADING BAR PROFESIONAL
# ═══════════════════════════════════════════════════════════════════════════

class LoadingBar:
    """Loading bar profesional dengan animasi progress."""
    
    # Unicode block characters untuk progress bar
    BLOCKS = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
    
    @staticmethod
    def render(progress: float, width: int = 20) -> str:
        """
        Render progress bar.
        progress: 0.0 - 1.0
        width: jumlah block
        """
        if progress < 0: progress = 0
        if progress > 1: progress = 1
        
        filled = progress * width
        full_blocks = int(filled)
        partial = filled - full_blocks
        
        # Full blocks
        bar = "█" * full_blocks
        
        # Partial block
        if full_blocks < width:
            partial_idx = int(partial * len(LoadingBar.BLOCKS))
            if partial_idx >= len(LoadingBar.BLOCKS):
                partial_idx = len(LoadingBar.BLOCKS) - 1
            bar += LoadingBar.BLOCKS[partial_idx]
        
        # Empty blocks
        bar += "░" * (width - full_blocks - (1 if full_blocks < width else 0))
        
        percentage = int(progress * 100)
        return f"[{bar}] {percentage}%"
    
    @staticmethod
    def spinner(frame: int) -> str:
        """Spinner animation frame."""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        return frames[frame % len(frames)]

async def show_loading(
    ctx: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    text: str,
    progress: float,
    prefix: str = "⏳"
):
    """Update pesan dengan loading bar."""
    bar = LoadingBar.render(progress)
    spinner = LoadingBar.spinner(int(time.time() * 10) % 10)
    full_text = f"{prefix} {text}\n\n`{bar}` {spinner}"
    try:
        await ctx.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=full_text,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass  # Skip jika tidak ada perubahan

async def loading_animation(
    ctx: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    text: str,
    duration: float = 3.0,
    steps: int = 20
):
    """Animasi loading bar dari 0% sampai 100%."""
    interval = duration / steps
    for i in range(steps + 1):
        progress = i / steps
        await show_loading(ctx, chat_id, message_id, text, progress)
        if i < steps:
            await asyncio.sleep(interval)

# ═══════════════════════════════════════════════════════════════════════════
# USER APPROVAL SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def is_approved(user_id: int) -> bool:
    """Cek apakah user sudah di-approve."""
    return user_id in APPROVED_USERS

def is_admin(user_id: int) -> bool:
    """Cek apakah user adalah admin."""
    return user_id in ADMIN_IDS

def is_pending(user_id: int) -> bool:
    """Cek apakah user sedang pending approval."""
    return user_id in PENDING_USERS

async def request_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle user baru yang belum di-approve."""
    user = update.effective_user
    
    # Cek apakah sudah pending
    if is_pending(user.id):
        await update.message.reply_text(
            "⏳ *Permintaan Akses Pending*\n\n"
            f"Akun kamu sedang menunggu persetujuan admin.\n"
            f"ID: `{user.id}`\n\n"
            "Harap tunggu, admin akan segera memproses.",
            parse_mode=ParseMode.MARKDOWN
        )
        return False
    
    # Tambah ke pending list
    PENDING_USERS[user.id] = {
        "name": user.first_name,
        "username": user.username or "-",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chat_id": update.effective_chat.id
    }
    
    # Notify user
    await update.message.reply_text(
        "🔒 *Akses Diperlukan*\n\n"
        f"Hai {user.first_name}!\n"
        f"ID Telegram: `{user.id}`\n\n"
        "Permintaan akses telah dikirim ke admin.\n"
        "Kamu akan dinotifikasi setelah disetujui.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Notify all admins dengan inline buttons
    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
                ],
                [InlineKeyboardButton("📋 Info User", callback_data=f"info_{user.id}")]
            ])
            
            await ctx.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 *PERMINTAAN AKSES BARU*\n\n"
                    f"👤 Nama: {user.first_name}\n"
                    f"🆔 ID: `{user.id}`\n"
                    f"👥 Username: @{user.username or '-'}\n"
                    f"⏰ Waktu: {PENDING_USERS[user.id]['time']}\n\n"
                    f"Total Pending: {len(PENDING_USERS)}"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Gagal kirim notif ke admin {admin_id}: {e}")
    
    return False

async def handle_approval_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle callback dari tombol approve/reject."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    admin_id = query.from_user.id
    
    # Hanya admin yang bisa approve/reject
    if not is_admin(admin_id):
        await query.edit_message_text(
            "⛔ Hanya admin yang dapat melakukan aksi ini.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        
        if user_id in PENDING_USERS:
            user_info = PENDING_USERS.pop(user_id)
            APPROVED_USERS.add(user_id)
            
            # Notify user
            try:
                await ctx.bot.send_message(
                    chat_id=user_info["chat_id"],
                    text=(
                        "🎉 *AKSES DISETUJUI!*\n\n"
                        "Selamat! Kamu sekarang dapat menggunakan bot.\n"
                        "Ketik /start untuk memulai."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Gagal notif user {user_id}: {e}")
            
            # Update admin message
            await query.edit_message_text(
                f"✅ *USER DISETUJUI*\n\n"
                f"👤 {user_info['name']}\n"
                f"🆔 `{user_id}`\n"
                f"👨‍💼 Disetujui oleh: {query.from_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"User {user_id} approved by {admin_id}")
    
    elif data.startswith("reject_"):
        user_id = int(data.split("_")[1])
        
        if user_id in PENDING_USERS:
            user_info = PENDING_USERS.pop(user_id)
            
            # Notify user
            try:
                await ctx.bot.send_message(
                    chat_id=user_info["chat_id"],
                    text=(
                        "❌ *AKSES DITOLAK*\n\n"
                        "Maaf, permintaan akses kamu ditolak.\n"
                        "Hubungi admin untuk informasi lebih lanjut."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Gagal notif user {user_id}: {e}")
            
            # Update admin message
            await query.edit_message_text(
                f"❌ *USER DITOLAK*\n\n"
                f"👤 {user_info['name']}\n"
                f"🆔 `{user_id}`\n"
                f"👨‍💼 Ditolak oleh: {query.from_user.first_name}",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"User {user_id} rejected by {admin_id}")
    
    elif data.startswith("info_"):
        user_id = int(data.split("_")[1])
        if user_id in PENDING_USERS:
            user_info = PENDING_USERS[user_id]
            await query.answer(
                f"Info: {user_info['name']} (@{user_info['username']}) - {user_info['time']}",
                show_alert=True
            )

async def check_access(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Cek akses user, request approval jika belum."""
    user = update.effective_user
    
    if is_approved(user.id):
        return True
    
    if is_admin(user.id):
        APPROVED_USERS.add(user.id)
        return True
    
    # User belum di-approve, request approval
    await request_approval(update, ctx)
    return False

# ═══════════════════════════════════════════════════════════════════════════
# PAGINATION PROFESIONAL
# ═══════════════════════════════════════════════════════════════════════════

class Paginator:
    """Paginator profesional untuk daftar item."""
    
    @staticmethod
    def paginate(items: list, page: int = 1, per_page: int = ITEMS_PER_PAGE) -> dict:
        """
        Return pagination info.
        Returns: {
            "items": list,      # items di halaman ini
            "page": int,        # halaman saat ini
            "total_pages": int, # total halaman
            "total_items": int, # total items
            "has_prev": bool,   # ada halaman sebelumnya
            "has_next": bool,   # ada halaman selanjutnya
        }
        """
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
        }
    
    @staticmethod
    def get_keyboard(
        callback_prefix: str,
        page: int,
        total_pages: int,
        extra_buttons: list = None
    ) -> InlineKeyboardMarkup:
        """Generate pagination keyboard."""
        buttons = []
        
        # Navigation row
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"{callback_prefix}_{page-1}")
            )
        
        nav_buttons.append(
            InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="page_info")
        )
        
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"{callback_prefix}_{page+1}")
            )
        
        buttons.append(nav_buttons)
        
        # Page number buttons (max 5)
        if total_pages > 1:
            page_buttons = []
            start_page = max(1, page - 2)
            end_page = min(total_pages, start_page + 4)
            
            for p in range(start_page, end_page + 1):
                label = f"[{p}]" if p == page else str(p)
                page_buttons.append(
                    InlineKeyboardButton(label, callback_data=f"{callback_prefix}_{p}")
                )
            
            buttons.append(page_buttons)
        
        # Extra buttons
        if extra_buttons:
            buttons.extend(extra_buttons)
        
        return InlineKeyboardMarkup(buttons)

async def handle_pagination_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle callback pagination."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "page_info":
        await query.answer("Info Halaman", show_alert=False)
        return
    
    # Parse callback data
    # Format: prefix_page (e.g., "numbers_2", "logs_3", "pending_1")
    parts = data.rsplit("_", 1)
    if len(parts) != 2:
        return
    
    prefix = parts[0]
    try:
        page = int(parts[1])
    except ValueError:
        return
    
    # Handle different pagination types
    if prefix == "numbers":
        await show_numbers_page(update, ctx, page)
    elif prefix == "logs":
        await show_logs_page(update, ctx, page)
    elif prefix == "pending":
        await show_pending_page(update, ctx, page)

async def show_numbers_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Tampilkan halaman daftar nomor."""
    query = update.callback_query
    
    actives = ctx.user_data.get("active_numbers", [])
    paginated = Paginator.paginate(actives, page)
    
    if not actives:
        await query.edit_message_text(
            "📋 *DAFTAR NOMOR AKTIF*\n\n"
            "Tidak ada nomor aktif.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Build message
    lines = [
        f"📋 *DAFTAR NOMOR AKTIF*\n",
        f"📊 Total: {paginated['total_items']} nomor | Hal {paginated['page']}/{paginated['total_pages']}\n",
        "─" * 20
    ]
    
    for i, n in enumerate(paginated["items"], start=(page-1)*ITEMS_PER_PAGE + 1):
        lines.append(
            f"\n*{i}.* 📞 `+{n['phone']}`\n"
            f"   🆔 `{n['id']}`\n"
            f"   📦 {n['service']} | {n['country']}\n"
            f"   🕐 {n['time']}"
        )
    
    keyboard = Paginator.get_keyboard("numbers", page, paginated["total_pages"])
    
    try:
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception:
        pass

async def show_logs_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Tampilkan halaman log."""
    query = update.callback_query
    
    logs = ctx.user_data.get("log", [])
    paginated = Paginator.paginate(logs, page, per_page=10)
    
    if not logs:
        await query.edit_message_text(
            "📋 *LOG AKTIVITAS*\n\n"
            "Log masih kosong.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    lines = [
        f"📋 *LOG AKTIVITAS*\n",
        f"📊 Total: {paginated['total_items']} entry | Hal {paginated['page']}/{paginated['total_pages']}\n",
        "─" * 20
    ]
    
    for log in paginated["items"]:
        lines.append(f"\n`{log}`")
    
    keyboard = Paginator.get_keyboard("logs", page, paginated["total_pages"])
    
    try:
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception:
        pass

async def show_pending_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Tampilkan halaman user pending (admin only)."""
    query = update.callback_query
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Admin only!", show_alert=True)
        return
    
    pending_list = [
        {"id": uid, **info} for uid, info in PENDING_USERS.items()
    ]
    paginated = Paginator.paginate(pending_list, page)
    
    if not pending_list:
        await query.edit_message_text(
            "📋 *USER PENDING*\n\n"
            "Tidak ada user yang menunggu approval.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    lines = [
        f"📋 *USER PENDING APPROVAL*\n",
        f"📊 Total: {paginated['total_items']} user | Hal {paginated['page']}/{paginated['total_pages']}\n",
        "─" * 20
    ]
    
    for i, user in enumerate(paginated["items"], start=(page-1)*ITEMS_PER_PAGE + 1):
        lines.append(
            f"\n*{i}.* 👤 {user['name']}\n"
            f"   🆔 `{user['id']}`\n"
            f"   👥 @{user['username']}\n"
            f"   ⏰ {user['time']}"
        )
    
    keyboard = Paginator.get_keyboard("pending", page, paginated["total_pages"])
    
    try:
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# PRICE RANGE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def handle_pricerange_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle callback untuk range harga."""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Admin only!", show_alert=True)
        return
    
    data = query.data
    
    if data == "pricerange_info":
        await query.answer(
            f"Range: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
            show_alert=True
        )
    
    elif data.startswith("pricerange_set_"):
        action = data.split("_")[2]
        
        if action == "min":
            ctx.user_data["waiting_for"] = "set_price_min"
            await query.edit_message_text(
                f"💰 *SET MINIMUM PRICE*\n\n"
                f"Current: *${PRICE_RANGE['min']:.2f}*\n\n"
                f"Masukkan harga minimum baru (dalam USD):\n"
                f"Contoh: `0.05`",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif action == "max":
            ctx.user_data["waiting_for"] = "set_price_max"
            await query.edit_message_text(
                f"💰 *SET MAXIMUM PRICE*\n\n"
                f"Current: *${PRICE_RANGE['max']:.2f}*\n\n"
                f"Masukkan harga maximum baru (dalam USD):\n"
                f"Contoh: `0.30`",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif action == "reset":
            PRICE_RANGE["min"] = 0.01
            PRICE_RANGE["max"] = 0.50
            await query.edit_message_text(
                f"✅ *PRICE RANGE RESET*\n\n"
                f"Min: ${PRICE_RANGE['min']:.2f}\n"
                f"Max: ${PRICE_RANGE['max']:.2f}",
                parse_mode=ParseMode.MARKDOWN
            )

def get_pricerange_keyboard() -> InlineKeyboardMarkup:
    """Keyboard untuk set price range."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📉 Min: ${PRICE_RANGE['min']:.2f}", callback_data="pricerange_set_min"),
            InlineKeyboardButton(f"📈 Max: ${PRICE_RANGE['max']:.2f}", callback_data="pricerange_set_max"),
        ],
        [
            InlineKeyboardButton("🔄 Reset Default", callback_data="pricerange_set_reset"),
        ]
    ])

def is_price_in_range(price: float) -> bool:
    """Cek apakah harga dalam range yang diizinkan."""
    return PRICE_RANGE["min"] <= price <= PRICE_RANGE["max"]

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_api_key(ctx) -> str | None:
    return ctx.user_data.get("api_key")

def add_log(ctx, msg: str):
    ctx.user_data.setdefault("log", [])
    ts = datetime.now().strftime("%H:%M:%S")
    ctx.user_data["log"].append(f"[{ts}] {msg}")
    ctx.user_data["log"] = ctx.user_data["log"][-100:]  # Simpan 100 log terakhir

def ensure_init(ctx):
    d = ctx.user_data
    d.setdefault("api_key",        None)
    d.setdefault("active_numbers", [])
    d.setdefault("log",            [])
    d.setdefault("service",        DEFAULT_SERVICE)
    d.setdefault("country",        DEFAULT_COUNTRY)
    d.setdefault("svc_name",       DEFAULT_SVC_NAME)
    d.setdefault("ctr_name",       DEFAULT_CTR_NAME)
    d.setdefault("price",          "?")

def fmt_numbers(actives: list) -> str:
    if not actives:
        return "_Belum ada nomor aktif._"
    lines = []
    for i, n in enumerate(actives, 1):
        lines.append(
            f"{i}. 📞 `+{n['phone']}`\n"
            f"   🆔 `{n['id']}` | {n['service']} | {n['country']}\n"
            f"   🕐 {n['time']}"
        )
    return "\n\n".join(lines)

def error_map(raw: str) -> str:
    MAP = {
        "NO_NUMBERS":                  "❌ Nomor habis. Coba layanan/negara lain.",
        "NO_BALANCE":                  "❌ Saldo tidak cukup. Top up di grizzlysms.com",
        "BAD_KEY":                     "❌ API Key tidak valid.",
        "BAD_SERVICE":                 "❌ Kode layanan tidak valid.",
        "BAD_COUNTRY":                 "❌ Kode negara tidak valid.",
        "SERVER_ERROR":                "❌ Server error. Coba lagi.",
        "TOO_MANY_ACTIVE_ACTIVATIONS": "❌ Terlalu banyak aktivasi. Batalkan dulu.",
        "FORMAT_ERROR":                "❌ Format response tidak dikenal.",
        "PRICE_OUT_OF_RANGE":          f"❌ Harga di luar range (${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}).",
    }
    return MAP.get(raw, f"❌ Error: `{raw}`")

# ═══════════════════════════════════════════════════════════════════════════
# API CALL
# ═══════════════════════════════════════════════════════════════════════════

def api_call(api_key: str, action: str, extra: dict = None) -> str:
    """
    API call dengan URL encoding manual.
    """
    params = {"api_key": api_key.strip(), "action": action}
    if extra:
        params.update(extra)

    query = urllib.parse.urlencode(params)

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    for base_url in [API_BASE, API_BASE2]:
        url = f"{base_url}?{query}"
        try:
            r = requests.get(url, timeout=12, verify=False, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            })
            result = r.text.strip()

            if result.startswith("<") or result.startswith("<!"):
                logger.warning(f"HTML response dari {base_url}, skip")
                continue

            logger.info(f"[{action}] {base_url.split('/')[2]} → {result[:100]}")
            return result

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout dari {base_url}")
            continue
        except Exception as e:
            logger.error(f"Request error {base_url}: {e}")
            continue

    return "SERVER_ERROR"

# ═══════════════════════════════════════════════════════════════════════════
# API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def api_get_balance(api_key: str) -> float | None:
    resp = api_call(api_key, "getBalance")
    if resp.startswith("ACCESS_BALANCE:"):
        try:
            return float(resp.split(":")[1])
        except:
            return 0.0
    logger.warning(f"getBalance gagal: {resp}")
    return None

def api_buy_number(api_key: str, service: str, country: str) -> dict:
    # Cek harga dulu
    price_info = api_get_price(api_key, service, country)
    try:
        cost = float(price_info.get("cost", 999))
    except (ValueError, TypeError):
        cost = 999.0

    # Cek apakah harga dalam range
    if not is_price_in_range(cost):
        logger.warning(f"Harga ${cost} di luar range ${PRICE_RANGE['min']:.2f}-${PRICE_RANGE['max']:.2f}")
        return {"status": "error", "msg": "PRICE_OUT_OF_RANGE", "cost": cost}

    # Beli nomor
    resp = api_call(api_key, "getNumber", {"service": service, "country": country})

    if resp.startswith("ACCESS_NUMBER:"):
        parts = resp.split(":", 2)
        if len(parts) == 3:
            act_id = parts[1].strip()
            phone  = parts[2].strip()
            logger.info(f"Beli OK id={act_id} phone={phone} harga=${cost}")
            return {"status": "ok", "id": act_id, "phone": phone, "cost": cost}
        logger.error(f"Format tidak dikenal: {resp}")
        return {"status": "error", "msg": "FORMAT_ERROR"}

    logger.warning(f"Beli gagal: {resp}")
    return {"status": "error", "msg": resp.split(":")[0] if ":" in resp else resp}

def api_get_sms(api_key: str, activation_id: str) -> dict:
    resp = api_call(api_key, "getStatus", {"id": activation_id})
    if resp.startswith("STATUS_OK:"):
        return {"status": "ok", "code": resp.split(":", 1)[1]}
    elif resp in ("STATUS_WAIT_CODE", "STATUS_WAIT_RETRY", "STATUS_WAIT_RESEND"):
        return {"status": "waiting"}
    elif resp == "STATUS_CANCEL":
        return {"status": "cancelled"}
    return {"status": "error", "msg": resp}

def api_cancel(api_key: str, activation_id: str) -> bool:
    resp = api_call(api_key, "setStatus", {"id": activation_id, "status": "8"})
    return any(x in resp for x in ["ACCESS_CANCEL", "ACCESS_ACTIVATION", "1"])

def api_confirm(api_key: str, activation_id: str) -> bool:
    resp = api_call(api_key, "setStatus", {"id": activation_id, "status": "6"})
    return any(x in resp for x in ["ACCESS_ACTIVATION", "1"])

def api_get_price(api_key: str, service: str, country: str) -> dict:
    resp = api_call(api_key, "getPrices", {"service": service, "country": country})
    try:
        data = json.loads(resp)
        p = data.get(str(country), {}).get(str(service), {})
        return {"cost": p.get("cost", "?"), "count": p.get("count", 0)}
    except:
        return {"cost": "?", "count": 0}

# ═══════════════════════════════════════════════════════════════════════════
# KEYBOARD
# ═══════════════════════════════════════════════════════════════════════════

def main_keyboard(ctx, is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    svc   = ctx.user_data.get("svc_name", DEFAULT_SVC_NAME)
    price = ctx.user_data.get("price", "?")
    
    # Keyboard dasar untuk user
    buttons = [
        [KeyboardButton("💰 Cek Saldo"),        KeyboardButton("📲 Beli 1 Nomor")],
        [KeyboardButton("🔟 Beli 5 Nomor"),     KeyboardButton("🔢 Beli 3 Nomor")],
        [KeyboardButton(f"📦 Layanan: {svc[:8]}..."), KeyboardButton(f"💲 Harga: ${price}")],
        [KeyboardButton("🔑 Ganti API Key")],
        [KeyboardButton("❌ Batalkan Nomor..."), KeyboardButton("🗑 Batalkan Semua")],
        [KeyboardButton("📋 Lihat Log"),        KeyboardButton("📞 Daftar Nomor")],
    ]
    
    # Tombol admin
    if is_admin_user:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def setup_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔑 Masukkan API Key")],
        [KeyboardButton("❓ Cara Dapat API Key")],
    ], resize_keyboard=True)

def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("👥 User Pending"),     KeyboardButton("📊 Statistik")],
        [KeyboardButton("💰 Set Range Harga"),  KeyboardButton("📋 Semua Log")],
        [KeyboardButton("🔙 Kembali ke Menu")],
    ], resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════════════
# AUTO POLL (OTP MASUK OTOMATIS)
# ═══════════════════════════════════════════════════════════════════════════

async def auto_poll_worker(app: Application, activation_id: str):
    """Background task — cek OTP tiap interval, kirim notif otomatis."""
    job = AUTO_POLL_JOBS.get(activation_id)
    if not job:
        return

    chat_id  = job["chat_id"]
    api_key  = job["api_key"]
    phone    = job["phone"]
    service  = job["service"]
    country  = job["country"]
    start_t  = job["start_time"]

    logger.info(f"Auto-poll mulai: id={activation_id} phone={phone}")

    while activation_id in AUTO_POLL_JOBS:
        elapsed = time.time() - start_t

        # Timeout
        if elapsed > SMS_MAX_WAIT:
            AUTO_POLL_JOBS.pop(activation_id, None)
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"⏰ *Timeout OTP*\n\n"
                        f"📞 `+{phone}`\n"
                        f"🆔 `{activation_id}`\n"
                        f"SMS tidak masuk dalam {SMS_MAX_WAIT//60} menit.\n\n"
                        f"Gunakan `/cancel {activation_id}` untuk batalkan."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Gagal kirim timeout notif: {e}")
            return

        result = api_get_sms(api_key, activation_id)

        if result["status"] == "ok":
            code = result["code"]
            AUTO_POLL_JOBS.pop(activation_id, None)
            logger.info(f"OTP diterima: id={activation_id} code={code}")
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔔 *OTP MASUK!*\n\n"
                        f"📞 Nomor : `+{phone}`\n"
                        f"🔑 *Kode OTP : `{code}`*\n"
                        f"📦 Layanan : {service}\n"
                        f"🌍 Negara  : {country}\n"
                        f"⏱️ Waktu   : {int(elapsed)}s\n\n"
                        f"✅ Setelah verifikasi berhasil:\n"
                        f"`/konfirmasi {activation_id}`"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Gagal kirim OTP notif: {e}")
            return

        elif result["status"] == "cancelled":
            AUTO_POLL_JOBS.pop(activation_id, None)
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Aktivasi `{activation_id}` dibatalkan.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            return

        elif result["status"] == "error":
            AUTO_POLL_JOBS.pop(activation_id, None)
            logger.warning(f"Auto-poll error: id={activation_id} msg={result.get('msg')}")
            return

        await asyncio.sleep(SMS_POLL_INTERVAL)

def start_poll(app: Application, activation_id: str, chat_id: int,
               api_key: str, phone: str, service: str, country: str):
    """Daftarkan job dan mulai background task."""
    AUTO_POLL_JOBS[activation_id] = {
        "chat_id":    chat_id,
        "api_key":    api_key,
        "phone":      phone,
        "service":    service,
        "country":    country,
        "start_time": time.time(),
    }
    asyncio.create_task(auto_poll_worker(app, activation_id))
    logger.info(f"Poll job registered: {activation_id}")

# ═══════════════════════════════════════════════════════════════════════════
# BUY FLOW DENGAN LOADING BAR
# ═══════════════════════════════════════════════════════════════════════════

async def do_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE, qty: int):
    ensure_init(ctx)
    api_key = get_api_key(ctx)
    if not api_key:
        await prompt_api_key(update, ctx)
        return

    service  = ctx.user_data["service"]
    country  = ctx.user_data["country"]
    svc_name = ctx.user_data["svc_name"]
    ctr_name = ctx.user_data["ctr_name"]

    # Kirim pesan dengan loading bar
    msg = await update.message.reply_text(
        f"⏳ *MEMBELI {qty}x NOMOR*\n\n"
        f"`{LoadingBar.render(0)}`",
        parse_mode=ParseMode.MARKDOWN
    )

    results = []
    for i in range(qty):
        # Update loading bar
        progress = (i / qty) * 0.8  # 0-80% untuk proses pembelian
        await show_loading(ctx, update.effective_chat.id, msg.message_id, 
                          f"MEMBELI {qty}x NOMOR", progress, "📲")
        
        result = api_buy_number(api_key, service, country)

        if result["status"] == "ok":
            entry = {
                "id":      result["id"],
                "phone":   result["phone"],
                "service": svc_name,
                "country": ctr_name,
                "time":    datetime.now().strftime("%H:%M:%S"),
                "cost":    result.get("cost", "?"),
            }
            ctx.user_data["active_numbers"].append(entry)
            results.append(entry)
            add_log(ctx, f"BELI OK | {result['id']} | +{result['phone']} | ${result.get('cost', '?')}")

            # Mulai auto-poll OTP
            start_poll(
                app=ctx.application,
                activation_id=result["id"],
                chat_id=update.effective_chat.id,
                api_key=api_key,
                phone=result["phone"],
                service=svc_name,
                country=ctr_name,
            )

            if qty > 1:
                await asyncio.sleep(1.2)
        else:
            err = result.get("msg", "UNKNOWN")
            add_log(ctx, f"BELI GAGAL | {err}")
            if qty == 1:
                # Complete loading bar
                await show_loading(ctx, update.effective_chat.id, msg.message_id,
                                  "PROSES SELESAI", 1.0, "❌")
                if err == "PRICE_OUT_OF_RANGE":
                    cost = result.get("cost", "?")
                    txt = (
                        f"❌ *HARGA DI LUAR RANGE!*\n\n"
                        f"Harga saat ini: *${cost}*\n"
                        f"Range yang diizinkan: *${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}*\n\n"
                        f"Gunakan /setrange untuk mengubah range harga."
                    )
                    await msg.edit_text(txt, parse_mode=ParseMode.MARKDOWN)
                else:
                    await msg.edit_text(error_map(err), parse_mode=ParseMode.MARKDOWN)
                return
            results.append({"error": err})

    # Complete loading bar
    await show_loading(ctx, update.effective_chat.id, msg.message_id,
                      "PROSES SELESAI", 1.0, "✅")

    # Tampilkan hasil
    if qty == 1 and results and "error" not in results[0]:
        n = results[0]
        text = (
            f"✅ *NOMOR BERHASIL DIBELI!*\n\n"
            f"📞 *Nomor:* `+{n['phone']}`\n"
            f"🆔 *ID:* `{n['id']}`\n"
            f"💰 *Harga:* ${n.get('cost', '?')}\n"
            f"📦 {n['service']} | {n['country']}\n"
            f"🕐 {n['time']}\n\n"
            f"🔔 *OTP akan dikirim otomatis ke sini!*\n"
            f"Masukkan nomor ke layanan tujuan sekarang 👆"
        )
    else:
        lines = [f"📊 *HASIL BELI {qty} NOMOR*\n"]
        for i, n in enumerate(results, 1):
            if "error" in n:
                lines.append(f"{i}. {error_map(n['error'])}")
            else:
                lines.append(
                    f"{i}. ✅ `+{n['phone']}`\n"
                    f"   🆔 `{n['id']}` 💰 ${n.get('cost', '?')}"
                )
        ok = sum(1 for n in results if "error" not in n)
        lines.append(f"\n✅ *Berhasil: {ok}/{qty}*")
        if ok > 0:
            lines.append("🔔 OTP akan dikirim otomatis!")
        text = "\n".join(lines)

    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════════════════
# PROMPT API KEY
# ═══════════════════════════════════════════════════════════════════════════

async def prompt_api_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["waiting_for"] = "api_key_setup"
    await update.message.reply_text(
        "🔑 *MASUKKAN API KEY GRIZZLYSMS*\n\n"
        "1. Login di grizzlysms.com\n"
        "2. Profil → *Settings*\n"
        "3. Copy *API Key*\n\n"
        "Paste di sini 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )

# ═══════════════════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    user    = update.effective_user
    api_key = get_api_key(ctx)

    if not api_key:
        await update.message.reply_text(
            f"🐻 *SELAMAT DATANG, {user.first_name}!*\n\n"
            f"🆔 ID Telegram: `{user.id}`\n\n"
            "Masukkan *API Key GrizzlySMS* kamu untuk mulai.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=setup_keyboard()
        )
    else:
        bal = api_get_balance(api_key)
        bal_text = f"${bal:.4f}" if bal is not None else "Gagal cek"
        await update.message.reply_text(
            f"🐻 *GrizzlySMS Bot v5 - Enhanced*\n\n"
            f"👤 {user.first_name} | 🆔 `{user.id}`\n"
            f"💰 Saldo: *{bal_text}*\n"
            f"📦 {ctx.user_data['svc_name']} | {ctx.user_data['ctr_name']}\n"
            f"💵 Range: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(ctx, is_admin(user.id))
        )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    text    = (update.message.text or "").strip()
    api_key = get_api_key(ctx)
    user_id = update.effective_user.id

    # ── Setup keyboard (belum ada API key)
    if text == "🔑 Masukkan API Key":
        await prompt_api_key(update, ctx); return

    if text == "❓ Cara Dapat API Key":
        await update.message.reply_text(
            "📖 *CARA DAPAT API KEY*\n\n"
            "1. Buka grizzlysms.com\n"
            "2. Daftar & top up saldo\n"
            "3. Profil → Settings → Copy API Key\n"
            "4. Paste di bot ini",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=setup_keyboard()
        ); return

    # ── Waiting states
    waiting = ctx.user_data.get("waiting_for")

    if waiting == "api_key_setup":
        ctx.user_data.pop("waiting_for")
        new_key = text.strip()
        if len(new_key) < 10:
            await update.message.reply_text("❌ API Key terlalu pendek. Coba lagi.")
            ctx.user_data["waiting_for"] = "api_key_setup"; return

        # Loading animation
        msg = await update.message.reply_text(
            f"⏳ Validasi API Key `{new_key[:6]}...`\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await loading_animation(ctx, update.effective_chat.id, msg.message_id, 
                               "Validasi API Key", duration=1.5)
        
        bal = api_get_balance(new_key)
        if bal is not None:
            ctx.user_data["api_key"] = new_key
            add_log(ctx, f"API KEY SETUP | saldo ${bal:.4f}")
            await msg.edit_text(
                f"✅ *API KEY DISIMPAN!*\n\n💰 Saldo: *${bal:.4f}*",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                "Pilih menu 👇",
                reply_markup=main_keyboard(ctx, is_admin(user_id))
            )
        else:
            await msg.edit_text(
                "❌ API Key tidak valid. Pastikan dari grizzlysms.com → Settings\n\nCoba lagi 👇",
                parse_mode=ParseMode.MARKDOWN
            )
            ctx.user_data["waiting_for"] = "api_key_setup"
        return

    if waiting == "api_key_change":
        ctx.user_data.pop("waiting_for")
        new_key = text.strip()
        msg = await update.message.reply_text(
            f"⏳ Validasi...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                               "Validasi", duration=1.0)
        bal = api_get_balance(new_key)
        if bal is not None:
            ctx.user_data["api_key"] = new_key
            add_log(ctx, f"API KEY GANTI | saldo ${bal:.4f}")
            await msg.edit_text(
                f"✅ *API Key diperbarui!*\n💰 Saldo: *${bal:.4f}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(ctx, is_admin(user_id))
            )
        else:
            await msg.edit_text("❌ Tidak valid. Coba lagi.")
            ctx.user_data["waiting_for"] = "api_key_change"
        return

    if waiting == "cancel_select":
        ctx.user_data.pop("waiting_for")
        actives = ctx.user_data.get("active_numbers", [])
        try:
            idx = int(text) - 1
            if 0 <= idx < len(actives):
                n = actives[idx]
                msg = await update.message.reply_text(
                    f"⏳ Membatalkan `+{n['phone']}`...\n\n`{LoadingBar.render(0)}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                                       "Membatalkan", duration=1.0)
                if api_cancel(api_key, n["id"]):
                    AUTO_POLL_JOBS.pop(n["id"], None)
                    ctx.user_data["active_numbers"].pop(idx)
                    add_log(ctx, f"CANCEL | {n['id']}")
                    await msg.edit_text(
                        f"✅ `+{n['phone']}` dibatalkan.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await msg.edit_text("❌ Gagal batalkan.")
            else:
                await update.message.reply_text("❌ Nomor urut tidak valid.")
        except:
            await update.message.reply_text("❌ Ketik angka urutan nomor.")
        return

    if waiting == "set_price_min":
        ctx.user_data.pop("waiting_for")
        try:
            new_min = float(text.replace("$", "").replace(",", "."))
            if new_min < 0:
                raise ValueError("Negative")
            if new_min > PRICE_RANGE["max"]:
                await update.message.reply_text(
                    f"❌ Min tidak boleh lebih dari Max (${PRICE_RANGE['max']:.2f})",
                    reply_markup=main_keyboard(ctx, is_admin(user_id))
                )
                return
            PRICE_RANGE["min"] = new_min
            add_log(ctx, f"PRICE RANGE MIN | ${new_min:.2f}")
            await update.message.reply_text(
                f"✅ *Minimum harga diubah!*\n\n"
                f"💵 Range: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(ctx, is_admin(user_id))
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Format salah. Masukkan angka (contoh: 0.05)",
                reply_markup=main_keyboard(ctx, is_admin(user_id))
            )
        return

    if waiting == "set_price_max":
        ctx.user_data.pop("waiting_for")
        try:
            new_max = float(text.replace("$", "").replace(",", "."))
            if new_max < 0:
                raise ValueError("Negative")
            if new_max < PRICE_RANGE["min"]:
                await update.message.reply_text(
                    f"❌ Max tidak boleh kurang dari Min (${PRICE_RANGE['min']:.2f})",
                    reply_markup=main_keyboard(ctx, is_admin(user_id))
                )
                return
            PRICE_RANGE["max"] = new_max
            add_log(ctx, f"PRICE RANGE MAX | ${new_max:.2f}")
            await update.message.reply_text(
                f"✅ *Maximum harga diubah!*\n\n"
                f"💵 Range: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(ctx, is_admin(user_id))
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Format salah. Masukkan angka (contoh: 0.50)",
                reply_markup=main_keyboard(ctx, is_admin(user_id))
            )
        return

    # ── Belum ada API key
    if not api_key:
        await update.message.reply_text(
            "⚠️ Belum ada API Key. Klik tombol 👇",
            reply_markup=setup_keyboard()
        )
        return

    # ── Menu utama
    if "Cek Saldo" in text:
        msg = await update.message.reply_text(
            f"⏳ Cek saldo...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                               "Cek Saldo", duration=1.0)
        bal = api_get_balance(api_key)
        if bal is not None:
            add_log(ctx, f"CEK SALDO ${bal:.4f}")
            await msg.edit_text(
                f"💰 *SALDO GRIZZLYSMS*\n\n*${bal:.4f}*\n\nTop up: grizzlysms.com",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await msg.edit_text("❌ Gagal cek saldo. Coba ganti API Key.")

    elif "Beli 1 Nomor" in text:
        await do_buy(update, ctx, 1)

    elif "Beli 3 Nomor" in text:
        await do_buy(update, ctx, 3)

    elif "Beli 5 Nomor" in text:
        await do_buy(update, ctx, 5)

    elif "Cek Harga" in text:
        msg = await update.message.reply_text(
            f"⏳ Ambil harga...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                               "Ambil Harga", duration=1.0)
        info = api_get_price(api_key, ctx.user_data["service"], ctx.user_data["country"])
        await msg.edit_text(
            f"💲 *HARGA SAAT INI*\n\n"
            f"📦 {ctx.user_data['svc_name']} | {ctx.user_data['ctr_name']}\n"
            f"💰 Harga    : *${info['cost']}*\n"
            f"📊 Tersedia : *{info['count']}* nomor\n"
            f"💵 Range Bot: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
            parse_mode=ParseMode.MARKDOWN
        )

    elif text.startswith("📦"):
        await update.message.reply_text(
            f"📦 *LAYANAN AKTIF*\n\n"
            f"Layanan : *{ctx.user_data['svc_name']}*\n"
            f"Negara  : *{ctx.user_data['ctr_name']}*\n\n"
            f"Ganti:\n`/setlayanan <kode_svc> <kode_negara> <nama_svc> <nama_negara>`\n\n"
            f"*Contoh:*\n"
            f"`/setlayanan wa 18 WhatsApp Vietnam`\n"
            f"`/setlayanan wa 6 WhatsApp Indonesia`\n"
            f"`/setlayanan tg 18 Telegram Vietnam`\n"
            f"`/setlayanan go 6 Google Indonesia`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif text.startswith("🌍"):
        await update.message.reply_text(
            f"🌍 *NEGARA AKTIF*: {ctx.user_data['ctr_name']}\n\n"
            f"Ganti negara dengan:\n"
            f"`/setlayanan <svc> <kode_negara> <nama_svc> <nama_negara>`\n\n"
            f"*Kode Negara Populer:*\n"
            f"`0`  = 🇺🇸 USA\n`6`  = 🇮🇩 Indonesia\n`18` = 🇻🇳 Vietnam\n"
            f"`22` = 🇬🇧 UK\n`32` = 🇮🇳 India\n`12` = 🇷🇺 Russia",
            parse_mode=ParseMode.MARKDOWN
        )

    elif "Ganti API Key" in text:
        ctx.user_data["waiting_for"] = "api_key_change"
        await update.message.reply_text(
            "🔑 Masukkan API Key baru:",
            reply_markup=ReplyKeyboardRemove()
        )

    elif text == "❌ Batalkan Nomor...":
        actives = ctx.user_data.get("active_numbers", [])
        if not actives:
            await update.message.reply_text("ℹ️ Tidak ada nomor aktif."); return
        
        # Gunakan pagination
        paginated = Paginator.paginate(actives, 1)
        lines = [
            f"📋 *PILIH NOMOR YANG DIBATALKAN*\n",
            f"📊 Total: {paginated['total_items']} nomor\n",
            "─" * 20
        ]
        for i, n in enumerate(paginated["items"], 1):
            lines.append(f"\n*{i}.* `+{n['phone']}`\n   🆔 `{n['id']}`")
        lines.append("\n\n_Balas dengan angka (contoh: `1`)_")
        
        ctx.user_data["waiting_for"] = "cancel_select"
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )

    elif "Batalkan Semua" in text:
        actives = ctx.user_data.get("active_numbers", [])
        if not actives:
            await update.message.reply_text("ℹ️ Tidak ada nomor aktif."); return
        
        msg = await update.message.reply_text(
            f"⏳ Membatalkan {len(actives)} nomor...\n\n`{LoadingBar.render(0)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        success = 0
        for i, n in enumerate(actives):
            progress = (i + 1) / len(actives)
            await show_loading(ctx, update.effective_chat.id, msg.message_id,
                              f"Membatalkan {len(actives)} nomor", progress)
            AUTO_POLL_JOBS.pop(n["id"], None)
            if api_cancel(api_key, n["id"]):
                success += 1
                add_log(ctx, f"CANCEL ALL | {n['id']}")
            await asyncio.sleep(0.3)
        
        ctx.user_data["active_numbers"] = []
        await msg.edit_text(
            f"✅ *DIBATALKAN: {success}/{len(actives)} NOMOR*",
            parse_mode=ParseMode.MARKDOWN
        )

    elif "Lihat Log" in text:
        logs = ctx.user_data.get("log", [])
        if not logs:
            await update.message.reply_text("📋 Log kosong.")
            return
        
        # Gunakan pagination
        paginated = Paginator.paginate(logs, 1, per_page=10)
        lines = [
            f"📋 *LOG AKTIVITAS*\n",
            f"📊 Total: {paginated['total_items']} entry | Hal {paginated['page']}/{paginated['total_pages']}\n",
            "─" * 20
        ]
        for log in paginated["items"]:
            lines.append(f"\n`{log}`")
        
        keyboard = Paginator.get_keyboard("logs", 1, paginated["total_pages"])
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    elif "Daftar Nomor" in text:
        actives = ctx.user_data.get("active_numbers", [])
        if not actives:
            await update.message.reply_text(
                "📋 *DAFTAR NOMOR AKTIF*\n\nTidak ada nomor aktif.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        paginated = Paginator.paginate(actives, 1)
        lines = [
            f"📋 *DAFTAR NOMOR AKTIF*\n",
            f"📊 Total: {paginated['total_items']} nomor | Hal {paginated['page']}/{paginated['total_pages']}\n",
            "─" * 20
        ]
        for i, n in enumerate(paginated["items"], 1):
            lines.append(
                f"\n*{i}.* 📞 `+{n['phone']}`\n"
                f"   🆔 `{n['id']}`\n"
                f"   📦 {n['service']} | {n['country']}\n"
                f"   🕐 {n['time']}"
            )
        
        keyboard = Paginator.get_keyboard("numbers", 1, paginated["total_pages"])
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    # ══ ADMIN MENU ══
    elif text == "⚙️ Admin Panel":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        await update.message.reply_text(
            "⚙️ *ADMIN PANEL*\n\n"
            f"👥 User Pending: {len(PENDING_USERS)}\n"
            f"✅ User Approved: {len(APPROVED_USERS)}\n"
            f"💵 Range Harga: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_keyboard()
        )

    elif text == "👥 User Pending":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        if not PENDING_USERS:
            await update.message.reply_text(
                "📋 *USER PENDING*\n\nTidak ada user yang menunggu approval.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        pending_list = [{"id": uid, **info} for uid, info in PENDING_USERS.items()]
        paginated = Paginator.paginate(pending_list, 1)
        
        lines = [
            f"📋 *USER PENDING APPROVAL*\n",
            f"📊 Total: {paginated['total_items']} user\n",
            "─" * 20
        ]
        for i, user in enumerate(paginated["items"], 1):
            lines.append(
                f"\n*{i}.* 👤 {user['name']}\n"
                f"   🆔 `{user['id']}`\n"
                f"   👥 @{user['username']}"
            )
        
        keyboard = Paginator.get_keyboard("pending", 1, paginated["total_pages"])
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    elif text == "📊 Statistik":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        await update.message.reply_text(
            f"📊 *STATISTIK BOT*\n\n"
            f"👥 User Pending: {len(PENDING_USERS)}\n"
            f"✅ User Approved: {len(APPROVED_USERS)}\n"
            f"👨‍💼 Admin: {len(ADMIN_IDS)}\n"
            f"📞 Active Poll Jobs: {len(AUTO_POLL_JOBS)}\n"
            f"💵 Range Harga: ${PRICE_RANGE['min']:.2f} - ${PRICE_RANGE['max']:.2f}",
            parse_mode=ParseMode.MARKDOWN
        )

    elif text == "💰 Set Range Harga":
        if not is_admin(user_id):
            await update.message.reply_text("⛔ Admin only!")
            return
        await update.message.reply_text(
            f"💰 *SET RANGE HARGA*\n\n"
            f"Range saat ini:\n"
            f"📉 Minimum: ${PRICE_RANGE['min']:.2f}\n"
            f"📈 Maximum: ${PRICE_RANGE['max']:.2f}\n\n"
            f"Bot hanya akan membeli nomor dalam range ini.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_pricerange_keyboard()
        )

    elif text == "🔙 Kembali ke Menu":
        await update.message.reply_text(
            "🏠 Menu Utama",
            reply_markup=main_keyboard(ctx, is_admin(user_id))
        )

    else:
        await update.message.reply_text(
            "❓ Gunakan menu di bawah.",
            reply_markup=main_keyboard(ctx, is_admin(user_id))
        )

# ═══════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

async def myid_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    status = "✅ Approved" if is_approved(u.id) else ("👨‍💼 Admin" if is_admin(u.id) else "⏳ Pending")
    await update.message.reply_text(
        f"🆔 *TELEGRAM ID KAMU*\n\n"
        f"ID: `{u.id}`\n"
        f"Nama: {u.first_name}\n"
        f"Username: @{u.username or '-'}\n"
        f"Status: {status}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cancel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    api_key = get_api_key(ctx)
    if not api_key:
        await prompt_api_key(update, ctx); return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/cancel <ID>`",
            parse_mode=ParseMode.MARKDOWN
        ); return
    act_id = args[0].strip()
    msg = await update.message.reply_text(
        f"⏳ Membatalkan `{act_id}`...\n\n`{LoadingBar.render(0)}`",
        parse_mode=ParseMode.MARKDOWN
    )
    await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                           "Membatalkan", duration=1.0)
    AUTO_POLL_JOBS.pop(act_id, None)
    if api_cancel(api_key, act_id):
        ctx.user_data["active_numbers"] = [
            n for n in ctx.user_data.get("active_numbers", []) if n["id"] != act_id
        ]
        add_log(ctx, f"CANCEL CMD | {act_id}")
        await msg.edit_text(
            f"✅ `{act_id}` dibatalkan.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await msg.edit_text(
            f"❌ Gagal batalkan `{act_id}`.",
            parse_mode=ParseMode.MARKDOWN
        )

async def konfirmasi_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    api_key = get_api_key(ctx)
    if not api_key:
        await prompt_api_key(update, ctx); return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/konfirmasi <ID>`",
            parse_mode=ParseMode.MARKDOWN
        ); return
    act_id = args[0].strip()
    msg = await update.message.reply_text(
        f"⏳ Konfirmasi `{act_id}`...\n\n`{LoadingBar.render(0)}`",
        parse_mode=ParseMode.MARKDOWN
    )
    await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                           "Konfirmasi", duration=1.0)
    if api_confirm(api_key, act_id):
        ctx.user_data["active_numbers"] = [
            n for n in ctx.user_data.get("active_numbers", []) if n["id"] != act_id
        ]
        add_log(ctx, f"KONFIRMASI | {act_id}")
        await msg.edit_text(
            f"✅ `{act_id}` dikonfirmasi!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await msg.edit_text(
            f"❌ Gagal konfirmasi `{act_id}`.",
            parse_mode=ParseMode.MARKDOWN
        )

async def setlayanan_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    api_key = get_api_key(ctx)
    if not api_key:
        await prompt_api_key(update, ctx); return
    args = ctx.args
    if len(args) < 4:
        await update.message.reply_text(
            "❌ Format:\n`/setlayanan <kode_svc> <kode_negara> <nama_svc> <nama_negara>`\n\n"
            "*Contoh:*\n"
            "`/setlayanan wa 18 WhatsApp Vietnam`\n"
            "`/setlayanan wa 6 WhatsApp Indonesia`\n"
            "`/setlayanan tg 18 Telegram Vietnam`\n"
            "`/setlayanan go 6 Google Indonesia`\n\n"
            "*Kode layanan:* `wa` `tg` `go` `fb` `ig` `tt`\n"
            "*Kode negara:* `0`=USA `6`=ID `18`=VN `22`=UK",
            parse_mode=ParseMode.MARKDOWN
        ); return

    svc_code, ctr_code = args[0], args[1]
    svc_name, ctr_name = args[2], args[3]
    
    msg = await update.message.reply_text(
        f"⏳ Cek harga...\n\n`{LoadingBar.render(0)}`",
        parse_mode=ParseMode.MARKDOWN
    )
    await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                           "Cek Harga", duration=1.0)
    
    info = api_get_price(api_key, svc_code, ctr_code)
    ctx.user_data.update({
        "service": svc_code,
        "country": ctr_code,
        "svc_name": svc_name,
        "ctr_name": ctr_name,
        "price": info["cost"]
    })
    add_log(ctx, f"SET LAYANAN | {svc_name} {ctr_name} ${info['cost']}")
    
    # Cek apakah harga dalam range
    try:
        cost = float(info["cost"])
        in_range = is_price_in_range(cost)
        range_status = "✅ Dalam range" if in_range else "⚠️ Di luar range"
    except:
        cost = info["cost"]
        range_status = "❓ Tidak dapat cek"
    
    await msg.edit_text(
        f"✅ *LAYANAN DIPERBARUI!*\n\n"
        f"📦 {svc_name} | {ctr_name}\n"
        f"💰 Harga: *${info['cost']}* | Tersedia: {info['count']}\n"
        f"📊 Status: {range_status}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(ctx, is_admin(update.effective_user.id))
    )

async def daftar_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    actives = ctx.user_data.get("active_numbers", [])
    
    if not actives:
        await update.message.reply_text(
            "📋 *DAFTAR NOMOR AKTIF*\n\nTidak ada nomor aktif.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    paginated = Paginator.paginate(actives, 1)
    lines = [
        f"📋 *DAFTAR NOMOR AKTIF ({len(actives)})*\n",
        f"Hal {paginated['page']}/{paginated['total_pages']}\n",
        "─" * 20
    ]
    for i, n in enumerate(paginated["items"], 1):
        lines.append(
            f"\n*{i}.* 📞 `+{n['phone']}`\n"
            f"   🆔 `{n['id']}`\n"
            f"   📦 {n['service']} | {n['country']}\n"
            f"   🕐 {n['time']}"
        )
    
    keyboard = Paginator.get_keyboard("numbers", 1, paginated["total_pages"])
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

async def ceksms_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Manual cek SMS — biasanya tidak perlu karena sudah auto."""
    if not await check_access(update, ctx): return
    ensure_init(ctx)
    api_key = get_api_key(ctx)
    if not api_key:
        await prompt_api_key(update, ctx); return
    args = ctx.args
    if not args:
        actives = ctx.user_data.get("active_numbers", [])
        if not actives:
            await update.message.reply_text(
                "ℹ️ Tidak ada nomor aktif.\n\nOTP sudah dikirim otomatis saat masuk."
            ); return
        lines = ["📋 *ID Aktif (OTP sudah auto-notif):*\n"]
        for n in actives:
            lines.append(f"• `{n['id']}` → `+{n['phone']}`")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    act_id = args[0].strip()
    msg = await update.message.reply_text(
        f"⏳ Cek SMS `{act_id}`...\n\n`{LoadingBar.render(0)}`",
        parse_mode=ParseMode.MARKDOWN
    )
    await loading_animation(ctx, update.effective_chat.id, msg.message_id,
                           "Cek SMS", duration=1.0)
    result = api_get_sms(api_key, act_id)
    if result["status"] == "ok":
        await msg.edit_text(
            f"✅ OTP: `{result['code']}`\n\n`/konfirmasi {act_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    elif result["status"] == "waiting":
        await msg.edit_text(
            f"⏳ Belum ada SMS untuk `{act_id}`. OTP akan notif otomatis.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await msg.edit_text(
            f"❌ Status: {result.get('msg', '?')}",
            parse_mode=ParseMode.MARKDOWN
        )

async def setrange_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set range harga (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            f"💰 *SET RANGE HARGA*\n\n"
            f"Range saat ini:\n"
            f"📉 Minimum: ${PRICE_RANGE['min']:.2f}\n"
            f"📈 Maximum: ${PRICE_RANGE['max']:.2f}\n\n"
            f"Format: `/setrange <min> <max>`\n"
            f"Contoh: `/setrange 0.05 0.30`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_pricerange_keyboard()
        ); return
    
    try:
        new_min = float(args[0].replace("$", "").replace(",", "."))
        new_max = float(args[1].replace("$", "").replace(",", "."))
        
        if new_min < 0 or new_max < 0:
            raise ValueError("Negative")
        if new_min > new_max:
            await update.message.reply_text(
                "❌ Min tidak boleh lebih dari Max!"
            ); return
        
        PRICE_RANGE["min"] = new_min
        PRICE_RANGE["max"] = new_max
        add_log(ctx, f"SET RANGE | ${new_min:.2f} - ${new_max:.2f}")
        
        await update.message.reply_text(
            f"✅ *RANGE HARGA DIUBAH!*\n\n"
            f"📉 Minimum: ${PRICE_RANGE['min']:.2f}\n"
            f"📈 Maximum: ${PRICE_RANGE['max']:.2f}",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Format salah! Gunakan angka.\n"
            "Contoh: `/setrange 0.05 0.30`",
            parse_mode=ParseMode.MARKDOWN
        )

async def approve_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Approve user manual (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/approve <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        ); return
    
    try:
        user_id = int(args[0])
        
        if user_id in APPROVED_USERS:
            await update.message.reply_text(
                f"ℹ️ User `{user_id}` sudah di-approve.",
                parse_mode=ParseMode.MARKDOWN
            ); return
        
        # Ambil info dari pending jika ada
        user_info = PENDING_USERS.pop(user_id, {"name": "Unknown", "username": "-", "chat_id": user_id})
        APPROVED_USERS.add(user_id)
        
        # Notify user
        try:
            await ctx.bot.send_message(
                chat_id=user_info.get("chat_id", user_id),
                text="🎉 *AKSES DISETUJUI!*\n\nKamu sekarang dapat menggunakan bot.\nKetik /start untuk memulai.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ User `{user_id}` telah di-approve!",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"User {user_id} manually approved by {update.effective_user.id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ User ID harus berupa angka.",
            parse_mode=ParseMode.MARKDOWN
        )

async def reject_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Reject user manual (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only!")
        return
    
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Gunakan: `/reject <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        ); return
    
    try:
        user_id = int(args[0])
        
        # Ambil info dari pending jika ada
        user_info = PENDING_USERS.pop(user_id, {"name": "Unknown", "username": "-", "chat_id": user_id})
        
        # Hapus dari approved jika ada
        APPROVED_USERS.discard(user_id)
        
        # Notify user
        try:
            await ctx.bot.send_message(
                chat_id=user_info.get("chat_id", user_id),
                text="❌ *AKSES DITOLAK*\n\nMaaf, akses kamu telah dicabut.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        await update.message.reply_text(
            f"❌ User `{user_id}` telah di-reject.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"User {user_id} rejected by {update.effective_user.id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ User ID harus berupa angka.",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("myid",       myid_cmd))
    app.add_handler(CommandHandler("ceksms",     ceksms_cmd))
    app.add_handler(CommandHandler("cancel",     cancel_cmd))
    app.add_handler(CommandHandler("konfirmasi", konfirmasi_cmd))
    app.add_handler(CommandHandler("setlayanan", setlayanan_cmd))
    app.add_handler(CommandHandler("daftar",     daftar_cmd))
    app.add_handler(CommandHandler("setrange",   setrange_cmd))
    app.add_handler(CommandHandler("approve",    approve_cmd))
    app.add_handler(CommandHandler("reject",     reject_cmd))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^(approve|reject|info)_"))
    app.add_handler(CallbackQueryHandler(handle_pricerange_callback, pattern=r"^pricerange_"))
    app.add_handler(CallbackQueryHandler(handle_pagination_callback, pattern=r"^(numbers|logs|pending)_\d+"))

    print("╔════════════════════════════════════════════╗")
    print("║  🐻 GrizzlySMS Bot v5 - Enhanced Edition   ║")
    print("╠════════════════════════════════════════════╣")
    print("║  ✅ Auto OTP Active                        ║")
    print("║  ✅ User Approval System Active            ║")
    print("║  ✅ Price Range System Active              ║")
    print("║  ✅ Professional Loading Bar Active        ║")
    print("║  ✅ Professional Pagination Active         ║")
    print("╠════════════════════════════════════════════╣")
    print(f"║  👨‍💼 Admins: {len(ADMIN_IDS)}                              ║")
    print(f"║  ✅ Approved Users: {len(APPROVED_USERS)}                     ║")
    print(f"║  💵 Price Range: ${PRICE_RANGE['min']:.2f}-${PRICE_RANGE['max']:.2f}             ║")
    print("╚════════════════════════════════════════════╝")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
