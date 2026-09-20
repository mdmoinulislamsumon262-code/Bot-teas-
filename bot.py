"""
🌸 LUXURY PINK DIGITAL SHOP BOT — ZERO-STUCK SMART NAVIGATION EDITION 🌸
Features: Auto State-Break on Navigation, Zero-ID Admin, 3s Live Mail OTP, In-place 2FA & 50K Load-Ready.
"""

import hashlib
import html as _html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import os
import random
import re
import secrets
import sqlite3
import string
import sys
import threading
import time
from datetime import datetime
import pyotp
import requests
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ═══════════════════════════════════════════════════════════════════════════
# 🌸 কনফিগারেশন ও এনভায়রনমেন্ট ভেরিয়েবল
# ═══════════════════════════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "123456789").strip()
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else 123456789

DATA_DIR = os.getenv("DATA_DIR", "./data").strip() or "./data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "pink_shop.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pink_shop")

# ৫০,০০০ ইউজারের হাই-কনকারেন্সি ট্রাফিক সামলাতে ২০টি মাল্টি-থ্রেড ওয়ার্কার
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=20)

shop_states = {}
shop_nav = {}
_checkout_locks = set()
_lock = threading.Lock()
_gc_sessions = {}
_gc_auto_refresh_threads = {}
SELECT_PAGE_SIZE = 8

# ═══════════════════════════════════════════════════════════════════════════
# 🎀 নান্দনিক পিংক স্টাইল ও ফরম্যাটিং
# ═══════════════════════════════════════════════════════════════════════════
def stylish(text: str) -> str:
    """Mathematical monospace font for luxury badges & titles."""
    res = []
    for ch in str(text):
        if 'A' <= ch <= 'Z':
            res.append(chr(0x1D670 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            res.append(chr(0x1D68A + ord(ch) - ord('a')))
        elif '0' <= ch <= '9':
            res.append(chr(0x1D7F6 + ord(ch) - ord('0')))
        else:
            res.append(ch)
    return ''.join(res)

def st(t) -> str:
    return stylish(str(t))

def esc(v) -> str:
    return _html.escape(str(v if v is not None else ""))

def sep(c="━", n=24) -> str:
    return f"🌸 {c * n} 🌸"

def sep_pink(c="─", n=22) -> str:
    return f"🎀 {c * n} 🎀"

def _skey(chat_id, user_id) -> str:
    return f"{chat_id}:{user_id}"

def now_ts() -> int:
    return int(time.time())

def fmt_ts(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d-%m-%Y %I:%M %p")
    except Exception:
        return "N/A"

def money(v) -> str:
    try:
        return f"{float(v or 0):,.2f} {currency()}"
    except Exception:
        return f"0.00 {currency()}"

# ═══════════════════════════════════════════════════════════════════════════
# 🗄️ ৫০K ইউজার অপ্টিমাইজড ডাটাবেস ইঞ্জিন (WAL + High-Speed Cache)
# ═══════════════════════════════════════════════════════════════════════════
class DBConnection:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.path, timeout=45.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = -64000")  # 64MB RAM Cache
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.execute("PRAGMA busy_timeout = 30000")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

def conn():
    return DBConnection(DB_PATH)

def raw_conn():
    c = sqlite3.connect(DB_PATH, timeout=45.0, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA synchronous = NORMAL")
    c.execute("PRAGMA busy_timeout = 30000")
    return c

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            last_active_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS wallet (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS shop_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS shop_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            image_file_id TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            is_deleted INTEGER DEFAULT 0,
            sold INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_cart_coupon (
            user_id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            applied_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            subtotal REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            total REAL DEFAULT 0,
            coupon_code TEXT DEFAULT '',
            payment_status TEXT DEFAULT 'PAID',
            order_status TEXT DEFAULT 'PENDING',
            delivery_status TEXT DEFAULT 'NOT_DELIVERED',
            created_at INTEGER DEFAULT (strftime('%s','now')),
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT DEFAULT '',
            qty INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0,
            subtotal REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS shop_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            admin_id INTEGER,
            kind TEXT DEFAULT 'TEXT',
            content TEXT DEFAULT '',
            file_id TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT DEFAULT 'PERCENT',
            discount_value REAL DEFAULT 0,
            min_order REAL DEFAULT 0,
            max_usage INTEGER DEFAULT 0,
            per_user_limit INTEGER DEFAULT 1,
            start_at INTEGER DEFAULT 0,
            expiry_at INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_coupon_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            order_id TEXT DEFAULT '',
            used_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            kind TEXT DEFAULT 'OFFER',
            start_at INTEGER DEFAULT 0,
            expiry_at INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_topups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL DEFAULT 0,
            reference TEXT DEFAULT '',
            status TEXT DEFAULT 'PENDING',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id TEXT DEFAULT '',
            kind TEXT DEFAULT 'DEBIT',
            amount REAL DEFAULT 0,
            note TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE INDEX IF NOT EXISTS idx_prod_cat ON shop_products(category);
        CREATE INDEX IF NOT EXISTS idx_prod_active ON shop_products(is_deleted, enabled);
        CREATE INDEX IF NOT EXISTS idx_orders_user ON shop_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_st ON shop_orders(order_status);
        CREATE INDEX IF NOT EXISTS idx_tx_user ON shop_transactions(user_id);
        """)
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))

init_db()

# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ শপ সেটিংস ও হেল্পার ফাংশন
# ═══════════════════════════════════════════════════════════════════════════
def sget(key, default=""):
    try:
        with conn() as c:
            r = c.execute("SELECT value FROM shop_settings WHERE key=?", (key,)).fetchone()
            return r["value"] if r else default
    except Exception:
        return default

def sset(key, value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?,?)", (key, str(value)))

def shop_name() -> str:
    return sget("shop_name", "Pink Velvet Store 🌸")

def currency() -> str:
    return sget("currency", "BDT")

def is_admin(user_id: int) -> bool:
    if int(user_id) == int(ADMIN_ID):
        return True
    with conn() as c:
        row = c.execute("SELECT 1 FROM admins WHERE user_id=?", (int(user_id),)).fetchone()
        return bool(row)

def user_balance(user_id: int) -> float:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO wallet (user_id, balance) VALUES (?, 0.0)", (user_id,))
        row = c.execute("SELECT balance FROM wallet WHERE user_id=?", (user_id,)).fetchone()
        return float(row["balance"]) if row else 0.0

def adjust_balance(user_id: int, delta: float, admin_id: int, reason: str = ""):
    c = raw_conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("INSERT OR IGNORE INTO wallet (user_id) VALUES (?)", (user_id,))
        row = c.execute("SELECT balance FROM wallet WHERE user_id=?", (user_id,)).fetchone()
        bal = float(row["balance"] or 0)
        if delta < 0 and bal + delta < 0:
            c.execute("ROLLBACK")
            return False, f"⛔ {st('অপর্যাপ্ত ব্যালেন্স!')}"
        c.execute("UPDATE wallet SET balance=balance+? WHERE user_id=?", (delta, user_id))
        c.execute(
            "INSERT INTO shop_transactions (user_id, kind, amount, note) VALUES (?,?,?,?)",
            (user_id, "CREDIT" if delta > 0 else "DEBIT", abs(delta), reason)
        )
        c.execute("COMMIT")
    except Exception as exc:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        return False, "⛔ ব্যালেন্স আপডেট ব্যর্থ হয়েছে।"
    finally:
        c.close()
    
    try:
        send(user_id, f"💖 <b>{st('WALLET UPDATED')}</b>\n{sep_pink()}\n"
                      f"🌸 আপনার ওয়ালেটে <b>{'+' if delta > 0 else '−'} {money(abs(delta))}</b> জমা/কাটা হয়েছে।\n"
                      f"🏦 {st('বর্তমান ব্যালেন্স')}: <b>{money(user_balance(user_id))}</b>")
    except Exception:
        pass
    return True, "ok"

def send(chat_id, text, **kw):
    try:
        return bot.send_message(chat_id, text, **kw)
    except Exception as exc:
        logger.warning(f"Send failed chat={chat_id}: {exc}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# 🌸 কীবোর্ড ও মেনু লেআউট
# ═══════════════════════════════════════════════════════════════════════════
def L(emoji, text) -> str:
    return f"{emoji} {st(text)}"

BACK = lambda: L("◀️", "Back")

USER_MENUS = {
    "main": lambda admin: [
        [L("🛍️", "Products"), L("💳", "Shop Balance")],
        [L("📋", "My Orders"), L("🎁", "Offers & Bonus")],
        [L("🔑", "Get Code Center")],
    ] + ([[L("👑", "Shop Admin Panel")]] if admin else []),

    "products": lambda admin: [
        [L("🛍️", "Product")],
        [L("📦", "All Products"), L("🔎", "Search Product")],
        [BACK()],
    ],

    "balance": lambda admin: [
        [L("💰", "Current Balance"), L("➕", "Add Balance")],
        [L("📜", "Transaction History")],
        [BACK()],
    ],

    "orders": lambda admin: [
        [L("⏳", "Pending Orders"), L("🚚", "Processing Orders")],
        [L("✅", "Confirmed Orders"), L("📦", "Delivered Orders")],
        [L("❌", "Cancelled Orders"), L("🔎", "Order Lookup")],
        [BACK()],
    ],

    "offers": lambda admin: [
        [L("🔥", "Special Offers"), L("🎟️", "Apply Promo Code")],
        [L("💎", "Active Discounts"), L("🎁", "Bonus Items")],
        [BACK()],
    ],
}

ADMIN_MAIN_MENU = lambda: [
    [L("➕", "Add Product"), L("📦", "Manage Products & Stock")],
    [L("🧾", "Manage Orders"), L("🎟️", "Promo & Coupons")],
    [L("📊", "Full Shop Reports"), L("⚙️", "Shop Settings")],
    [BACK()],
]

# সকল মেনু বাটনের তালিকা (ইনপুট স্টেট স্বয়ংক্রিয়ভাবে ব্রেক করার জন্য)
def get_all_navigation_buttons():
    buttons = {
        L("🛍️", "Products"), L("💳", "Shop Balance"), L("📋", "My Orders"),
        L("🎁", "Offers & Bonus"), L("🔑", "Get Code Center"), L("👑", "Shop Admin Panel"),
        BACK(), L("⛔", "Cancel"), "◀️ Back", "/cancel",
        # Sub-menus:
        L("🛍️", "Product"), L("🌸", "Product"), L("📦", "All Products"), L("🔎", "Search Product"),
        L("💰", "Current Balance"), L("➕", "Add Balance"), L("📜", "Transaction History"),
        L("⏳", "Pending Orders"), L("🚚", "Processing Orders"), L("✅", "Confirmed Orders"),
        L("📦", "Delivered Orders"), L("❌", "Cancelled Orders"), L("🔎", "Order Lookup"),
        L("🔥", "Special Offers"), L("🎟️", "Apply Promo Code"), L("💎", "Active Discounts"), L("🎁", "Bonus Items"),
        # Admin Buttons:
        L("➕", "Add Product"), L("📦", "Manage Products & Stock"), L("🧾", "Manage Orders"),
        L("🎟️", "Promo & Coupons"), L("📊", "Full Shop Reports"), L("⚙️", "Shop Settings"),
    }
    return buttons

def keyboard_for(menu: str, user_id: int):
    adm = is_admin(user_id)
    if menu == "admin":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for row in ADMIN_MAIN_MENU():
            kb.add(*[KeyboardButton(b) for b in row])
        return kb

    spec = USER_MENUS.get(menu)
    if not spec:
        return None
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for row in spec(adm):
        kb.add(*[KeyboardButton(b) for b in row])
    return kb

def render_menu(chat_id, user_id, menu, text=None, push=True):
    adm = is_admin(user_id)
    if push:
        stack = shop_nav.setdefault(user_id, [])
        if menu == "main":
            shop_nav[user_id] = ["main"]
        elif not stack or stack[-1] != menu:
            stack.append(menu)

    bal = user_balance(user_id)
    title = (
        f"🌸 <b>{st(shop_name().upper())}</b> 🌸\n{sep()}\n"
        f"✨ <i>আমাদের প্রিমিয়াম ডিজিটাল শপে আপনাকে স্বাগতম!</i>\n\n"
        f"<blockquote>"
        f"💖 <b>{st('Wallet Balance')}:</b> <b>{money(bal)}</b>\n"
        f"🛍️ <b>{st('Service Status')}:</b> 🟢 <b>{st('Active & Super Fast')}</b>"
        f"</blockquote>\n\n"
        f"👇 <i>পণ্য কেনাকাটা বা কোড পেতে নিচের অপশন নির্বাচন করুন:</i>"
    )
    if menu == "admin":
        title = f"👑 <b>{st('CLEAN ADMIN PANEL')}</b>\n{sep()}\n{_admin_overview()}"
    elif menu == "products":
        title = f"🛍️ <b>{st('PRODUCT CATALOGUE')}</b>\n{sep()}\n✨ <i>আমাদের সবথেকে আকর্ষণীয় প্রোডাক্টসমূহ এক্সপ্লোর করুন:</i>"
    elif menu == "balance":
        title = (
            f"💳 <b>{st('SHOP BALANCE & WALLET')}</b> 🌸\n{sep()}\n\n"
            f"<blockquote>"
            f"💰 <b>{st('Current Balance')}:</b> <b>{money(bal)}</b>\n"
            f"🏦 <b>{st('Account Status')}:</b> 🟢 <b>{st('Active')}</b>"
            f"</blockquote>\n\n"
            f"<i>ব্যালেন্স যোগ করতে বা ট্রানজেকশন দেখতে নিচের বাটন ব্যবহার করুন:</i>"
        )
    elif menu == "orders":
        title = f"📋 <b>{st('ORDER MANAGEMENT')}</b>\n{sep()}\n✨ <i>আপনার অর্ডারের বর্তমান অবস্থা ও ডেলিভারি দেখতে নির্বাচন করুন:</i>"
    elif menu == "offers":
        title = f"🎁 <b>{st('PROMOTIONS & DISCOUNTS')}</b>\n{sep()}\n✨ <i>আজকের সেরা অফার ও ডিসকাউন্ট কুপনগুলো উপভোগ করুন:</i>"

    body = text or title
    send(chat_id, body, reply_markup=keyboard_for(menu, user_id))

def _admin_overview() -> str:
    try:
        with conn() as c:
            prod = c.execute("SELECT COUNT(*) n FROM shop_products WHERE is_deleted=0").fetchone()["n"]
            pend = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE order_status='PENDING'").fetchone()["n"]
            rev = c.execute("SELECT COALESCE(SUM(total),0) t FROM shop_orders WHERE order_status IN ('CONFIRMED','PROCESSING','DELIVERED')").fetchone()["t"]
            low = c.execute("SELECT COUNT(*) n FROM shop_products WHERE is_deleted=0 AND stock<=5").fetchone()["n"]
        return (
            f"<blockquote>"
            f"📦 <b>{st('Total Products')}:</b> <b>{prod}</b>\n"
            f"⏳ <b>{st('Pending Orders')}:</b> <b>{pend}</b>\n"
            f"💰 <b>{st('Total Revenue')}:</b> <b>{money(rev)}</b>\n"
            f"⚠️ <b>{st('Low Stock Alert')}:</b> <b>{low}</b>"
            f"</blockquote>"
        )
    except Exception:
        return st("Choose an option below.")

def go_back(chat_id, user_id):
    stack = shop_nav.get(user_id) or []
    if stack:
        stack.pop()
    if stack:
        render_menu(chat_id, user_id, stack[-1], push=False)
    else:
        render_menu(chat_id, user_id, "main", push=False)

# ═══════════════════════════════════════════════════════════════════════════
# 🛍️ প্রোডাক্ট ও ইনস্ট্যান্ট ক্রয় লজিক
# ═══════════════════════════════════════════════════════════════════════════
def get_product(pid, admin=False):
    q = "SELECT * FROM shop_products WHERE product_id=?"
    if not admin:
        q += " AND is_deleted=0"
    with conn() as c:
        row = c.execute(q, (str(pid),)).fetchone()
    return dict(row) if row else None

def list_products(kind="all", arg="", limit=SELECT_PAGE_SIZE, offset=0):
    base = "SELECT * FROM shop_products WHERE is_deleted=0 AND enabled=1"
    params = []
    if kind == "cat":
        base += " AND LOWER(category)=LOWER(?)"
        params.append(arg)
    elif kind == "search":
        like = f"%{arg.lower()}%"
        base += " AND (LOWER(name) LIKE ? OR LOWER(product_id) LIKE ? OR LOWER(category) LIKE ?)"
        params += [like, like, like]
    base += " ORDER BY sold DESC, id DESC LIMIT ? OFFSET ?"
    params += [limit + 1, offset]
    with conn() as c:
        rows = [dict(r) for r in c.execute(base, params).fetchall()]
    has_more = len(rows) > limit
    return rows[:limit], has_more

def product_card(p) -> str:
    stock_line = f"❌ {st('Out of Stock')}" if int(p["stock"]) <= 0 else f"<b>{int(p['stock'])} টি অবশিষ্ট</b>"
    return (
        f"🌸 <b>{esc(p['name'])}</b> 🌸\n{sep_pink()}\n"
        f"<blockquote>"
        f"🆔 <b>{st('Product Code')}:</b> <code>{esc(p['product_id'])}</code>\n"
        f"🗂️ <b>{st('Category')}:</b> {esc(p['category'])}\n"
        f"💰 <b>{st('Price')}:</b> <b>{money(p['price'])}</b>\n"
        f"📦 <b>{st('Stock Status')}:</b> {stock_line}"
        f"</blockquote>\n\n"
        f"📝 <b>{st('Product Details')}:</b>\n"
        f"<blockquote>{esc(p.get('description') or 'কোনো বিস্তারিত বিবরণ নেই।')}</blockquote>"
    )

def product_inline(p):
    kb = InlineKeyboardMarkup(row_width=1)
    if int(p["stock"]) > 0 and p["enabled"] and not p["is_deleted"]:
        kb.add(InlineKeyboardButton(f"⚡ {st('BUY NOW (INSTANT)')} 🌸", callback_data=f"shop_qty:buy:{p['product_id']}:1"))
    else:
        kb.add(InlineKeyboardButton(f"❌ {st('Stock Out')}", callback_data="shop_noop"))
    kb.add(InlineKeyboardButton(f"◀️ {st('Back to Catalogue')}", callback_data="shop_list:all::0"))
    return kb

def send_product_list(chat_id, user_id, kind, arg="", page=0):
    rows, has_more = list_products(kind, arg, SELECT_PAGE_SIZE, page * SELECT_PAGE_SIZE)
    if not rows:
        send(chat_id, f"📭 <i>দুঃখিত! এই মুহূর্তে কোনো প্রোডাক্ট পাওয়া যায়নি।</i>")
        return
    title_kind = f"CATEGORY: {arg}" if kind == "cat" else kind.upper()
    lines = [f"🌸 <b>{st('PRODUCT LISTING')} • {st(title_kind)}</b> 🌸\n{sep()}"]
    kb = InlineKeyboardMarkup(row_width=1)
    for p in rows:
        stock = "❌ স্টক শেষ" if int(p["stock"]) <= 0 else f"📦 {int(p['stock'])} টি"
        lines.append(f"• <b>{esc(p['name'])}</b>\n  💰 {money(p['price'])} | {stock} | 🆔 <code>{p['product_id']}</code>")
        kb.add(InlineKeyboardButton(f"🛍️ {p['name'][:24]} — {money(p['price'])}", callback_data=f"shop_view:{p['product_id']}"))
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ পূর্ববর্তী", callback_data=f"shop_list:{kind}:{arg}:{page-1}"))
    if has_more:
        nav.append(InlineKeyboardButton("পরবর্তী ▶️", callback_data=f"shop_list:{kind}:{arg}:{page+1}"))
    if nav:
        kb.row(*nav)
    send(chat_id, "\n".join(lines), reply_markup=kb)

def validate_coupon(code, user_id, subtotal):
    code = str(code or "").strip().upper()
    if not code:
        return False, "কোনো কুপন কোড দেওয়া হয়নি।", 0.0
    with conn() as c:
        row = c.execute("SELECT * FROM shop_coupons WHERE UPPER(code)=?", (code,)).fetchone()
        if not row:
            return False, "অবৈধ কুপন কোড!", 0.0
        cp = dict(row)
        used_by_user = c.execute("SELECT COUNT(*) n FROM shop_coupon_usage WHERE UPPER(code)=? AND user_id=?", (code, user_id)).fetchone()["n"]
    if not cp["enabled"]:
        return False, "এই কুপনটি বর্তমানে নিষ্ক্রিয়।", 0.0
    ts = now_ts()
    if cp["start_at"] and ts < int(cp["start_at"]):
        return False, "কুপনটি এখনো শুরু হয়নি।", 0.0
    if cp["expiry_at"] and ts > int(cp["expiry_at"]):
        return False, "কুপনের মেয়াদ শেষ হয়ে গেছে।", 0.0
    if cp["min_order"] and float(subtotal) < float(cp["min_order"]):
        return False, f"ন্যূনতম অর্ডারের পরিমাণ হতে হবে {money(cp['min_order'])}", 0.0
    if cp["max_usage"] and int(cp["used_count"]) >= int(cp["max_usage"]):
        return False, "কুপন ব্যবহারের সর্বোচ্চ লিমিট শেষ।", 0.0
    if cp["per_user_limit"] and used_by_user >= int(cp["per_user_limit"]):
        return False, "আপনি ইতিমধ্যে এই কুপনটি ব্যবহার করে ফেলেছেন।", 0.0
    if cp["discount_type"].upper() == "PERCENT":
        disc = float(subtotal) * float(cp["discount_value"]) / 100.0
    else:
        disc = float(cp["discount_value"])
    return True, f"কুপন সক্রিয় হয়েছে! ছাড়: −{money(disc)}", round(min(disc, float(subtotal)), 2)

def place_order(user, chat_id, payload):
    user_id = user.id
    with _lock:
        if user_id in _checkout_locks:
            return None, "পূর্ববর্তী অর্ডারটি এখনো প্রসেস হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন।"
        _checkout_locks.add(user_id)
    c = None
    try:
        order_id = "PK" + datetime.now().strftime("%y%m%d") + secrets.token_hex(2).upper()
        total = float(payload["total"])
        c = raw_conn()
        c.execute("BEGIN IMMEDIATE")
        
        # Stock Check
        for it in payload["items"]:
            r = c.execute("SELECT price, stock, enabled, is_deleted FROM shop_products WHERE product_id=?", (it["product_id"],)).fetchone()
            if not r or r["is_deleted"] or not r["enabled"] or int(r["stock"]) < it["qty"]:
                c.execute("ROLLBACK")
                return None, f"দুঃখিত! <b>{it['name']}</b> এর স্টক শেষ হয়ে গেছে।"

        # Deduct wallet
        cur = c.execute("UPDATE wallet SET balance=balance-? WHERE user_id=? AND balance>=?", (total, user_id, total))
        if cur.rowcount != 1:
            c.execute("ROLLBACK")
            return None, "অপর্যাপ্ত ব্যালেন্স! ওয়ালেট রিচার্জ করুন।"

        for it in payload["items"]:
            c.execute("UPDATE shop_products SET stock=stock-?, sold=sold+? WHERE product_id=?", (it["qty"], it["qty"], it["product_id"]))

        uname = f"@{user.username}" if user.username else ""
        c.execute("""
            INSERT INTO shop_orders (order_id, user_id, username, subtotal, discount, total, coupon_code, payment_status, order_status, delivery_status)
            VALUES (?,?,?,?,?,?,?,'PAID','PROCESSING','NOT_DELIVERED')
        """, (order_id, user_id, uname, payload["subtotal"], payload["discount"], total, payload["coupon"]))

        for it in payload["items"]:
            c.execute("INSERT INTO shop_order_items (order_id, product_id, product_name, qty, unit_price, subtotal) VALUES (?,?,?,?,?,?)",
                      (order_id, it["product_id"], it["name"], it["qty"], it["unit_price"], it["subtotal"]))

        if payload["coupon"]:
            c.execute("INSERT INTO shop_coupon_usage (code, user_id, order_id) VALUES (?,?,?)", (payload["coupon"], user_id, order_id))
            c.execute("UPDATE shop_coupons SET used_count=used_count+1 WHERE UPPER(code)=?", (payload["coupon"],))

        c.execute("INSERT INTO shop_transactions (user_id, order_id, kind, amount, note) VALUES (?,?,?,?,?)",
                  (user_id, order_id, "DEBIT", total, "Order purchase payment"))
        c.execute("COMMIT")
        return order_id, None
    except Exception as exc:
        logger.error(f"Place order failed: {exc}")
        if c:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return None, "অর্ডার সম্পন্ন হতে ব্যর্থ হয়েছে। আপনার ব্যালেন্স কাটা হয়নি।"
    finally:
        if c:
            try:
                c.close()
            except Exception:
                pass
        with _lock:
            _checkout_locks.discard(user_id)

def send_instant_buy_invoice(chat_id, user_id, product, qty=1):
    subtotal = float(product["price"]) * qty
    code = ""
    disc = 0.0
    total = max(0.0, subtotal - disc)
    bal = user_balance(user_id)
    
    if bal < total:
        send(chat_id, f"⛔ <b>{st('INSUFFICIENT BALANCE')}</b> 🌸\n{sep_pink()}\n"
                      f"💰 <b>{st('Product Price')}:</b> <b>{money(total)}</b>\n"
                      f"🏦 <b>{st('Current Balance')}:</b> <b>{money(bal)}</b>\n\n"
                      f"<i>আপনার ব্যালেন্স কম রয়েছে। 'Shop Balance' মেনু থেকে ব্যালেন্স যোগ করুন।</i>")
        return

    token = secrets.token_hex(4)
    item_entry = {"product_id": product["product_id"], "name": product["name"], "qty": qty, "unit_price": float(product["price"]), "subtotal": subtotal}
    shop_states[_skey(chat_id, user_id)] = {
        "step": "await_confirm",
        "data": {"token": token, "payload": {"items": [item_entry], "subtotal": subtotal, "discount": disc, "total": total, "coupon": code}}
    }
    
    lines = [
        f"🧾 <b>{st('INSTANT PURCHASE INVOICE')}</b> 🌸\n{sep()}\n",
        f"• <b>{esc(product['name'])}</b> × {qty} = <b>{money(subtotal)}</b>\n",
        f"{sep_pink()}\n",
        f"💵 <b>{st('Subtotal')}:</b> {money(subtotal)}\n",
        f"💰 <b>{st('Final Payable')}:</b> <b>{money(total)}</b>\n\n",
        f"🏦 <b>{st('Current Wallet')}:</b> <b>{money(bal)}</b>\n",
        f"💳 <b>{st('Remaining Balance')}:</b> <b>{money(bal - total)}</b>"
    ]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"🌸 {st('CONFIRM & PAY')} ({money(total)}) 🌸", callback_data=f"shop_confirm:{token}"))
    kb.add(InlineKeyboardButton(f"❌ {st('Cancel')}", callback_data="shop_confirm_cancel"))
    send(chat_id, "".join(lines), reply_markup=kb)

# ═══════════════════════════════════════════════════════════════════════════
# 🔑 GET CODE CENTER (3s Auto-Refresh Mail + In-Place 2FA)
# ═══════════════════════════════════════════════════════════════════════════
def _gc_hotmail_otp(refresh_token, client_id):
    try:
        token_res = requests.post(
            "https://login.live.com/oauth20_token.srf",
            data={
                "client_id": client_id,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "https://graph.microsoft.com/Mail.Read offline_access",
            },
            timeout=10,
        )
        tdata = token_res.json()
        if "access_token" not in tdata:
            return False, "টোকেন এক্সপায়ার্ড অথবা Client ID/Refresh Token সঠিক নয়।"
        mail_res = requests.get(
            "https://graph.microsoft.com/v1.0/me/messages?$top=1&$orderby=receivedDateTime desc",
            headers={"Authorization": f"Bearer {tdata['access_token']}"},
            timeout=10,
        )
        mdata = mail_res.json()
        if mdata.get("value"):
            msg = mdata["value"][0]
            body = msg.get("body", {}).get("content", "")
            subject = msg.get("subject", "No Subject")
            sender = msg.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            otp = _gc_extract_otp(body, subject)
            if otp:
                return True, {"otp": otp, "sender": sender, "subject": subject, "date": msg.get("receivedDateTime", "")}
            return False, "ইনবক্সে মেইল এসেছে কিন্তু কোনো ওটিপি কোড খুঁজে পাওয়া যায়নি।"
        return False, "ইনবক্সে কোনো নতুন মেইল পাওয়া যায়নি।"
    except Exception as exc:
        return False, f"কানেকশন এরর: {str(exc)[:60]}"

def _gc_extract_otp(body, subject):
    clean = re.sub(r"<[^<]+?>", " ", str(body or ""))
    full = f"{subject or ''} {clean}"
    
    spaced = re.findall(r'(?<!\d)(\d{3,4}[ \-]\d{3,4})(?!\d)', full)
    if spaced:
        return re.sub(r'[ \-]', '', spaced[0])

    for word in ("code", "otp", "verification", "confirmation", "pin", "password"):
        m = re.search(rf"{word}.*?(\d{{4,8}})", full, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1)
    for digit in re.findall(r"\b\d{4,8}\b", full):
        if not (2000 <= int(digit) <= 2030):
            return digit
    return None

def build_mail_waiting_card(email, check_count=0):
    spinners = ["⏳", "⌛", "🔄", "✨", "🌸"]
    spinner = spinners[check_count % len(spinners)]
    return (
        f"🌸 <b>{st('LIVE MAIL OTP CHECKER')}</b> 🌸\n{sep()}\n\n"
        f"<blockquote>"
        f"📧 <b>{st('Account')}:</b> <code>{esc(email)}</code>\n"
        f"🛰️ <b>{st('Engine')}:</b> <code>Microsoft Graph API</code>\n"
        f"🔄 <b>{st('Live Status')}:</b> {spinner} <b>{st('Checking every 3s...')}</b>\n"
        f"⏱️ <b>{st('Refreshes')}:</b> <code>{check_count}</code> বার চেক করা হয়েছে"
        f"</blockquote>\n\n"
        f"<i>💡 কোড আসার সাথে সাথে এই মেসেজটি স্বয়ংক্রিয়ভাবে আপডেট হয়ে যাবে।</i>"
    )

def build_mail_success_card(email, res):
    return (
        f"✨ {sep()} ✨\n"
        f"        💖 <b>{st('NEW OTP CODE ARRIVED')}</b> 💖\n"
        f"✨ {sep()} ✨\n\n"
        f"<blockquote>"
        f"📧 <b>{st('Account')}:</b> <code>{esc(email)}</code>\n"
        f"🏷️ <b>{st('Sender')}:</b> <code>{esc(res['sender'])}</code>\n"
        f"📌 <b>{st('Subject')}:</b> <i>{esc(res['subject'])}</i>"
        f"</blockquote>\n\n"
        f"🔑 <b>{st('YOUR OTP CODE')}:</b>\n"
        f"┌{'─'*24}┐\n"
        f"  <code>{esc(res['otp'])}</code>\n"
        f"└{'─'*24}┘\n"
        f"<i>👆 কোডের উপর আলতো ট্যাপ করে কপি করে নিন।</i>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌸 <b>{st('Live Auto-Refresher Active')}</b>"
    )

def _gc_progress_bar(remaining, total=30) -> str:
    filled = int((remaining / total) * 10)
    return "█" * filled + "░" * (10 - filled)

def build_2fa_card(otp, remaining):
    return (
        f"🛡️ <b>{st('LIVE 2FA AUTHENTICATOR')}</b> 🌸\n{sep()}\n\n"
        f"🔢 <b>{st('CURRENT 2FA CODE')}:</b>\n"
        f"┌{'─'*24}┐\n"
        f"  <code>{otp}</code>\n"
        f"└{'─'*24}┘\n"
        f"<i>👆 কোডের উপর আলতো ট্যাপ করে কপি করে নিন।</i>\n\n"
        f"<blockquote>"
        f"⏳ <b>{st('Expires in')}:</b> <code>{remaining}s</code> / 30s\n"
        f"📊 <code>{_gc_progress_bar(remaining)}</code>\n"
        f"🔄 <b>{st('Status')}:</b> লাইভ ইন-প্লেস রিফ্রেশ"
        f"</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌸 <i>'Refresh 2FA' বাটনে চাপলে কোনো নতুন মেসেজ ছাড়া এখানেই কোড আপডেট হবে।</i>"
    )

def _start_mail_auto_refresh(chat_id, msg_id, uid):
    if uid in _gc_auto_refresh_threads:
        _gc_auto_refresh_threads[uid] = False
        time.sleep(0.5)

    _gc_auto_refresh_threads[uid] = True

    def poller():
        ses = _gc_sessions.get(uid, {})
        r_token = ses.get("r_token")
        c_id = ses.get("c_id")
        email = ses.get("email", "Mail Account")
        check_count = 0
        last_otp = None

        while _gc_auto_refresh_threads.get(uid, False) and check_count < 60:
            time.sleep(3)
            check_count += 1
            if not _gc_auto_refresh_threads.get(uid, False):
                break

            ok, res = _gc_hotmail_otp(r_token, c_id)
            if ok:
                if res["otp"] != last_otp:
                    last_otp = res["otp"]
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(
                        InlineKeyboardButton("♻️ আবার চেক করুন", callback_data="shop_gc:mail_check"),
                        InlineKeyboardButton("🛑 বন্ধ করুন", callback_data="shop_gc:stop_auto")
                    )
                    try:
                        bot.edit_message_text(
                            build_mail_success_card(email, res),
                            chat_id=chat_id,
                            message_id=msg_id,
                            reply_markup=kb
                        )
                    except Exception:
                        pass
            else:
                if check_count % 3 == 0:
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(
                        InlineKeyboardButton("♻️ এখনই চেক করুন", callback_data="shop_gc:mail_check"),
                        InlineKeyboardButton("🛑 বন্ধ করুন", callback_data="shop_gc:stop_auto")
                    )
                    try:
                        bot.edit_message_text(
                            build_mail_waiting_card(email, check_count),
                            chat_id=chat_id,
                            message_id=msg_id,
                            reply_markup=kb
                        )
                    except Exception:
                        pass

        _gc_auto_refresh_threads[uid] = False

    t = threading.Thread(target=poller, daemon=True)
    t.start()

def gc_open_menu(chat_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"📧 {st('Mail Code (OTP)')}", callback_data="shop_gc:mail"),
        InlineKeyboardButton(f"🛡️ {st('2FA Live Code')}", callback_data="shop_gc:2fa"),
    )
    send(
        chat_id,
        f"🔑 <b>{st('GET CODE CENTER — LUXURY')}</b> 🌸\n{sep()}\n"
        f"✨ <i>যেকোনো সার্ভিসের ওটিপি ও ২এফএ কোড নিমেষেই বের করুন:</i>\n\n"
        f"<blockquote>"
        f"📧 <b>{st('Mail Code')}</b> ➤ হটমেইল/আউটলুক ইনবক্স থেকে ৩ সেকেন্ড অটো-রিফ্রেশ ওটিপি\n"
        f"🛡️ <b>{st('2FA Code')}</b> ➤ Secret Key দিয়ে ইনস্ট্যান্ট লাইভ ৬ ডিজিট কোড"
        f"</blockquote>\n\n"
        f"👇 <i>আপনার পছন্দমতো অপশনটি বেছে নিন:</i>",
        reply_markup=kb
    )

# ═══════════════════════════════════════════════════════════════════════════
# 👑 স্মার্ট অ্যাডমিন প্রোডাক্ট ও স্টক কন্ট্রোল (ZERO-ID PROMPT)
# ═══════════════════════════════════════════════════════════════════════════
def admin_show_products_list(chat_id):
    with conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM shop_products WHERE is_deleted=0 ORDER BY id DESC").fetchall()]
    if not rows:
        send(chat_id, f"📭 <i>কোনো প্রোডাক্ট নেই। '➕ Add Product' দিয়ে যোগ করুন।</i>")
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for p in rows:
        flag = "🟢" if p["enabled"] else "🔴"
        label = f"{flag} {p['name'][:22]} (📦 {p['stock']} | 💰 {money(p['price'])})"
        kb.add(InlineKeyboardButton(label, callback_data=f"adm_pview:{p['product_id']}"))
    send(chat_id, f"📦 <b>{st('MANAGE PRODUCTS & STOCK')}</b> 🌸\n{sep()}\n<i>যে প্রোডাক্টটি কন্ট্রোল বা এডিট করতে চান তার ওপর চাপুন:</i>", reply_markup=kb)

def admin_product_control_card(chat_id, pid):
    p = get_product(pid, admin=True)
    if not p:
        send(chat_id, f"⛔ <i>প্রোডাক্ট পাওয়া যায়নি।</i>")
        return

    text = (
        f"🌸 <b>{esc(p['name'])}</b> (<code>{esc(p['product_id'])}</code>) 🌸\n{sep_pink()}\n"
        f"<blockquote>"
        f"🗂️ <b>{st('Category')}:</b> {esc(p['category'])}\n"
        f"💰 <b>{st('Price')}:</b> {money(p['price'])}\n"
        f"📦 <b>{st('Stock Available')}:</b> <b>{p['stock']} টি</b>\n"
        f"🟢 <b>{st('Status')}:</b> {'সক্রিয় (Active)' if p['enabled'] else 'নিষ্ক্রিয় (Disabled)'}"
        f"</blockquote>"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton("➕ Stock Up (+10)", callback_data=f"adm_stkadd:{pid}:10"),
        InlineKeyboardButton("➕ Custom Stock", callback_data=f"adm_stkcustom:{pid}"),
    )
    kb.row(
        InlineKeyboardButton("❌ Stock Out (Set 0)", callback_data=f"adm_stkzero:{pid}"),
        InlineKeyboardButton(f"{'🔴 Disable' if p['enabled'] else '🟢 Enable'}", callback_data=f"adm_toggle:{pid}"),
    )
    kb.row(
        InlineKeyboardButton("✏️ Edit Price", callback_data=f"adm_editprice:{pid}"),
        InlineKeyboardButton("🖼️ Change Photo", callback_data=f"adm_setphoto:{pid}"),
    )
    kb.row(
        InlineKeyboardButton("🗑️ Delete Product", callback_data=f"adm_delprod:{pid}"),
        InlineKeyboardButton("◀️ All Products", callback_data="adm_back_prodlist"),
    )

    if p.get("image_file_id"):
        try:
            bot.send_photo(chat_id, p["image_file_id"], caption=text, reply_markup=kb)
            return
        except Exception:
            pass
    send(chat_id, text, reply_markup=kb)

def admin_show_orders_overview(chat_id):
    with conn() as c:
        pend = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE order_status='PENDING'").fetchone()["n"]
        proc = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE order_status='PROCESSING'").fetchone()["n"]
        deli = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE order_status='DELIVERED'").fetchone()["n"]
        canc = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE order_status='CANCELLED'").fetchone()["n"]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton(f"⏳ Pending ({pend})", callback_data="adm_ordlist:PENDING"),
        InlineKeyboardButton(f"🚚 Processing ({proc})", callback_data="adm_ordlist:PROCESSING"),
    )
    kb.row(
        InlineKeyboardButton(f"📦 Delivered ({deli})", callback_data="adm_ordlist:DELIVERED"),
        InlineKeyboardButton(f"❌ Cancelled ({canc})", callback_data="adm_ordlist:CANCELLED"),
    )
    send(chat_id, f"🧾 <b>{st('MANAGE ORDERS')}</b> 🌸\n{sep()}\n<i>অর্ডার ক্যাটাগরি নির্বাচন করুন:</i>", reply_markup=kb)

def admin_show_full_reports(chat_id):
    now = now_ts()
    with conn() as c:
        today_rev = c.execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM shop_orders WHERE order_status IN ('CONFIRMED','PROCESSING','DELIVERED') AND created_at>=?", (now - 86400,)).fetchone()
        week_rev = c.execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM shop_orders WHERE order_status IN ('CONFIRMED','PROCESSING','DELIVERED') AND created_at>=?", (now - 7*86400,)).fetchone()
        month_rev = c.execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM shop_orders WHERE order_status IN ('CONFIRMED','PROCESSING','DELIVERED') AND created_at>=?", (now - 30*86400,)).fetchone()
        top_prods = c.execute("SELECT product_name, SUM(qty) q, SUM(subtotal) s FROM shop_order_items GROUP BY product_id ORDER BY q DESC LIMIT 5").fetchall()
        users_cnt = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        prods_cnt = c.execute("SELECT COUNT(*) n FROM shop_products WHERE is_deleted=0").fetchone()["n"]

    top_lines = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, r in enumerate(top_prods):
        top_lines.append(f"{medals[i]} <b>{esc(r['product_name'])}</b> — {r['q']} টি বিক্রি ({money(r['s'])})")
    if not top_lines:
        top_lines.append("<i>এখনো কোনো বিক্রয় হয়নি।</i>")

    send(chat_id,
         f"📊 <b>{st('FULL SHOP PERFORMANCE REPORT')}</b> 🌸\n{sep()}\n\n"
         f"<blockquote>"
         f"📅 <b>{st('Today Sales')}:</b> <b>{money(today_rev['t'])}</b> ({today_rev['n']} Orders)\n"
         f"🗓️ <b>{st('7-Day Revenue')}:</b> <b>{money(week_rev['t'])}</b> ({week_rev['n']} Orders)\n"
         f"📆 <b>{st('30-Day Revenue')}:</b> <b>{money(month_rev['t'])}</b> ({month_rev['n']} Orders)\n\n"
         f"👥 <b>{st('Total Buyers')}:</b> <b>{users_cnt} জন</b>\n"
         f"📦 <b>{st('Active Products')}:</b> <b>{prods_cnt} টি</b>"
         f"</blockquote>\n\n"
         f"🏆 <b>{st('TOP SELLING PRODUCTS')}:</b>\n" + "\n".join(top_lines))

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 মেসেজ হ্যান্ডলার ও স্টেট মেশিন (স্মার্ট স্টেট ব্রেকার সহ)
# ═══════════════════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    shop_states.pop(_skey(message.chat.id, uid), None)
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO users (id, first_name, username, last_active_at) VALUES (?,?,?,?)",
                  (uid, message.from_user.first_name or "", message.from_user.username or "", now_ts()))
        c.execute("INSERT OR IGNORE INTO wallet (user_id, balance) VALUES (?, 0.0)", (uid,))
    render_menu(message.chat.id, uid, "main")

@bot.message_handler(content_types=["photo", "document"])
def handle_media_messages(message):
    uid, chat_id = message.from_user.id, message.chat.id
    key = _skey(chat_id, uid)
    state = shop_states.get(key)
    
    # Upload logo during Add Product
    if state and state.get("step") == "ap_photo":
        file_id = message.photo[-1].file_id if message.photo else (message.document.file_id if message.document else "")
        d = state["data"]
        with conn() as c:
            cnt = c.execute("SELECT COUNT(*) n FROM shop_products").fetchone()["n"]
            pid = f"PK{1001 + cnt}"
            c.execute("""
                INSERT INTO shop_products (product_id, name, category, description, price, stock, image_file_id)
                VALUES (?,?,?,?,?,?,?)
            """, (pid, d["name"], d["cat"], d["desc"], d["price"], d["stock"], file_id))
            
        shop_states.pop(key, None)
        send(chat_id, f"🌸 <b>{st('PRODUCT & LOGO ADDED SUCCESSFULLY')}</b> 🌸\n{sep_pink()}\n"
                      f"🆔 <code>{pid}</code> | <b>{esc(d['name'])}</b>\n"
                      f"💰 {money(d['price'])} | 📦 {d['stock']} টি\n"
                      f"🖼️ <i>লোগো সফলভাবে সেট করা হয়েছে!</i>")
        render_menu(chat_id, uid, "admin")
        return

    # Update photo for existing product
    if state and state.get("step") == "adm_wait_photo":
        file_id = message.photo[-1].file_id if message.photo else (message.document.file_id if message.document else "")
        pid = state["pid"]
        with conn() as c:
            c.execute("UPDATE shop_products SET image_file_id=? WHERE product_id=?", (file_id, pid))
        shop_states.pop(key, None)
        send(chat_id, f"✅ <b>{st('PHOTO UPDATED')}</b>\nনতুন ছবি সফলভাবে সেভ করা হয়েছে।")
        admin_product_control_card(chat_id, pid)
        return

    # Deliver order via document/photo
    if state and state.get("step") == "adm_deliver_file":
        file_id = message.photo[-1].file_id if message.photo else (message.document.file_id if message.document else "")
        order_id = state["order_id"]
        with conn() as c:
            o = c.execute("SELECT * FROM shop_orders WHERE order_id=?", (order_id,)).fetchone()
        if o:
            caption = f"✅ <b>{st('ORDER DELIVERED')}</b> 🌸\n{sep_pink()}\n🧾 {st('Order ID')}: <code>{order_id}</code>\n📦 আপনার প্রোডাক্ট ফাইলটি পাঠানো হলো।"
            try:
                if message.photo:
                    bot.send_photo(o["user_id"], file_id, caption=caption)
                else:
                    bot.send_document(o["user_id"], file_id, caption=caption)
                with conn() as c:
                    c.execute("UPDATE shop_orders SET order_status='DELIVERED', delivery_status='DELIVERED' WHERE order_id=?", (order_id,))
                send(chat_id, f"✅ Order <code>{order_id}</code> সফলভাবে ডেলিভারি করা হয়েছে!")
            except Exception as e:
                send(chat_id, f"⛔ ডেলিভারি ব্যর্থ: {e}")
        shop_states.pop(key, None)
        return

@bot.message_handler(content_types=["text"])
def handle_all_text(message):
    uid, chat_id = message.from_user.id, message.chat.id
    text = message.text.strip()
    key = _skey(chat_id, uid)
    all_nav_buttons = get_all_navigation_buttons()

    if text == "/start":
        cmd_start(message)
        return

    # 🌟 স্মার্ট স্টেট ব্রেকার (ইউজার অন্য বাটনে চাপলে স্বয়ংক্রিয়ভাবে আগের স্টেট ক্লিয়ার হবে)
    if text in all_nav_buttons:
        shop_states.pop(key, None)
        _gc_auto_refresh_threads[uid] = False

    # 1. State Input Handling
    state = shop_states.get(key)
    if state:
        if text == BACK() or text == L("⛔", "Cancel") or text == "/cancel":
            shop_states.pop(key, None)
            render_menu(chat_id, uid, "main")
            return
        if handle_state_flow(message, state):
            return

    # 2. Main Navigation
    if text == BACK():
        go_back(chat_id, uid)
        return

    # User Routes
    if text == L("🛍️", "Products"):
        render_menu(chat_id, uid, "products")
    elif text == L("💳", "Shop Balance"):
        render_menu(chat_id, uid, "balance")
    elif text == L("📋", "My Orders"):
        render_menu(chat_id, uid, "orders")
    elif text == L("🎁", "Offers & Bonus"):
        render_menu(chat_id, uid, "offers")
    elif text == L("🔑", "Get Code Center"):
        gc_open_menu(chat_id)

    # Balance Submenu
    elif text == L("💰", "Current Balance"):
        bal = user_balance(uid)
        send(chat_id, f"💰 <b>{st('WALLET BALANCE')}</b>\n{sep_pink()}\n"
                      f"🏦 {st('Available Balance')}: <b>{money(bal)}</b>\n"
                      f"✨ <i>যেকোনো পণ্য কেনার সময় ওয়ালেট থেকে ব্যালেন্স সরাসরি কাটা হবে।</i>")
    elif text == L("➕", "Add Balance"):
        p_info = sget("payment_info", "📱 bKash/Nagad/Rocket: 017XXXXXXXX\nটাকা পাঠিয়ে নিচে TrxID এবং টাকার পরিমাণ লিখে পাঠান।")
        shop_states[key] = {"step": "topup_amount", "data": {}}
        send(chat_id, f"💳 <b>{st('ADD BALANCE / DEPOSIT')}</b> 🌸\n{sep_pink()}\n<blockquote>{p_info}</blockquote>\n\n💵 <b>{st('কত টাকা পাঠিয়েছেন তা লিখুন (সংখ্যায়):')}</b>")
    elif text == L("📜", "Transaction History"):
        with conn() as c:
            rows = c.execute("SELECT * FROM shop_transactions WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        if not rows:
            send(chat_id, f"📭 <i>আপনার কোনো পূর্ববর্তী ট্রানজেকশন হিস্ট্রি পাওয়া যায়নি।</i>")
            return
        lines = [f"📜 <b>{st('TRANSACTION HISTORY')}</b> 🌸\n{sep()}"]
        for r in rows:
            lines.append(f"• {r['kind']} <b>{money(r['amount'])}</b> | {fmt_ts(r['created_at'])}\n  📝 {esc(r['note'])}")
        send(chat_id, "\n".join(lines))

    # Submenus Handling
    elif text in (L("🛍️", "Product"), L("🌸", "Product")):
        with conn() as c:
            rows = c.execute("SELECT DISTINCT category FROM shop_products WHERE is_deleted=0 AND enabled=1").fetchall()
        if not rows:
            send(chat_id, f"📭 <i>বর্তমানে কোনো ক্যাটাগরি তৈরি করা হয়নি।</i>")
            return
        kb = InlineKeyboardMarkup(row_width=2)
        for r in rows:
            kb.add(InlineKeyboardButton(f"📁 {r['category']}", callback_data=f"shop_list:cat:{r['category']}:0"))
        send(chat_id, f"🌸 <b>{st('SELECT A CATEGORY')}</b>\n{sep_pink()}", reply_markup=kb)

    elif text == L("📦", "All Products"):
        send_product_list(chat_id, uid, "all")
    elif text == L("🔎", "Search Product"):
        shop_states[key] = {"step": "usr_search"}
        send(chat_id, f"🔎 <b>{st('পণ্য খুঁজুন:')}</b>\n\n<i>প্রোডাক্টের নাম বা কোড লিখে পাঠান:</i>")

    # Orders Submenu
    elif text in (L("⏳", "Pending Orders"), L("🚚", "Processing Orders"), L("✅", "Confirmed Orders"), L("📦", "Delivered Orders"), L("❌", "Cancelled Orders")):
        st_map = {
            L("⏳", "Pending Orders"): "PENDING",
            L("🚚", "Processing Orders"): "PROCESSING",
            L("✅", "Confirmed Orders"): "CONFIRMED",
            L("📦", "Delivered Orders"): "DELIVERED",
            L("❌", "Cancelled Orders"): "CANCELLED",
        }
        send_user_orders(chat_id, uid, st_map[text])
    elif text == L("🔎", "Order Lookup"):
        shop_states[key] = {"step": "usr_order_lookup"}
        send(chat_id, f"🔎 <i>আপনার Order ID লিখে পাঠান (যেমন: PK123456):</i>")

    # Offers Submenu
    elif text == L("🔥", "Special Offers"):
        send_offers(chat_id, "OFFER", "SPECIAL OFFERS")
    elif text == L("🎟️", "Apply Promo Code"):
        shop_states[key] = {"step": "usr_coupon_input"}
        send(chat_id, f"🎟️ <i>আপনার প্রোমো কোডটি লিখে পাঠান:</i>")
    elif text == L("💎", "Active Discounts"):
        send_active_coupons(chat_id)
    elif text == L("🎁", "Bonus Items"):
        send_offers(chat_id, "BONUS", "BONUS REWARDS")

    # Clean Admin Panel Routing
    elif text == L("👑", "Shop Admin Panel") and is_admin(uid):
        render_menu(chat_id, uid, "admin")
    elif is_admin(uid):
        if text == L("➕", "Add Product"):
            shop_states[key] = {"step": "ap_name", "data": {}}
            send(chat_id, f"🌸 <b>{st('প্রোডাক্টের নাম লিখে পাঠান:')}</b>")
        elif text == L("📦", "Manage Products & Stock"):
            admin_show_products_list(chat_id)
        elif text == L("🧾", "Manage Orders"):
            admin_show_orders_overview(chat_id)
        elif text == L("🎟️", "Promo & Coupons"):
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("➕ Create Promo Coupon", callback_data="adm_act_addcoupon"),
                InlineKeyboardButton("🎁 Create Special Offer", callback_data="adm_act_addoffer"),
            )
            send(chat_id, f"🎟️ <b>{st('PROMOTIONS & DISCOUNTS')}</b> 🌸\n{sep()}", reply_markup=kb)
        elif text == L("📊", "Full Shop Reports"):
            admin_show_full_reports(chat_id)
        elif text == L("⚙️", "Shop Settings"):
            p_info = sget("payment_info", "Not Set")
            s_name = shop_name()
            curr = currency()
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("🏪 Change Shop Name", callback_data="adm_set_shopname"),
                InlineKeyboardButton("💳 Change Payment Info", callback_data="adm_set_payment"),
                InlineKeyboardButton("💱 Change Currency", callback_data="adm_set_curr"),
            )
            send(chat_id, f"⚙️ <b>{st('SHOP SETTINGS')}</b> 🌸\n{sep()}\n"
                          f"🏪 <b>Shop:</b> {s_name}\n💱 <b>Currency:</b> {curr}\n💳 <b>Payment:</b>\n<code>{p_info}</code>", reply_markup=kb)

def send_offers(chat_id, kind, title):
    with conn() as c:
        rows = c.execute("SELECT * FROM shop_offers WHERE enabled=1 AND kind=? ORDER BY id DESC LIMIT 5", (kind,)).fetchall()
    if not rows:
        send(chat_id, f"📭 <i>এই মুহূর্তে কোনো {title} নেই। শীঘ্রই আসছে!</i>")
        return
    lines = [f"🎁 <b>{st(title)}</b> 🌸\n{sep()}"]
    for o in rows:
        lines.append(f"\n🔥 <b>{esc(o['title'])}</b>\n📝 {esc(o['description'])}\n{sep_pink('─', 16)}")
    send(chat_id, "\n".join(lines))

def send_active_coupons(chat_id):
    with conn() as c:
        rows = c.execute("SELECT * FROM shop_coupons WHERE enabled=1 ORDER BY id DESC LIMIT 5").fetchall()
    if not rows:
        send(chat_id, f"📭 <i>বর্তমানে কোনো ডিসকাউন্ট কুপন সক্রিয় নেই।</i>")
        return
    lines = [f"💎 <b>{st('AVAILABLE PROMO COUPONS')}</b> 🌸\n{sep()}"]
    for cp in rows:
        val = f"{cp['discount_value']:.0f}%" if cp["discount_type"].upper() == "PERCENT" else money(cp["discount_value"])
        lines.append(f"🎟️ <code>{esc(cp['code'])}</code> — <b>{val} OFF</b>\n  🧮 {st('Min Order')}: {money(cp['min_order'])}")
    send(chat_id, "\n".join(lines))

def send_user_orders(chat_id, uid, status):
    with conn() as c:
        rows = c.execute("SELECT * FROM shop_orders WHERE user_id=? AND order_status=? ORDER BY id DESC LIMIT 10", (uid, status)).fetchall()
    if not rows:
        send(chat_id, f"📭 <i>{status} স্ট্যাটাসের কোনো অর্ডার নেই।</i>")
        return
    for o in rows:
        items = []
        with conn() as c2:
            itms = c2.execute("SELECT * FROM shop_order_items WHERE order_id=?", (o["order_id"],)).fetchall()
            for it in itms:
                items.append(f"• {it['product_name']} × {it['qty']}")
        
        send(chat_id,
             f"🧾 <b>{st('ORDER')} <code>{o['order_id']}</code></b> 🌸\n{sep_pink()}\n"
             f"<blockquote>"
             f"{chr(10).join(items)}\n\n"
             f"💰 <b>{st('Total Paid')}:</b> {money(o['total'])}\n"
             f"📌 <b>{st('Status')}:</b> <b>{o['order_status']}</b>\n"
             f"🕒 <b>{st('Date')}:</b> {fmt_ts(o['created_at'])}"
             f"</blockquote>")

# ═══════════════════════════════════════════════════════════════════════════
# 🔄 ইনপুট স্টেট মেশিন
# ═══════════════════════════════════════════════════════════════════════════
def handle_state_flow(message, state) -> bool:
    uid, chat_id = message.from_user.id, message.chat.id
    step = state.get("step")
    text = message.text.strip() if message.text else ""
    key = _skey(chat_id, uid)

    if step == "usr_search":
        shop_states.pop(key, None)
        send_product_list(chat_id, uid, "search", text)
        return True

    if step == "usr_order_lookup":
        shop_states.pop(key, None)
        with conn() as c:
            o = c.execute("SELECT * FROM shop_orders WHERE order_id=? AND user_id=?", (text.upper(), uid)).fetchone()
        if not o:
            send(chat_id, f"⛔ <i>অর্ডার পাওয়া যায়নি। সঠিক Order ID দিন।</i>")
            return True
        send(chat_id, f"🧾 <b>{st('ORDER')} <code>{o['order_id']}</code></b> 🌸\n{sep_pink()}\n"
                      f"💰 <b>{st('Total')}:</b> {money(o['total'])}\n"
                      f"📌 <b>{st('Status')}:</b> <b>{o['order_status']}</b>\n"
                      f"🕒 <b>{st('Date')}:</b> {fmt_ts(o['created_at'])}")
        return True

    # User Topup
    if step == "topup_amount":
        try:
            amt = float(text)
            if amt <= 0: raise ValueError
            state["amount"] = amt
            state["step"] = "topup_ref"
            send(chat_id, f"📝 <b>{st('পেমেন্টের Transaction ID (TrxID) বা প্রমাণ লিখে পাঠান:')}</b>")
        except Exception:
            send(chat_id, f"⛔ <i>সঠিক সংখ্যায় টাকার পরিমাণ লিখুন।</i>")
        return True

    if step == "topup_ref":
        amt = state["amount"]
        with conn() as c:
            cur = c.execute("INSERT INTO shop_topups (user_id, amount, reference) VALUES (?,?,?)", (uid, amt, text))
            tid = cur.lastrowid
        shop_states.pop(key, None)
        send(chat_id, f"✅ <b>{st('TOP-UP REQUEST SUBMITTED')}</b> 🌸\n{sep_pink()}\n"
                      f"🧾 <b>{st('Request ID')}:</b> <code>#{tid}</code>\n"
                      f"💰 <b>{st('Amount')}:</b> <b>{money(amt)}</b>\n"
                      f"📝 <b>{st('TrxID')}:</b> <code>{esc(text)}</code>\n\n"
                      f"<i>অ্যাডমিন ভেরিফাই করে কিছুক্ষণের মধ্যে আপনার ব্যালেন্স অ্যাড করে দেবে।</i>")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"shop_topup:approve:{tid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"shop_topup:reject:{tid}")
        )
        send(ADMIN_ID, f"🔔 <b>NEW TOP-UP REQUEST #{tid}</b>\n{sep()}\n"
                       f"👤 User ID: <code>{uid}</code>\n💰 Amount: {money(amt)}\n📝 TrxID: <code>{esc(text)}</code>",
             reply_markup=kb)
        return True

    # Admin Add Product Flow
    if step == "ap_name":
        state["data"]["name"] = text
        state["step"] = "ap_cat"
        send(chat_id, f"🗂️ <b>{st('ক্যাটাগরির নাম দিন (যেমন: Accounts, OTT, Gaming):')}</b>")
        return True

    if step == "ap_cat":
        state["data"]["cat"] = text
        state["step"] = "ap_price"
        send(chat_id, f"💰 <b>{st('প্রোডাক্টের মূল্য (Price) লিখুন:')}</b>")
        return True

    if step == "ap_price":
        try:
            state["data"]["price"] = float(text)
            state["step"] = "ap_stock"
            send(chat_id, f"📦 <b>{st('স্টক সংখ্যা (Stock Quantity) লিখুন:')}</b>")
        except Exception:
            send(chat_id, f"⛔ <i>সঠিক সংখ্যায় দাম লিখুন।</i>")
        return True

    if step == "ap_stock":
        try:
            state["data"]["stock"] = int(text)
            state["step"] = "ap_desc"
            send(chat_id, f"📝 <b>{st('প্রোডাক্টের ডেসক্রিপশন দিন (বা বাদ দিতে - লিখুন):')}</b>")
        except Exception:
            send(chat_id, f"⛔ <i>সঠিক পূর্ণসংখ্যা লিখুন।</i>")
        return True

    if step == "ap_desc":
        state["data"]["desc"] = "" if text == "-" else text
        state["step"] = "ap_photo"
        send(chat_id, f"🖼️ <b>{st('এখন প্রোডাক্টের লোগো বা ছবি পাঠান:')}</b>\n\n<i>(ছবি ছাড়া প্রোডাক্ট যোগ করতে <code>-</code> লিখে পাঠান)</i>")
        return True

    if step == "ap_photo":
        file_id = ""
        d = state["data"]
        with conn() as c:
            cnt = c.execute("SELECT COUNT(*) n FROM shop_products").fetchone()["n"]
            pid = f"PK{1001 + cnt}"
            c.execute("""
                INSERT INTO shop_products (product_id, name, category, description, price, stock, image_file_id)
                VALUES (?,?,?,?,?,?,?)
            """, (pid, d["name"], d["cat"], d["desc"], d["price"], d["stock"], file_id))
        shop_states.pop(key, None)
        send(chat_id, f"🌸 <b>{st('PRODUCT ADDED WITHOUT LOGO')}</b> 🌸\n{sep_pink()}\n"
                      f"🆔 <code>{pid}</code> | <b>{esc(d['name'])}</b>\n💰 {money(d['price'])} | 📦 {d['stock']} টি")
        render_menu(chat_id, uid, "admin")
        return True

    # Admin Custom Stock Edit
    if step == "adm_custom_stock":
        try:
            qty = int(text)
            pid = state["pid"]
            with conn() as c:
                c.execute("UPDATE shop_products SET stock=? WHERE product_id=?", (qty, pid))
            shop_states.pop(key, None)
            send(chat_id, f"✅ স্টক আপডেট হয়েছে! নতুন স্টক: <b>{qty} টি</b>")
            admin_product_control_card(chat_id, pid)
        except Exception:
            send(chat_id, "⛔ সঠিক সংখ্যা লিখুন:")
        return True

    # Admin Price Edit
    if step == "adm_edit_price":
        try:
            price = float(text)
            pid = state["pid"]
            with conn() as c:
                c.execute("UPDATE shop_products SET price=? WHERE product_id=?", (price, pid))
            shop_states.pop(key, None)
            send(chat_id, f"✅ মূল্য আপডেট হয়েছে! নতুন মূল্য: <b>{money(price)}</b>")
            admin_product_control_card(chat_id, pid)
        except Exception:
            send(chat_id, "⛔ সঠিক সংখ্যা লিখুন:")
        return True

    # Admin Deliver Order Text
    if step == "adm_deliver_text":
        order_id = state["order_id"]
        with conn() as c:
            o = c.execute("SELECT * FROM shop_orders WHERE order_id=?", (order_id,)).fetchone()
        if o:
            msg_user = f"✅ <b>{st('ORDER DELIVERED')}</b> 🌸\n{sep_pink()}\n🧾 {st('Order ID')}: <code>{order_id}</code>\n\n🔑 <b>ডেলিভারি ডাটা:</b>\n<blockquote>{esc(text)}</blockquote>"
            send(o["user_id"], msg_user)
            with conn() as c:
                c.execute("UPDATE shop_orders SET order_status='DELIVERED', delivery_status='DELIVERED' WHERE order_id=?", (order_id,))
            send(chat_id, f"✅ Order <code>{order_id}</code> সফলভাবে ডেলিভারি করা হয়েছে!")
        shop_states.pop(key, None)
        return True

    # Settings
    if step == "adm_set_shopname":
        sset("shop_name", text)
        shop_states.pop(key, None)
        send(chat_id, f"✅ শপের নাম পরিবর্তন করা হয়েছে: <b>{esc(text)}</b>")
        return True

    if step == "adm_set_payment":
        sset("payment_info", text)
        shop_states.pop(key, None)
        send(chat_id, "✅ পেমেন্ট ইনফো সফলভাবে সেভ করা হয়েছে।")
        return True

    if step == "adm_set_curr":
        sset("currency", text.upper())
        shop_states.pop(key, None)
        send(chat_id, f"✅ কারেন্সি পরিবর্তন করা হয়েছে: <b>{esc(text.upper())}</b>")
        return True

    # Coupons
    if step == "adm_coupon_code":
        state["code"] = text.upper().replace(" ", "")
        state["step"] = "adm_coupon_val"
        send(chat_id, f"💯 <b>{st('ডিসকাউন্ট শতকরা (Percentage) লিখুন (যেমন: 10):')}</b>")
        return True

    if step == "adm_coupon_val":
        try:
            val = float(text)
            with conn() as c:
                c.execute("INSERT INTO shop_coupons (code, discount_type, discount_value, min_order) VALUES (?, 'PERCENT', ?, 0)", (state["code"], val))
            shop_states.pop(key, None)
            send(chat_id, f"🎟️ <b>কুপন তৈরি সফল!</b>\nCode: <code>{state['code']}</code> | Discount: <b>{val}%</b>")
        except Exception:
            send(chat_id, "⛔ সঠিক সংখ্যা লিখুন:")
        return True

    # Offers
    if step == "adm_offer_title":
        state["title"] = text
        state["step"] = "adm_offer_desc"
        send(chat_id, f"📝 <b>{st('অফারের বিস্তারিত বিবরণ লিখুন:')}</b>")
        return True

    if step == "adm_offer_desc":
        with conn() as c:
            c.execute("INSERT INTO shop_offers (title, description, kind) VALUES (?,?,'OFFER')", (state["title"], text))
        shop_states.pop(key, None)
        send(chat_id, f"🎁 <b>অফার যোগ করা হয়েছে!</b>\nTitle: <b>{esc(state['title'])}</b>")
        return True

    # Get Code: Mail Input
    if step == "gc_mail_data":
        parts = text.split("|")
        if len(parts) < 4:
            send(chat_id, f"⛔ <b>ভুল ফরম্যাট!</b>\nসঠিক ফরম্যাটে পাঠান:\n<code>Email|Pass|RefreshToken|ClientID</code>")
            return True
        email_addr = parts[0].strip()
        _gc_sessions[uid] = {"email": email_addr, "r_token": parts[2].strip(), "c_id": parts[3].strip()}
        shop_states.pop(key, None)

        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("♻️ এখনই চেক করুন", callback_data="shop_gc:mail_check"),
            InlineKeyboardButton("🛑 বন্ধ করুন", callback_data="shop_gc:stop_auto")
        )
        msg = send(chat_id, build_mail_waiting_card(email_addr, 0), reply_markup=kb)
        if msg:
            _start_mail_auto_refresh(chat_id, msg.message_id, uid)
        return True

    # Get Code: 2FA Input
    if step == "gc_2fa_key":
        secret = text.replace(" ", "").upper()
        try:
            otp = pyotp.TOTP(secret).now()
            remaining = 30 - (int(time.time()) % 30)
            _gc_sessions[uid] = {"2fa_key": secret}
            shop_states.pop(key, None)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("♻️ Refresh 2FA", callback_data="shop_gc:2fa_refresh"))
            send(chat_id, build_2fa_card(otp, remaining), reply_markup=kb)
        except Exception:
            send(chat_id, f"⛔ <i>অবৈধ 2FA Secret Key! দয়া করে সঠিক Base-32 কি পাঠান।</i>")
        return True

    return False

# ═══════════════════════════════════════════════════════════════════════════
# 🔘 ইনলাইন বাটন ও কলব্যাক হ্যান্ডলার
# ═══════════════════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    uid = call.from_user.id
    data = call.data or ""
    chat_id = call.message.chat.id if call.message else uid

    if data == "shop_noop":
        bot.answer_callback_query(call.id)
        return

    # Category / List Pagination
    if data.startswith("shop_list:"):
        _, kind, rest = data.split(":", 2)
        arg, _sep, page = rest.rpartition(":")
        if not _sep or not page.isdigit():
            arg, page = rest, "0"
        page = int(page)
        bot.answer_callback_query(call.id)
        send_product_list(chat_id, uid, kind, arg, page)
        return

    # View Product with Logo
    if data.startswith("shop_view:"):
        pid = data.split(":", 1)[1]
        p = get_product(pid)
        bot.answer_callback_query(call.id)
        if not p:
            send(chat_id, f"⛔ <i>প্রোডাক্টটি পাওয়া যায়নি।</i>")
            return
        if p.get("image_file_id"):
            try:
                bot.send_photo(chat_id, p["image_file_id"], caption=product_card(p), reply_markup=product_inline(p))
                return
            except Exception:
                pass
        send(chat_id, product_card(p), reply_markup=product_inline(p))
        return

    # Quantity Selector for Instant Buy
    if data.startswith("shop_qty:"):
        _, mode, pid, qty_str = data.split(":", 3)
        qty = max(1, int(qty_str))
        p = get_product(pid)
        if not p:
            bot.answer_callback_query(call.id, "পণ্যটি আর অবশিষ্ট নেই!", show_alert=True)
            return
        stock = int(p["stock"])
        qty = min(qty, stock)
        bot.answer_callback_query(call.id)
        
        kb = InlineKeyboardMarkup(row_width=3)
        kb.row(
            InlineKeyboardButton("➖", callback_data=f"shop_qty:{mode}:{pid}:{max(1, qty-1)}"),
            InlineKeyboardButton(f"🌸 {qty} টি 🌸", callback_data="shop_noop"),
            InlineKeyboardButton("➕", callback_data=f"shop_qty:{mode}:{pid}:{min(stock, qty+1)}"),
        )
        kb.add(InlineKeyboardButton(f"⚡ {st('Confirm Quantity & Purchase')}", callback_data=f"shop_do:buy:{pid}:{qty}"))
        kb.add(InlineKeyboardButton(f"◀️ {st('Back')}", callback_data=f"shop_view:{pid}"))
        
        text = (
            f"🌸 <b>{esc(p['name'])}</b> 🌸\n{sep_pink()}\n"
            f"💰 <b>{st('Unit Price')}:</b> {money(p['price'])}\n"
            f"🔢 <b>{st('Quantity')}:</b> <b>{qty} টি</b>\n"
            f"🧮 <b>{st('Total Price')}:</b> <b>{money(float(p['price']) * qty)}</b>"
        )
        try:
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=kb)
        except Exception:
            send(chat_id, text, reply_markup=kb)
        return

    # Direct Buy / Instant Invoice
    if data.startswith("shop_do:"):
        _, mode, pid, qty_str = data.split(":", 3)
        qty = int(qty_str)
        p = get_product(pid)
        bot.answer_callback_query(call.id)
        if p:
            send_instant_buy_invoice(chat_id, uid, p, qty)
        return

    # Confirm Order
    if data.startswith("shop_confirm:"):
        token = data.split(":", 1)[1]
        key = _skey(chat_id, uid)
        state = shop_states.pop(key, None)
        if not state or state.get("data", {}).get("token") != token:
            bot.answer_callback_query(call.id, "সেশনের মেয়াদ শেষ! আবার চেষ্টা করুন।", show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "অর্ডার প্রসেস হচ্ছে...")
        order_id, _ = place_order(call.from_user, chat_id, state["data"]["payload"])
        if not order_id:
            send(chat_id, "⛔ অর্ডার সম্পন্ন হতে ব্যর্থ হয়েছে।")
            return

        msg = (
            f"🎉 <b>{st('ORDER PLACED SUCCESSFULLY')}</b> 🌸\n{sep()}\n\n"
            f"<blockquote>"
            f"🧾 <b>{st('Order ID')}:</b> <code>{order_id}</code>\n"
            f"💰 <b>{st('Amount Paid')}:</b> <b>{money(state['data']['payload']['total'])}</b>\n"
            f"🏦 <b>{st('Remaining Balance')}:</b> <b>{money(user_balance(uid))}</b>\n"
            f"📌 <b>{st('Status')}:</b> <b>প্রসেসিং</b>"
            f"</blockquote>\n\n"
            f"⏳ <i>আপনার অর্ডারটি প্রক্রিয়াধীন রয়েছে। খুব শীঘ্রই অ্যাডমিন ডেলিভারি সম্পন্ন করবেন।</i>"
        )
        send(chat_id, msg)
        render_menu(chat_id, uid, "main")
        return

    if data == "shop_confirm_cancel":
        shop_states.pop(_skey(chat_id, uid), None)
        bot.answer_callback_query(call.id, "অর্ডার বাতিল করা হয়েছে।")
        send(chat_id, f"❌ <i>চেকআউট বাতিল করা হয়েছে।</i>")
        return

    # ═══════════════════════════════════════════════════════════════════════
    # 👑 ADMIN SMART CONTROLS (CALLBACKS)
    # ═══════════════════════════════════════════════════════════════════════
    if data.startswith("adm_pview:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        admin_product_control_card(chat_id, pid)
        return

    if data == "adm_back_prodlist" and is_admin(uid):
        bot.answer_callback_query(call.id)
        admin_show_products_list(chat_id)
        return

    if data.startswith("adm_stkadd:") and is_admin(uid):
        _, pid, add_str = data.split(":", 2)
        add_cnt = int(add_str)
        with conn() as c:
            c.execute("UPDATE shop_products SET stock=stock+? WHERE product_id=?", (add_cnt, pid))
        bot.answer_callback_query(call.id, f"+{add_cnt} স্টক যোগ করা হয়েছে!")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        admin_product_control_card(chat_id, pid)
        return

    if data.startswith("adm_stkzero:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        with conn() as c:
            c.execute("UPDATE shop_products SET stock=0 WHERE product_id=?", (pid,))
        bot.answer_callback_query(call.id, "❌ স্টক ০ (Stock Out) করা হয়েছে!")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        admin_product_control_card(chat_id, pid)
        return

    if data.startswith("adm_toggle:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        p = get_product(pid, admin=True)
        if p:
            new_st = 0 if p["enabled"] else 1
            with conn() as c:
                c.execute("UPDATE shop_products SET enabled=? WHERE product_id=?", (new_st, pid))
            bot.answer_callback_query(call.id, f"{'🟢 Enabled' if new_st else '🔴 Disabled'}")
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            admin_product_control_card(chat_id, pid)
        return

    if data.startswith("adm_stkcustom:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_custom_stock", "pid": pid}
        send(chat_id, f"🔢 <b>{pid}</b> এর জন্য নতুন স্টক সংখ্যা লিখে পাঠান:")
        return

    if data.startswith("adm_editprice:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_edit_price", "pid": pid}
        send(chat_id, f"💰 <b>{pid}</b> এর জন্য নতুন মূল্য লিখে পাঠান:")
        return

    if data.startswith("adm_setphoto:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_wait_photo", "pid": pid}
        send(chat_id, f"🖼️ <b>{pid}</b> এর জন্য নতুন ছবি/লোগো ফটো আকারে পাঠান:")
        return

    if data.startswith("adm_delprod:") and is_admin(uid):
        pid = data.split(":", 1)[1]
        with conn() as c:
            c.execute("UPDATE shop_products SET is_deleted=1, enabled=0 WHERE product_id=?", (pid,))
        bot.answer_callback_query(call.id, "🗑️ প্রোডাক্ট মুছে ফেলা হয়েছে!")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        admin_show_products_list(chat_id)
        return

    # Admin Order Management Callbacks
    if data.startswith("adm_ordlist:") and is_admin(uid):
        status = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        with conn() as c:
            rows = c.execute("SELECT * FROM shop_orders WHERE order_status=? ORDER BY id DESC LIMIT 8", (status,)).fetchall()
        if not rows:
            send(chat_id, f"📭 <i>{status} স্ট্যাটাসের কোনো অর্ডার নেই।</i>")
            return
        send(chat_id, f"🧾 <b>{status} ORDERS LIST</b>\n{sep()}")
        for o in rows:
            kb = InlineKeyboardMarkup(row_width=2)
            if status != "DELIVERED" and status != "CANCELLED":
                kb.row(
                    InlineKeyboardButton("📤 Deliver Text", callback_data=f"adm_dlvtxt:{o['order_id']}"),
                    InlineKeyboardButton("📁 Deliver File", callback_data=f"adm_dlvfil:{o['order_id']}"),
                )
                kb.row(InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"adm_ordcan:{o['order_id']}"))
            send(chat_id,
                 f"🧾 <b>Order:</b> <code>{o['order_id']}</code>\n"
                 f"👤 <b>User:</b> <code>{o['user_id']}</code>\n"
                 f"💰 <b>Total:</b> {money(o['total'])}\n"
                 f"📌 <b>Status:</b> <b>{o['order_status']}</b>\n"
                 f"🕒 <b>Date:</b> {fmt_ts(o['created_at'])}",
                 reply_markup=kb if len(kb.keyboard) > 0 else None)
        return

    if data.startswith("adm_dlvtxt:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_deliver_text", "order_id": order_id}
        send(chat_id, f"📤 <code>{order_id}</code> এর জন্য ডেলিভারি টেক্সট বা একাউন্ট ডাটা পাঠান:")
        return

    if data.startswith("adm_dlvfil:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_deliver_file", "order_id": order_id}
        send(chat_id, f"📁 <code>{order_id}</code> এর জন্য ডেলিভারি ফাইল বা ফটো পাঠান:")
        return

    if data.startswith("adm_ordcan:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        with conn() as c:
            o = c.execute("SELECT * FROM shop_orders WHERE order_id=?", (order_id,)).fetchone()
            if o and o["order_status"] not in ("CANCELLED", "DELIVERED"):
                adjust_balance(o["user_id"], float(o["total"]), uid, f"Refund for {order_id}")
                c.execute("UPDATE shop_orders SET order_status='CANCELLED' WHERE order_id=?", (order_id,))
                bot.answer_callback_query(call.id, "Order Cancelled & Refunded!")
                send(o["user_id"], f"❌ <b>আপনার অর্ডার {order_id} বাতিল করা হয়েছে এবং {money(o['total'])} ওয়ালেটে রিফান্ড করা হয়েছে।</b>")
                send(chat_id, f"✅ Order <code>{order_id}</code> বাতিল ও রিফান্ড সম্পন্ন!")
            else:
                bot.answer_callback_query(call.id, "ইতিমধ্যে প্রসেস করা হয়েছে।")
        return

    # Admin Settings Callbacks
    if data == "adm_set_shopname" and is_admin(uid):
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_set_shopname"}
        send(chat_id, "🏪 নতুন শপের নাম লিখে পাঠান:")
        return

    if data == "adm_set_payment" and is_admin(uid):
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_set_payment"}
        send(chat_id, "💳 নতুন পেমেন্ট নম্বর ও নির্দেশাবলী লিখে পাঠান:")
        return

    if data == "adm_set_curr" and is_admin(uid):
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_set_curr"}
        send(chat_id, "💱 কারেন্সি কোড পাঠান (যেমন: BDT, USD, USDT):")
        return

    if data == "adm_act_addcoupon" and is_admin(uid):
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_coupon_code"}
        send(chat_id, "🎟️ কুপন কোড নাম লিখুন (যেমন: PINK20):")
        return

    if data == "adm_act_addoffer" and is_admin(uid):
        bot.answer_callback_query(call.id)
        shop_states[_skey(chat_id, uid)] = {"step": "adm_offer_title"}
        send(chat_id, "🎁 অফারের শিরোনাম লিখে পাঠান:")
        return

    # Get Code Live Handlers
    if data.startswith("shop_gc:"):
        act = data.split(":", 1)[1]
        if act == "mail":
            shop_states[_skey(chat_id, uid)] = {"step": "gc_mail_data"}
            bot.answer_callback_query(call.id)
            send(chat_id,
                 f"📧 <b>{st('MAIL TOKEN INPUT')}</b> 🌸\n{sep_pink()}\n"
                 f"📥 <i>আপনার মেইল ডাটা এই ফরম্যাটে পাঠান:</i>\n\n"
                 f"<code>Email|Pass|RefreshToken|ClientID</code>")
        elif act == "2fa":
            shop_states[_skey(chat_id, uid)] = {"step": "gc_2fa_key"}
            bot.answer_callback_query(call.id)
            send(chat_id,
                 f"🛡️ <b>{st('2FA SECRET KEY')}</b> 🌸\n{sep_pink()}\n"
                 f"🔐 <i>আপনার 2FA Base-32 Secret Key লিখে পাঠান:</i>\n"
                 f"<i>উদাহরণ: <code>JBSWY3DPEHPK3PXP</code></i>")
        elif act == "mail_check":
            ses = _gc_sessions.get(uid)
            if not ses:
                bot.answer_callback_query(call.id, "মেইল ডাটা পুনরায় পাঠান।", show_alert=True)
                return
            bot.answer_callback_query(call.id, "ইনবক্স চেক করা হচ্ছে...")
            ok, res = _gc_hotmail_otp(ses["r_token"], ses["c_id"])
            if ok:
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("♻️ আবার চেক করুন", callback_data="shop_gc:mail_check"),
                    InlineKeyboardButton("🛑 বন্ধ করুন", callback_data="shop_gc:stop_auto")
                )
                try:
                    bot.edit_message_text(
                        build_mail_success_card(ses["email"], res),
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        reply_markup=kb
                    )
                except Exception:
                    pass
            else:
                bot.answer_callback_query(call.id, f"⚠️ {res}", show_alert=True)
        elif act == "stop_auto":
            _gc_auto_refresh_threads[uid] = False
            bot.answer_callback_query(call.id, "অটো-রিফ্রেশ বন্ধ করা হয়েছে।")
        elif act == "2fa_refresh":
            ses = _gc_sessions.get(uid)
            if not ses or "2fa_key" not in ses:
                bot.answer_callback_query(call.id, "2FA কি পাওয়া যায়নি! পুনরায় কি দিন।", show_alert=True)
                return
            otp = pyotp.TOTP(ses["2fa_key"]).now()
            remaining = 30 - (int(time.time()) % 30)
            bot.answer_callback_query(call.id, "2FA রিফ্রেশ সফল!")
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("♻️ Refresh 2FA", callback_data="shop_gc:2fa_refresh"))
            try:
                bot.edit_message_text(
                    build_2fa_card(otp, remaining),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=kb
                )
            except Exception:
                pass
        return

    # Admin Topup Actions
    if data.startswith("shop_topup:") and is_admin(uid):
        _, act, tid_str = data.split(":", 2)
        tid = int(tid_str)
        with conn() as c:
            r = c.execute("SELECT * FROM shop_topups WHERE id=?", (tid,)).fetchone()
        if not r or r["status"] != "PENDING":
            bot.answer_callback_query(call.id, "Already processed.", show_alert=True)
            return
        if act == "approve":
            adjust_balance(r["user_id"], float(r["amount"]), uid, f"Topup #{tid}")
            with conn() as c:
                c.execute("UPDATE shop_topups SET status='APPROVED' WHERE id=?", (tid,))
            bot.answer_callback_query(call.id, "Approved!")
            send(r["user_id"], f"✅ <b>{st('TOP-UP APPROVED')}</b> 🌸\n💰 <b>{money(r['amount'])}</b> আপনার ওয়ালেটে যোগ হয়েছে।")
        else:
            with conn() as c:
                c.execute("UPDATE shop_topups SET status='REJECTED' WHERE id=?", (tid,))
            bot.answer_callback_query(call.id, "Rejected!")
            send(r["user_id"], f"❌ <b>{st('TOP-UP REJECTED')}</b>\n💰 {money(r['amount'])} এর রিকোয়েস্টটি বাতিল করা হয়েছে।")
        return

# ═══════════════════════════════════════════════════════════════════════════
# 🌐 RENDER 24/7 HEALTH SERVER
# ═══════════════════════════════════════════════════════════════════════════
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b'{"status":"ok","service":"pink-shop-bot-50k-ready"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"🌸 Health Server Port Active: {port}")
    except Exception as exc:
        logger.warning(f"Port bind notice: {exc}")

# ═══════════════════════════════════════════════════════════════════════════
# 🏁 বট স্টার্ট (ক্র্যাশ প্রতিরোধে Auto-Reconnect লুপ)
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    start_health_server()
    print("🌸 Luxury Pink Shop Bot (50K Load-Ready) is running successfully...")
    try:
        bot.remove_webhook()
    except Exception:
        pass

    # ৫০ হাজার ইউজারের বড় ট্রাফিক সামলাতে Auto-Reconnect Polling Engine
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            logger.error(f"Polling connection drop recovered: {e}")
            time.sleep(3)