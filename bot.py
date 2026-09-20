"""
🌸 PINK AESTHETIC TELEGRAM DIGITAL SHOP BOT 🌸
Complete Standalone Shop & Admin System with 2FA/Mail Code & Render 24/7 Hosting.
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
# 🌸 কনফিগারেশন (ENVIRONMENT VARIABLES)
# ═══════════════════════════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "123456789").strip()
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else 123456789

DATA_DIR = os.getenv("DATA_DIR", "./data").strip() or "./data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "pink_shop.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pink_shop")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

shop_states = {}
shop_nav = {}
_checkout_locks = set()
_lock = threading.Lock()
_gc_sessions = {}
SELECT_PAGE_SIZE = 8

# ═══════════════════════════════════════════════════════════════════════════
# 🎀 পিংক স্টাইলিং ও ফরম্যাটিং হেল্পার
# ═══════════════════════════════════════════════════════════════════════════
def stylish(text: str) -> str:
    """Mathematical monospace / aesthetic typewriter font."""
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

def sep(c="━", n=26) -> str:
    return f"🌸 {c * n} 🌸"

def sep_pink(c="─", n=24) -> str:
    return f"🎀 {c * n} 🎀"

def _skey(chat_id, user_id) -> str:
    return f"{chat_id}:{user_id}"

def now_ts() -> int:
    return int(time.time())

def fmt_ts(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d-%m-%Y %H:%M")
    except Exception:
        return "N/A"

def money(v) -> str:
    try:
        return f"{float(v or 0):.2f} {currency()}"
    except Exception:
        return f"0.00 {currency()}"

# ═══════════════════════════════════════════════════════════════════════════
# 🗄️ ডাটাবেস হ্যান্ডলিং
# ═══════════════════════════════════════════════════════════════════════════
class DBConnection:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.path, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
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
    c = sqlite3.connect(DB_PATH, timeout=30.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
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
            delivery_type TEXT DEFAULT 'TEXT',
            enabled INTEGER DEFAULT 1,
            featured INTEGER DEFAULT 0,
            popular INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            sold INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            qty INTEGER DEFAULT 1,
            added_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(user_id, product_id)
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
            is_resend INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_auto_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            content TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            order_id TEXT DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS shop_stock_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            admin_id INTEGER,
            change INTEGER DEFAULT 0,
            reason TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT DEFAULT '',
            target TEXT DEFAULT '',
            detail TEXT DEFAULT '',
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
        """)
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))

init_db()

# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ শপ সেটিংস ও হেল্পার
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
    return sget("shop_name", "Pink Velvet Shop 🌸")

def currency() -> str:
    return sget("currency", "BDT")

def min_order() -> float:
    try:
        return float(sget("min_order", "0") or 0)
    except Exception:
        return 0.0

def maintenance_on() -> bool:
    return sget("maintenance", "0") == "1"

def low_stock_threshold() -> int:
    try:
        return int(sget("low_stock", "5") or 5)
    except Exception:
        return 5

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
            return False, f"⛔ {st('Insufficient user balance.')}"
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
        return False, f"⛔ {st('Balance update failed.')}"
    finally:
        c.close()
    
    log_activity(admin_id, "BALANCE", str(user_id), f"{delta:+.2f} {reason}")
    try:
        send(user_id, f"💖 <b>{st('WALLET UPDATED')}</b>\n{sep_pink()}\n"
                      f"{'➕' if delta > 0 else '➖'} <b>{money(abs(delta))}</b>\n"
                      f"🏦 {st('New balance')}: <b>{money(user_balance(user_id))}</b>")
    except Exception:
        pass
    return True, "ok"

def log_activity(admin_id, action, target="", detail=""):
    try:
        with conn() as c:
            c.execute("INSERT INTO shop_activity_logs (admin_id, action, target, detail) VALUES (?,?,?,?)",
                      (admin_id, action, str(target), str(detail)[:400]))
    except Exception:
        pass

def send(chat_id, text, **kw):
    try:
        return bot.send_message(chat_id, text, **kw)
    except Exception as exc:
        logger.warning(f"Send failed chat={chat_id}: {exc}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# 🌸 কীবোর্ড ও মেনুসমূহ (PINK UI)
# ═══════════════════════════════════════════════════════════════════════════
def L(emoji, text) -> str:
    return f"{emoji} {st(text)}"

BACK = lambda: L("◀️", "Back")

USER_MENUS = {
    "main": lambda admin: [
        [L("🛍️", "Products"), L("🛒", "My Cart")],
        [L("📋", "My Orders"), L("💳", "Shop Balance")],
        [L("🎁", "Offers & Bonus"), L("🔑", "Get Code Center")],
        [L("👤", "Profile"), L("ℹ️", "Support & FAQ")],
    ] + ([[L("👑", "Shop Admin Panel")]] if admin else []),

    "products": lambda admin: [
        [L("🌸", "Category List")],
        [L("📦", "All Products"), L("✨", "New Products")],
        [L("🔥", "Popular Products"), L("⭐", "Featured Products")],
        [L("🔎", "Search Product")],
        [BACK()],
    ],

    "orders": lambda admin: [
        [L("⏳", "Pending Orders"), L("🚚", "Processing Orders")],
        [L("✅", "Confirmed Orders"), L("📦", "Delivered Orders")],
        [L("❌", "Cancelled Orders"), L("🔎", "Order Lookup")],
        [BACK()],
    ],

    "balance": lambda admin: [
        [L("💰", "Current Balance"), L("➕", "Add Balance")],
        [L("📜", "Transaction History")],
        [BACK()],
    ],

    "offers": lambda admin: [
        [L("🔥", "Special Offers"), L("🎟️", "Apply Coupon")],
        [L("💎", "Active Discounts"), L("🎁", "Bonus Items")],
        [BACK()],
    ],
}

ADMIN_MENUS = {
    "admin": lambda admin: [
        [L("📦", "Product Management"), L("🗃️", "Stock Management")],
        [L("🧾", "Order Management"), L("🚚", "Delivery Management")],
        [L("🎟️", "Coupons & Offers"), L("👥", "Users & Balance")],
        [L("📊", "Reports"), L("⚙️", "Shop Settings")],
        [L("🗂️", "Shop Logs")],
        [BACK()],
    ],
    "admin_products": lambda admin: [
        [L("➕", "Add Product"), L("✏️", "Edit Product")],
        [L("🗑️", "Delete Product"), L("📃", "Product List")],
        [L("🔁", "Toggle Enable"), L("⭐", "Toggle Featured")],
        [L("🔥", "Toggle Popular"), L("🖼️", "Set Photo")],
        [BACK()],
    ],
    "admin_stock": lambda admin: [
        [L("➕", "Add Stock"), L("🔢", "Set Stock")],
        [L("⚠️", "Low Stock Report"), L("🤖", "Auto Delivery Items")],
        [L("📜", "Stock Logs")],
        [BACK()],
    ],
    "admin_orders": lambda admin: [
        [L("⏳", "Pending Orders"), L("✅", "Confirmed Orders")],
        [L("🚚", "Processing Orders"), L("📤", "Delivered Orders")],
        [L("❌", "Cancelled Orders"), L("🔎", "Find Order")],
        [BACK()],
    ],
    "admin_delivery": lambda admin: [
        [L("📤", "Deliver Order"), L("♻️", "Resend Delivery")],
        [L("🤖", "Auto Deliver"), L("📜", "Delivery Logs")],
        [BACK()],
    ],
    "admin_promos": lambda admin: [
        [L("➕", "Add Coupon"), L("📃", "Coupon List")],
        [L("🗑️", "Delete Coupon"), L("🎁", "Add Offer")],
        [L("📃", "Offer List"), L("🗑️", "Delete Offer")],
        [BACK()],
    ],
    "admin_users": lambda admin: [
        [L("➕", "Add User Balance"), L("➖", "Remove User Balance")],
        [L("💳", "Top-up Requests"), L("🔎", "User Lookup")],
        [L("📢", "Send Notice")],
        [BACK()],
    ],
    "admin_reports": lambda admin: [
        [L("📈", "Sales Report"), L("🏆", "Top Products")],
        [L("💰", "Revenue Summary"), L("📊", "Order Stats")],
        [BACK()],
    ],
    "admin_settings": lambda admin: [
        [L("🏪", "Shop Name"), L("💱", "Currency")],
        [L("🧮", "Minimum Order"), L("💳", "Payment Info")],
        [L("🛠️", "Maintenance Mode"), L("⚠️", "Low Stock Limit")],
        [L("❓", "FAQ Text"), L("💬", "Support Contact")],
        [BACK()],
    ],
    "admin_logs": lambda admin: [
        [L("🗂️", "Activity Logs"), L("📜", "Stock Log List")],
        [L("💸", "Shop Transactions")],
        [BACK()],
    ],
}

def keyboard_for(menu: str, user_id: int):
    adm = is_admin(user_id)
    spec = USER_MENUS.get(menu) or ADMIN_MENUS.get(menu)
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

    title = f"🌸 <b>{st(shop_name().upper())}</b>\n{sep()}\n{st('Select an option below:')}"
    if menu == "admin":
        title = f"👑 <b>{st('SHOP ADMIN PANEL')}</b>\n{sep()}\n{_admin_overview()}"
    elif menu.startswith("admin_"):
        title = f"👑 <b>{st(menu.replace('admin_', '').upper() + ' CONTROL')}</b>\n{sep()}"
    elif menu != "main":
        title = f"🌸 <b>{st(menu.upper())}</b>\n{sep()}"

    body = text or title
    send(chat_id, body, reply_markup=keyboard_for(menu, user_id))

def _admin_overview() -> str:
    try:
        with conn() as c:
            prod = c.execute("SELECT COUNT(*) n FROM shop_products WHERE is_deleted=0").fetchone()["n"]
            pend = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE order_status='PENDING'").fetchone()["n"]
            rev = c.execute("SELECT COALESCE(SUM(total),0) t FROM shop_orders WHERE order_status IN ('CONFIRMED','PROCESSING','DELIVERED')").fetchone()["t"]
            low = c.execute("SELECT COUNT(*) n FROM shop_products WHERE is_deleted=0 AND stock<=?", (low_stock_threshold(),)).fetchone()["n"]
        return (
            f"<blockquote>"
            f"📦 {st('Products')}: <b>{prod}</b>\n"
            f"⏳ {st('Pending Orders')}: <b>{pend}</b>\n"
            f"💰 {st('Revenue')}: <b>{money(rev)}</b>\n"
            f"⚠️ {st('Low Stock')}: <b>{low}</b>"
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
# 🛍️ প্রোডাক্ট ও কার্ট লজিক
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
    if kind == "popular":
        base += " AND popular=1"
    elif kind == "featured":
        base += " AND featured=1"
    elif kind == "cat":
        base += " AND LOWER(category)=LOWER(?)"
        params.append(arg)
    elif kind == "search":
        like = f"%{arg.lower()}%"
        base += " AND (LOWER(name) LIKE ? OR LOWER(product_id) LIKE ? OR LOWER(category) LIKE ?)"
        params += [like, like, like]
    order = " ORDER BY created_at DESC" if kind == "new" else " ORDER BY sold DESC, id DESC"
    base += order + " LIMIT ? OFFSET ?"
    params += [limit + 1, offset]
    with conn() as c:
        rows = [dict(r) for r in c.execute(base, params).fetchall()]
    has_more = len(rows) > limit
    return rows[:limit], has_more

def product_card(p) -> str:
    stock_line = f"❌ {st('Out of Stock')}" if int(p["stock"]) <= 0 else f"<b>{int(p['stock'])}</b>"
    flags = []
    if p.get("featured"):
        flags.append("⭐ Featured")
    if p.get("popular"):
        flags.append("🔥 Popular")
    return (
        f"🌸 <b>{esc(p['name'])}</b>\n{sep_pink()}\n"
        f"<blockquote>"
        f"🆔 {st('Product ID')}: <code>{esc(p['product_id'])}</code>\n"
        f"🗂️ {st('Category')}: {esc(p['category'])}\n"
        f"💰 {st('Price')}: <b>{money(p['price'])}</b>\n"
        f"📦 {st('Stock')}: {stock_line}\n"
        f"🚚 {st('Delivery')}: <code>{esc(p['delivery_type'])}</code>"
        f"</blockquote>\n"
        f"{' | '.join(flags)}\n\n"
        f"📝 <b>{st('Description')}:</b>\n<blockquote>{esc(p.get('description') or 'N/A')}</blockquote>"
    )

def product_inline(p):
    kb = InlineKeyboardMarkup(row_width=2)
    if int(p["stock"]) > 0 and p["enabled"] and not p["is_deleted"]:
        kb.add(
            InlineKeyboardButton(f"🛒 {st('Add to Cart')}", callback_data=f"shop_qty:cart:{p['product_id']}:1"),
            InlineKeyboardButton(f"⚡ {st('Buy Now')}", callback_data=f"shop_qty:buy:{p['product_id']}:1"),
        )
    else:
        kb.add(InlineKeyboardButton(f"❌ {st('Out of Stock')}", callback_data="shop_noop"))
    kb.add(InlineKeyboardButton(f"◀️ {st('Back')}", callback_data="shop_list:all::0"))
    return kb

def send_product_list(chat_id, user_id, kind, arg="", page=0):
    rows, has_more = list_products(kind, arg, SELECT_PAGE_SIZE, page * SELECT_PAGE_SIZE)
    if not rows:
        send(chat_id, f"📭 {st('No products found.')}")
        return
    lines = [f"🌸 <b>{st('PRODUCT SHOWCASE')} ({kind.upper()})</b>\n{sep()}"]
    kb = InlineKeyboardMarkup(row_width=1)
    for p in rows:
        stock = "❌ Out of Stock" if int(p["stock"]) <= 0 else f"📦 {int(p['stock'])}"
        tags = ("⭐" if p["featured"] else "") + ("🔥" if p["popular"] else "")
        lines.append(f"• <b>{esc(p['name'])}</b> {tags}\n  💰 {money(p['price'])} | {stock} | 🆔 <code>{p['product_id']}</code>")
        kb.add(InlineKeyboardButton(f"🛍️ {p['name'][:24]} — {money(p['price'])}", callback_data=f"shop_view:{p['product_id']}"))
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"shop_list:{kind}:{arg}:{page-1}"))
    if has_more:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"shop_list:{kind}:{arg}:{page+1}"))
    if nav:
        kb.row(*nav)
    send(chat_id, "\n".join(lines), reply_markup=kb)

def cart_rows(user_id):
    with conn() as c:
        rows = c.execute("""
            SELECT ci.product_id, ci.qty, p.name, p.price, p.stock, p.enabled, p.is_deleted, p.delivery_type
            FROM shop_cart_items ci LEFT JOIN shop_products p ON p.product_id=ci.product_id
            WHERE ci.user_id=? ORDER BY ci.id
        """, (user_id,)).fetchall()
    return [dict(r) for r in rows]

def validate_coupon(code, user_id, subtotal):
    code = str(code or "").strip().upper()
    if not code:
        return False, st("No coupon applied."), 0.0
    with conn() as c:
        row = c.execute("SELECT * FROM shop_coupons WHERE UPPER(code)=?", (code,)).fetchone()
        if not row:
            return False, st("Invalid coupon code."), 0.0
        cp = dict(row)
        used_by_user = c.execute("SELECT COUNT(*) n FROM shop_coupon_usage WHERE UPPER(code)=? AND user_id=?", (code, user_id)).fetchone()["n"]
    if not cp["enabled"]:
        return False, st("This coupon is disabled."), 0.0
    ts = now_ts()
    if cp["start_at"] and ts < int(cp["start_at"]):
        return False, st("Coupon not active yet."), 0.0
    if cp["expiry_at"] and ts > int(cp["expiry_at"]):
        return False, st("Coupon expired."), 0.0
    if cp["min_order"] and float(subtotal) < float(cp["min_order"]):
        return False, f"{st('Minimum order')}: {money(cp['min_order'])}", 0.0
    if cp["max_usage"] and int(cp["used_count"]) >= int(cp["max_usage"]):
        return False, st("Coupon usage limit finished."), 0.0
    if cp["per_user_limit"] and used_by_user >= int(cp["per_user_limit"]):
        return False, st("You have already used this coupon."), 0.0
    if cp["discount_type"].upper() == "PERCENT":
        disc = float(subtotal) * float(cp["discount_value"]) / 100.0
    else:
        disc = float(cp["discount_value"])
    return True, f"{st('Coupon applied')}: −{money(disc)}", round(min(disc, float(subtotal)), 2)

def send_cart(chat_id, user_id):
    rows = cart_rows(user_id)
    if not rows:
        send(chat_id, f"🛒 {st('Your cart is empty.')}")
        return
    lines = [f"🛒 <b>{st('MY SHOPPING CART')}</b>\n{sep()}"]
    kb = InlineKeyboardMarkup(row_width=3)
    total = 0.0
    for r in rows:
        if not r["name"] or r["is_deleted"]:
            continue
        sub = float(r["price"]) * int(r["qty"])
        total += sub
        lines.append(f"• <b>{esc(r['name'])}</b>\n  💰 {money(r['price'])} × {int(r['qty'])} = <b>{money(sub)}</b>")
        kb.row(
            InlineKeyboardButton("➖", callback_data=f"shop_cart:dec:{r['product_id']}"),
            InlineKeyboardButton(f"{r['name'][:12]} ({int(r['qty'])})", callback_data="shop_noop"),
            InlineKeyboardButton("➕", callback_data=f"shop_cart:inc:{r['product_id']}"),
        )
        kb.add(InlineKeyboardButton(f"🗑️ {st('Remove')} {r['name'][:14]}", callback_data=f"shop_cart:del:{r['product_id']}"))

    code = sget_cart_coupon(user_id)
    disc = 0.0
    if code:
        ok, _, disc = validate_coupon(code, user_id, total)
        if not ok:
            disc = 0.0

    lines.append(f"\n{sep_pink()}\n💵 {st('Subtotal')}: <b>{money(total)}</b>")
    if code:
        lines.append(f"🎟️ {st('Coupon')} (<code>{esc(code)}</code>): −<b>{money(disc)}</b>")
        lines.append(f"💰 {st('Payable')}: <b>{money(max(0.0, total - disc))}</b>")
    kb.add(InlineKeyboardButton(f"💳 {st('Checkout Now')}", callback_data="shop_cart:checkout"))
    kb.add(InlineKeyboardButton(f"🗑️ {st('Clear Cart')}", callback_data="shop_cart:clear"))
    send(chat_id, "\n".join(lines), reply_markup=kb)

def sget_cart_coupon(user_id):
    with conn() as c:
        row = c.execute("SELECT code FROM shop_cart_coupon WHERE user_id=?", (user_id,)).fetchone()
        return row["code"] if row else ""

def place_order(user, chat_id, payload):
    user_id = user.id
    with _lock:
        if user_id in _checkout_locks:
            return None, st("Previous checkout is still processing.")
        _checkout_locks.add(user_id)
    c = None
    try:
        order_id = "PK" + datetime.now().strftime("%y%m%d") + secrets.token_hex(2).upper()
        total = float(payload["total"])
        c = raw_conn()
        c.execute("BEGIN IMMEDIATE")
        
        # Stock and price check
        for it in payload["items"]:
            r = c.execute("SELECT price, stock, enabled, is_deleted FROM shop_products WHERE product_id=?", (it["product_id"],)).fetchone()
            if not r or r["is_deleted"] or not r["enabled"] or int(r["stock"]) < it["qty"]:
                c.execute("ROLLBACK")
                return None, f"{st('Stock ran out for')} {it['name']}"

        # Deduct wallet
        cur = c.execute("UPDATE wallet SET balance=balance-? WHERE user_id=? AND balance>=?", (total, user_id, total))
        if cur.rowcount != 1:
            c.execute("ROLLBACK")
            return None, st("Insufficient wallet balance.")

        # Deduct stock and assign auto items
        auto_delivered = []
        for it in payload["items"]:
            c.execute("UPDATE shop_products SET stock=stock-?, sold=sold+? WHERE product_id=?", (it["qty"], it["qty"], it["product_id"]))
            p_dtype = c.execute("SELECT delivery_type FROM shop_products WHERE product_id=?", (it["product_id"],)).fetchone()["delivery_type"]
            if p_dtype == "AUTO":
                auto_rows = c.execute("SELECT id, content FROM shop_auto_items WHERE product_id=? AND used=0 LIMIT ?", (it["product_id"], it["qty"])).fetchall()
                for ar in auto_rows:
                    c.execute("UPDATE shop_auto_items SET used=1, order_id=? WHERE id=?", (order_id, ar["id"]))
                    auto_delivered.append(f"📦 <b>{esc(it['name'])}:</b>\n<code>{esc(ar['content'])}</code>")

        uname = f"@{user.username}" if user.username else ""
        c.execute("""
            INSERT INTO shop_orders (order_id, user_id, username, subtotal, discount, total, coupon_code, payment_status, order_status, delivery_status)
            VALUES (?,?,?,?,?,?,?,'PAID',?,'NOT_DELIVERED')
        """, (order_id, user_id, uname, payload["subtotal"], payload["discount"], total, payload["coupon"],
              "DELIVERED" if auto_delivered else "PROCESSING"))

        for it in payload["items"]:
            c.execute("INSERT INTO shop_order_items (order_id, product_id, product_name, qty, unit_price, subtotal) VALUES (?,?,?,?,?,?)",
                      (order_id, it["product_id"], it["name"], it["qty"], it["unit_price"], it["subtotal"]))

        if payload["coupon"]:
            c.execute("INSERT INTO shop_coupon_usage (code, user_id, order_id) VALUES (?,?,?)", (payload["coupon"], user_id, order_id))
            c.execute("UPDATE shop_coupons SET used_count=used_count+1 WHERE UPPER(code)=?", (payload["coupon"],))

        c.execute("DELETE FROM shop_cart_items WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM shop_cart_coupon WHERE user_id=?", (user_id,))
        c.execute("INSERT INTO shop_transactions (user_id, order_id, kind, amount, note) VALUES (?,?,?,?,?)",
                  (user_id, order_id, "DEBIT", total, "Order payment"))
        c.execute("COMMIT")
        return order_id, auto_delivered
    except Exception as exc:
        logger.error(f"Place order failed: {exc}")
        if c:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return None, st("Order failed. Balance was not deducted.")
    finally:
        if c:
            try:
                c.close()
            except Exception:
                pass
        with _lock:
            _checkout_locks.discard(user_id)

def send_order_summary(chat_id, user_id):
    rows = cart_rows(user_id)
    if not rows:
        send(chat_id, f"🛒 {st('Your cart is empty.')}")
        return
    items = []
    subtotal = 0.0
    for r in rows:
        sub = float(r["price"]) * int(r["qty"])
        subtotal += sub
        items.append({"product_id": r["product_id"], "name": r["name"], "qty": int(r["qty"]), "unit_price": float(r["price"]), "subtotal": sub})
    
    code = sget_cart_coupon(user_id)
    disc = 0.0
    if code:
        ok, _, disc = validate_coupon(code, user_id, subtotal)
        if not ok:
            disc = 0.0
    total = max(0.0, subtotal - disc)
    bal = user_balance(user_id)
    
    if bal < total:
        send(chat_id, f"⛔ <b>{st('INSUFFICIENT BALANCE')}</b>\n{sep_pink()}\n"
                      f"💰 {st('Required')}: <b>{money(total)}</b>\n"
                      f"🏦 {st('Your Balance')}: <b>{money(bal)}</b>\n\n"
                      f"<i>{st('Please add balance from Shop Balance menu.')}</i>")
        return

    token = secrets.token_hex(4)
    shop_states[_skey(chat_id, user_id)] = {
        "step": "await_confirm",
        "data": {"token": token, "payload": {"items": items, "subtotal": subtotal, "discount": disc, "total": total, "coupon": code}}
    }
    
    lines = [f"🧾 <b>{st('ORDER CHECKOUT CONFIRMATION')}</b>\n{sep()}"]
    for it in items:
        lines.append(f"• <b>{esc(it['name'])}</b> × {it['qty']} = {money(it['subtotal'])}")
    lines.append(
        f"\n{sep_pink()}\n"
        f"💵 {st('Subtotal')}: {money(subtotal)}\n"
        f"🎟️ {st('Discount')}: −{money(disc)}\n"
        f"💰 <b>{st('Total Payable')}: {money(total)}</b>\n\n"
        f"🏦 {st('Remaining Balance')}: <b>{money(bal - total)}</b>"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"🌸 {st('CONFIRM & PAY NOW')} 🌸", callback_data=f"shop_confirm:{token}"))
    kb.add(InlineKeyboardButton(f"❌ {st('Cancel')}", callback_data="shop_confirm_cancel"))
    send(chat_id, "\n".join(lines), reply_markup=kb)

# ═══════════════════════════════════════════════════════════════════════════
# 🔑 GET CODE CENTER (HOTMAIL / 2FA)
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
            timeout=15,
        )
        tdata = token_res.json()
        if "access_token" not in tdata:
            return False, st("Access Token Failed! Client ID or Refresh Token invalid.")
        mail_res = requests.get(
            "https://graph.microsoft.com/v1.0/me/messages?$top=1&$orderby=receivedDateTime desc",
            headers={"Authorization": f"Bearer {tdata['access_token']}"},
            timeout=15,
        )
        mdata = mail_res.json()
        if mdata.get("value"):
            msg = mdata["value"][0]
            body = msg.get("body", {}).get("content", "")
            subject = msg.get("subject", "No Subject")
            sender = msg.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            otp = _gc_extract_otp(body, subject)
            if otp:
                return True, {"otp": otp, "sender": sender, "subject": subject}
            return False, st("Mail found, but no OTP code detected.")
        return False, st("No new mail found in inbox.")
    except Exception as exc:
        return False, f"Error: {exc}"

def _gc_extract_otp(body, subject):
    clean = re.sub(r"<[^<]+?>", " ", str(body or ""))
    full = f"{subject or ''} {clean}"
    for word in ("code", "otp", "verification", "confirmation", "pin"):
        m = re.search(rf"{word}.*?(\d{{4,8}})", full, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1)
    for digit in re.findall(r"\b\d{4,8}\b", full):
        if not (2000 <= int(digit) <= 2030):
            return digit
    return None

def gc_open_menu(chat_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"📧 {st('Mail Code')}", callback_data="shop_gc:mail"),
        InlineKeyboardButton(f"🛡️ {st('2FA Code')}", callback_data="shop_gc:2fa"),
    )
    send(
        chat_id,
        f"🔑 <b>{st('GET CODE CENTER')}</b>\n{sep()}\n"
        f"<blockquote>"
        f"📧 <b>{st('Mail Code')}</b> ➤ {st('Get OTP from Hotmail/Outlook API')}\n"
        f"🛡️ <b>{st('2FA Code')}</b> ➤ {st('Generate Live OTP from Secret Key')}"
        f"</blockquote>",
        reply_markup=kb
    )

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 মেসেজ হ্যান্ডলার ও স্টেট মেশিন
# ═══════════════════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO users (id, first_name, username, last_active_at) VALUES (?,?,?,?)",
                  (uid, message.from_user.first_name or "", message.from_user.username or "", now_ts()))
        c.execute("INSERT OR IGNORE INTO wallet (user_id, balance) VALUES (?, 0.0)", (uid,))
    render_menu(message.chat.id, uid, "main")

@bot.message_handler(content_types=["text"])
def handle_all_text(message):
    uid, chat_id = message.from_user.id, message.chat.id
    text = message.text.strip()
    key = _skey(chat_id, uid)

    if text == "/start":
        cmd_start(message)
        return

    # 1. State Handling
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

    menu = (shop_nav.get(uid) or ["main"])[-1]

    # User Routes
    if text == L("🛍️", "Products"):
        render_menu(chat_id, uid, "products")
    elif text == L("🛒", "My Cart"):
        send_cart(chat_id, uid)
    elif text == L("📋", "My Orders"):
        render_menu(chat_id, uid, "orders")
    elif text == L("💳", "Shop Balance"):
        render_menu(chat_id, uid, "balance")
    elif text == L("🎁", "Offers & Bonus"):
        render_menu(chat_id, uid, "offers")
    elif text == L("🔑", "Get Code Center"):
        gc_open_menu(chat_id)
    elif text == L("👤", "Profile"):
        bal = user_balance(uid)
        with conn() as c:
            ords = c.execute("SELECT COUNT(*) n FROM shop_orders WHERE user_id=?", (uid,)).fetchone()["n"]
        send(chat_id, f"👤 <b>{st('USER PROFILE')}</b>\n{sep()}\n"
                      f"<blockquote>"
                      f"🆔 <b>{st('User ID')}:</b> <code>{uid}</code>\n"
                      f"🌸 <b>{st('Name')}:</b> {esc(message.from_user.first_name)}\n"
                      f"💰 <b>{st('Balance')}:</b> <b>{money(bal)}</b>\n"
                      f"🧾 <b>{st('Orders')}:</b> <b>{ords}</b>"
                      f"</blockquote>")
    elif text == L("ℹ️", "Support & FAQ"):
        faq = sget("faq_text", "যেকোনো প্রশ্নের জন্য সাপোর্টে যোগাযোগ করুন।")
        supp = sget("support_contact", "@SupportUsername")
        send(chat_id, f"ℹ️ <b>{st('HELP & SUPPORT')}</b>\n{sep()}\n{faq}\n\n💬 Support: {supp}")

    # Submenus Handling
    elif text == L("🌸", "Category List"):
        with conn() as c:
            rows = c.execute("SELECT DISTINCT category FROM shop_products WHERE is_deleted=0 AND enabled=1").fetchall()
        if not rows:
            send(chat_id, f"📭 {st('No categories yet.')}")
            return
        kb = InlineKeyboardMarkup(row_width=2)
        for r in rows:
            kb.add(InlineKeyboardButton(f"📁 {r['category']}", callback_data=f"shop_list:cat:{r['category']}:0"))
        send(chat_id, f"🌸 <b>{st('CATEGORIES')}</b>", reply_markup=kb)

    elif text == L("📦", "All Products"):
        send_product_list(chat_id, uid, "all")
    elif text == L("✨", "New Products"):
        send_product_list(chat_id, uid, "new")
    elif text == L("🔥", "Popular Products"):
        send_product_list(chat_id, uid, "popular")
    elif text == L("⭐", "Featured Products"):
        send_product_list(chat_id, uid, "featured")
    elif text == L("🔎", "Search Product"):
        shop_states[key] = {"step": "usr_search"}
        send(chat_id, f"🔎 {st('Send product name or keyword:')}")

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

    # Balance Submenu
    elif text == L("💰", "Current Balance"):
        send(chat_id, f"💰 <b>{st('WALLET BALANCE')}</b>\n{sep_pink()}\n"
                      f"🏦 {st('Available')}: <b>{money(user_balance(uid))}</b>")
    elif text == L("➕", "Add Balance"):
        p_info = sget("payment_info", "Send payment to: bKash/Nagad 017XXXXXXXX\nThen send amount.")
        shop_states[key] = {"step": "topup_amount", "data": {}}
        send(chat_id, f"💳 <b>{st('ADD BALANCE')}</b>\n{sep_pink()}\n<blockquote>{p_info}</blockquote>\n\n{st('Send amount paid:')}")
    elif text == L("📜", "Transaction History"):
        with conn() as c:
            rows = c.execute("SELECT * FROM shop_transactions WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        if not rows:
            send(chat_id, f"📭 {st('No transactions yet.')}")
            return
        lines = [f"📜 <b>{st('TRANSACTIONS')}</b>\n{sep()}"]
        for r in rows:
            lines.append(f"• {r['kind']} <b>{money(r['amount'])}</b> | {fmt_ts(r['created_at'])}\n  📝 {esc(r['note'])}")
        send(chat_id, "\n".join(lines))

    # Admin Panel
    elif text == L("👑", "Shop Admin Panel") and is_admin(uid):
        render_menu(chat_id, uid, "admin")
    elif is_admin(uid):
        handle_admin_routes(message, text)

def send_user_orders(chat_id, uid, status):
    with conn() as c:
        rows = c.execute("SELECT * FROM shop_orders WHERE user_id=? AND order_status=? ORDER BY id DESC LIMIT 10", (uid, status)).fetchall()
    if not rows:
        send(chat_id, f"📭 {st(f'No {status} orders found.')}")
        return
    for o in rows:
        send(chat_id, f"🧾 <b>{st('ORDER')} <code>{o['order_id']}</code></b>\n{sep_pink()}\n"
                      f"💰 {st('Total')}: <b>{money(o['total'])}</b>\n"
                      f"📌 {st('Status')}: <b>{o['order_status']}</b>\n"
                      f"🕒 {st('Date')}: {fmt_ts(o['created_at'])}")

# ═══════════════════════════════════════════════════════════════════════════
# 👑 অ্যাডমিন মেনু রাউটিং
# ═══════════════════════════════════════════════════════════════════════════
def handle_admin_routes(message, text):
    uid, chat_id = message.from_user.id, message.chat.id
    admin_routes = {
        L("📦", "Product Management"): "admin_products",
        L("🗃️", "Stock Management"): "admin_stock",
        L("🧾", "Order Management"): "admin_orders",
        L("🚚", "Delivery Management"): "admin_delivery",
        L("🎟️", "Coupons & Offers"): "admin_promos",
        L("👥", "Users & Balance"): "admin_users",
        L("📊", "Reports"): "admin_reports",
        L("⚙️", "Shop Settings"): "admin_settings",
        L("🗂️", "Shop Logs"): "admin_logs",
    }
    if text in admin_routes:
        render_menu(chat_id, uid, admin_routes[text])
        return

    # Actions inside Admin
    if text == L("➕", "Add Product"):
        shop_states[_skey(chat_id, uid)] = {"step": "ap_name", "data": {}}
        send(chat_id, f"🌸 {st('Send product name:')}")
    elif text == L("📃", "Product List"):
        with conn() as c:
            rows = c.execute("SELECT * FROM shop_products WHERE is_deleted=0 ORDER BY id DESC LIMIT 20").fetchall()
        if not rows:
            send(chat_id, f"📭 {st('No products.')}")
            return
        lines = [f"📃 <b>{st('PRODUCT LIST')}</b>\n{sep()}"]
        for p in rows:
            flag = "🟢" if p["enabled"] else "🔴"
            lines.append(f"{flag} <code>{p['product_id']}</code> — <b>{esc(p['name'])}</b> | {money(p['price'])} | Stock: {p['stock']}")
        send(chat_id, "\n".join(lines))
    elif text == L("➕", "Add User Balance"):
        shop_states[_skey(chat_id, uid)] = {"step": "adm_bal_uid", "mode": "add"}
        send(chat_id, f"👤 {st('Send User Numeric Telegram ID:')}")
    elif text == L("➖", "Remove User Balance"):
        shop_states[_skey(chat_id, uid)] = {"step": "adm_bal_uid", "mode": "rem"}
        send(chat_id, f"👤 {st('Send User Numeric Telegram ID:')}")
    elif text == L("📢", "Send Notice"):
        shop_states[_skey(chat_id, uid)] = {"step": "adm_notice"}
        send(chat_id, f"📢 {st('Send notice message for all buyers:')}")

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

    # User Topup
    if step == "topup_amount":
        try:
            amt = float(text)
            if amt <= 0: raise ValueError
            state["amount"] = amt
            state["step"] = "topup_ref"
            send(chat_id, f"📝 {st('Send Transaction ID / Reference:')}")
        except Exception:
            send(chat_id, f"⛔ {st('Send a valid amount.')}")
        return True

    if step == "topup_ref":
        amt = state["amount"]
        with conn() as c:
            cur = c.execute("INSERT INTO shop_topups (user_id, amount, reference) VALUES (?,?,?)", (uid, amt, text))
            tid = cur.lastrowid
        shop_states.pop(key, None)
        send(chat_id, f"✅ <b>{st('TOP-UP REQUEST SUBMITTED')}</b>\n{sep_pink()}\n"
                      f"🧾 <code>#{tid}</code> | 💰 <b>{money(amt)}</b>\n<i>{st('Waiting for admin approval.')}</i>")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"shop_topup:approve:{tid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"shop_topup:reject:{tid}")
        )
        send(ADMIN_ID, f"🔔 <b>NEW TOP-UP REQUEST #{tid}</b>\n{sep()}\n"
                       f"👤 User: <code>{uid}</code>\n💰 Amount: {money(amt)}\n📝 Ref: <code>{esc(text)}</code>",
             reply_markup=kb)
        return True

    # Admin Add Product
    if step == "ap_name":
        state["data"]["name"] = text
        state["step"] = "ap_cat"
        send(chat_id, f"🗂️ {st('Send category name:')}")
        return True

    if step == "ap_cat":
        state["data"]["cat"] = text
        state["step"] = "ap_price"
        send(chat_id, f"💰 {st('Send price:')}")
        return True

    if step == "ap_price":
        try:
            state["data"]["price"] = float(text)
            state["step"] = "ap_stock"
            send(chat_id, f"📦 {st('Send stock count:')}")
        except Exception:
            send(chat_id, f"⛔ {st('Send valid number.')}")
        return True

    if step == "ap_stock":
        try:
            state["data"]["stock"] = int(text)
            state["step"] = "ap_dtype"
            send(chat_id, f"🚚 {st('Delivery Type (AUTO / TEXT / FILE):')}")
        except Exception:
            send(chat_id, f"⛔ {st('Send integer.')}")
        return True

    if step == "ap_dtype":
        dt = text.upper()
        if dt not in ("AUTO", "TEXT", "FILE"):
            send(chat_id, f"⛔ {st('Choose AUTO, TEXT or FILE.')}")
            return True
        state["data"]["dtype"] = dt
        state["step"] = "ap_desc"
        send(chat_id, f"📝 {st('Send description (or - to skip):')}")
        return True

    if step == "ap_desc":
        desc = "" if text == "-" else text
        d = state["data"]
        with conn() as c:
            cnt = c.execute("SELECT COUNT(*) n FROM shop_products").fetchone()["n"]
            pid = f"PK{1001 + cnt}"
            c.execute("INSERT INTO shop_products (product_id, name, category, description, price, stock, delivery_type) VALUES (?,?,?,?,?,?,?)",
                      (pid, d["name"], d["cat"], desc, d["price"], d["stock"], d["dtype"]))
        shop_states.pop(key, None)
        send(chat_id, f"🌸 <b>{st('PRODUCT ADDED')}</b>\n{sep_pink()}\n"
                      f"🆔 <code>{pid}</code> | <b>{esc(d['name'])}</b>\n💰 {money(d['price'])} | 📦 {d['stock']}")
        return True

    # Admin Balance
    if step == "adm_bal_uid":
        try:
            state["target"] = int(text)
            state["step"] = "adm_bal_amt"
            send(chat_id, f"💰 {st('Send amount (e.g. 100):')}")
        except Exception:
            send(chat_id, f"⛔ {st('Send numeric user id.')}")
        return True

    if step == "adm_bal_amt":
        try:
            amt = float(text)
            target = state["target"]
            delta = amt if state["mode"] == "add" else -amt
            adjust_balance(target, delta, uid, "Admin direct adjust")
            shop_states.pop(key, None)
            send(chat_id, f"✅ {st('Balance updated for')} <code>{target}</code>.")
        except Exception as e:
            send(chat_id, f"⛔ Error: {e}")
        return True

    # Broadcast Notice
    if step == "adm_notice":
        shop_states.pop(key, None)
        with conn() as c:
            users = c.execute("SELECT id FROM users").fetchall()
        sent = 0
        for u in users:
            try:
                send(u["id"], f"📢 <b>{st('SHOP NOTICE')}</b>\n{sep()}\n{esc(text)}")
                sent += 1
            except Exception:
                pass
        send(chat_id, f"✅ Notice sent to {sent} users.")
        return True

    # Get Code Data Input
    if step == "gc_mail_data":
        parts = text.split("|")
        if len(parts) < 4:
            send(chat_id, f"⛔ Format: <code>Email|Pass|RefreshToken|ClientID</code>")
            return True
        _gc_sessions[uid] = {"email": parts[0].strip(), "r_token": parts[2].strip(), "c_id": parts[3].strip()}
        shop_states.pop(key, None)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📥 Check Inbox OTP", callback_data="shop_gc:mail_check"))
        send(chat_id, f"✅ <b>{st('MAIL DATA SAVED')}</b>\n{parts[0]}", reply_markup=kb)
        return True

    if step == "gc_2fa_key":
        secret = text.replace(" ", "").upper()
        try:
            otp = pyotp.TOTP(secret).now()
            _gc_sessions[uid] = {"2fa_key": secret}
            shop_states.pop(key, None)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("♻️ Refresh 2FA", callback_data="shop_gc:2fa_refresh"))
            send(chat_id, f"🛡️ <b>{st('2FA OTP')}:</b> <code>{otp}</code>", reply_markup=kb)
        except Exception:
            send(chat_id, f"⛔ {st('Invalid 2FA Secret Key.')}")
        return True

    return False

# ═══════════════════════════════════════════════════════════════════════════
# 🔘 ইনলাইন কলব্যাক কুয়েরি হ্যান্ডলার
# ═══════════════════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    uid = call.from_user.id
    data = call.data or ""
    chat_id = call.message.chat.id if call.message else uid

    if data == "shop_noop":
        bot.answer_callback_query(call.id)
        return

    # View Product
    if data.startswith("shop_view:"):
        pid = data.split(":", 1)[1]
        p = get_product(pid)
        bot.answer_callback_query(call.id)
        if not p:
            send(chat_id, f"⛔ {st('Product unavailable.')}")
            return
        if p.get("image_file_id"):
            try:
                bot.send_photo(chat_id, p["image_file_id"], caption=product_card(p), reply_markup=product_inline(p))
                return
            except Exception:
                pass
        send(chat_id, product_card(p), reply_markup=product_inline(p))
        return

    # Quantity Selector
    if data.startswith("shop_qty:"):
        _, mode, pid, qty_str = data.split(":", 3)
        qty = max(1, int(qty_str))
        p = get_product(pid)
        if not p:
            bot.answer_callback_query(call.id, "Unavailable", show_alert=True)
            return
        stock = int(p["stock"])
        qty = min(qty, stock)
        bot.answer_callback_query(call.id)
        
        kb = InlineKeyboardMarkup(row_width=3)
        kb.row(
            InlineKeyboardButton("➖", callback_data=f"shop_qty:{mode}:{pid}:{max(1, qty-1)}"),
            InlineKeyboardButton(f"🌸 {qty} 🌸", callback_data="shop_noop"),
            InlineKeyboardButton("➕", callback_data=f"shop_qty:{mode}:{pid}:{min(stock, qty+1)}"),
        )
        label = f"⚡ {st('Buy Now')}" if mode == "buy" else f"🛒 {st('Add to Cart')}"
        kb.add(InlineKeyboardButton(label, callback_data=f"shop_do:{mode}:{pid}:{qty}"))
        kb.add(InlineKeyboardButton(f"◀️ {st('Back')}", callback_data=f"shop_view:{pid}"))
        
        text = (
            f"🌸 <b>{esc(p['name'])}</b>\n{sep_pink()}\n"
            f"💰 {st('Unit Price')}: {money(p['price'])}\n"
            f"🔢 {st('Selected Quantity')}: <b>{qty}</b>\n"
            f"🧮 {st('Subtotal')}: <b>{money(float(p['price']) * qty)}</b>"
        )
        try:
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=kb)
        except Exception:
            send(chat_id, text, reply_markup=kb)
        return

    # Add to Cart / Direct Buy
    if data.startswith("shop_do:"):
        _, mode, pid, qty_str = data.split(":", 3)
        qty = int(qty_str)
        with conn() as c:
            c.execute("INSERT INTO shop_cart_items (user_id, product_id, qty) VALUES (?,?,?) "
                      "ON CONFLICT(user_id, product_id) DO UPDATE SET qty=qty+excluded.qty", (uid, pid, qty))
        bot.answer_callback_query(call.id, "✅ Added to Cart!")
        if mode == "buy":
            send_order_summary(chat_id, uid)
        else:
            send_cart(chat_id, uid)
        return

    # Cart Operations
    if data.startswith("shop_cart:"):
        act = data.split(":", 1)[1]
        if act == "clear":
            with conn() as c:
                c.execute("DELETE FROM shop_cart_items WHERE user_id=?", (uid,))
                c.execute("DELETE FROM shop_cart_coupon WHERE user_id=?", (uid,))
            bot.answer_callback_query(call.id, "Cart cleared!")
            send(chat_id, f"🗑️ {st('Your cart is empty.')}")
            return
        if act == "checkout":
            bot.answer_callback_query(call.id)
            send_order_summary(chat_id, uid)
            return
        op, pid = act.split(":", 1)
        with conn() as c:
            if op == "del":
                c.execute("DELETE FROM shop_cart_items WHERE user_id=? AND product_id=?", (uid, pid))
            elif op == "inc":
                c.execute("UPDATE shop_cart_items SET qty=qty+1 WHERE user_id=? AND product_id=?", (uid, pid))
            elif op == "dec":
                c.execute("UPDATE shop_cart_items SET qty=MAX(1, qty-1) WHERE user_id=? AND product_id=?", (uid, pid))
        bot.answer_callback_query(call.id)
        send_cart(chat_id, uid)
        return

    # Order Confirmation
    if data.startswith("shop_confirm:"):
        token = data.split(":", 1)[1]
        key = _skey(chat_id, uid)
        state = shop_states.pop(key, None)
        if not state or state.get("data", {}).get("token") != token:
            bot.answer_callback_query(call.id, "Session expired.", show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "Processing...")
        order_id, auto_items = place_order(call.from_user, chat_id, state["data"]["payload"])
        if not order_id:
            send(chat_id, f"⛔ {auto_items}")
            return

        msg = (
            f"🎉 <b>{st('ORDER COMPLETED')}</b> 🌸\n{sep()}\n"
            f"🧾 {st('Order ID')}: <code>{order_id}</code>\n"
            f"💰 {st('Paid')}: <b>{money(state['data']['payload']['total'])}</b>\n"
            f"🏦 {st('Remaining Balance')}: <b>{money(user_balance(uid))}</b>\n"
        )
        if auto_items:
            msg += f"\n🔑 <b>{st('DELIVERY CONTENT')}:</b>\n" + "\n\n".join(auto_items)
        else:
            msg += f"\n⏳ <i>{st('Your order is processing. Admin will deliver soon.')}</i>"
        send(chat_id, msg)
        render_menu(chat_id, uid, "main")
        return

    if data == "shop_confirm_cancel":
        shop_states.pop(_skey(chat_id, uid), None)
        bot.answer_callback_query(call.id, "Cancelled.")
        send(chat_id, f"❌ {st('Checkout cancelled.')}")
        return

    # Get Code Callbacks
    if data.startswith("shop_gc:"):
        act = data.split(":", 1)[1]
        if act == "mail":
            shop_states[_skey(chat_id, uid)] = {"step": "gc_mail_data"}
            bot.answer_callback_query(call.id)
            send(chat_id, f"📧 {st('Send data:')}\n<code>Email|Pass|RefreshToken|ClientID</code>")
        elif act == "2fa":
            shop_states[_skey(chat_id, uid)] = {"step": "gc_2fa_key"}
            bot.answer_callback_query(call.id)
            send(chat_id, f"🛡️ {st('Send 2FA Base-32 Secret Key:')}")
        elif act == "mail_check":
            ses = _gc_sessions.get(uid)
            if not ses:
                bot.answer_callback_query(call.id, "Send mail data again.", show_alert=True)
                return
            bot.answer_callback_query(call.id, "Checking...")
            ok, res = _gc_hotmail_otp(ses["r_token"], ses["c_id"])
            if ok:
                send(chat_id, f"✨ <b>{st('OTP RECEIVED')}</b> ✨\n{sep_pink()}\n"
                              f"🔑 <b>{st('Code')}:</b> <code>{res['otp']}</code>\n"
                              f"🏷️ Sender: {res['sender']}\n📌 Subject: {res['subject']}")
            else:
                send(chat_id, f"⚠️ {res}")
        elif act == "2fa_refresh":
            ses = _gc_sessions.get(uid)
            if not ses or "2fa_key" not in ses:
                bot.answer_callback_query(call.id, "Key not found.", show_alert=True)
                return
            otp = pyotp.TOTP(ses["2fa_key"]).now()
            bot.answer_callback_query(call.id, "Refreshed!")
            send(chat_id, f"🛡️ <b>{st('2FA OTP')}:</b> <code>{otp}</code>")
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
            send(r["user_id"], f"✅ <b>{st('TOP-UP APPROVED')}</b>\n💰 {money(r['amount'])} added to wallet.")
        else:
            with conn() as c:
                c.execute("UPDATE shop_topups SET status='REJECTED' WHERE id=?", (tid,))
            bot.answer_callback_query(call.id, "Rejected!")
            send(r["user_id"], f"❌ <b>{st('TOP-UP REJECTED')}</b>\n💰 {money(r['amount'])}")
        return

# ═══════════════════════════════════════════════════════════════════════════
# 🌐 RENDER 24/7 HEALTH SERVER
# ═══════════════════════════════════════════════════════════════════════════
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b'{"status":"ok","service":"pink-telegram-shop-bot"}'
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
        logger.info(f"🌸 Health server active on port {port}")
    except Exception as exc:
        logger.warning(f"Health server port bind warning: {exc}")

# ═══════════════════════════════════════════════════════════════════════════
# 🏁 মেইন এক্সিকিউশন
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    start_health_server()
    print("🌸 Pink Aesthetic Shop Bot is starting...")
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True)