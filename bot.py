"""
ADVANCED TELEGRAM SHOP & ADMIN SYSTEM
Matches the complete shop_admin architecture with full features & Render 24/7 support.
"""

import logging
import os
import sqlite3
import threading
import time
from flask import Flask
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ═══════════════════════════════════════════════════════════════════════════
# ⚙️ কনফিগারেশন
# ═══════════════════════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))
DB_PATH = "shop_master.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("shop_bot")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
user_states = {}

# ═══════════════════════════════════════════════════════════════════════════
# 🗄️ ডাটাবেস ও হেল্পার
# ═══════════════════════════════════════════════════════════════════════════
class DBConnection:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.path, timeout=20.0)
        self.conn.row_factory = sqlite3.Row
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
    c = sqlite3.connect(DB_PATH, timeout=20.0)
    c.row_factory = sqlite3.Row
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

        CREATE TABLE IF NOT EXISTS shop_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS shop_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE,
            name TEXT,
            category TEXT DEFAULT 'General',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0.0,
            stock INTEGER DEFAULT 0,
            delivery_type TEXT DEFAULT 'AUTO', -- AUTO, TEXT, FILE
            image_file_id TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            featured INTEGER DEFAULT 0,
            popular INTEGER DEFAULT 0,
            sold INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_auto_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            content TEXT,
            used INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_stock_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            admin_id INTEGER,
            change INTEGER,
            reason TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            user_id INTEGER,
            username TEXT,
            total REAL DEFAULT 0.0,
            discount REAL DEFAULT 0.0,
            order_status TEXT DEFAULT 'PENDING', -- PENDING, CONFIRMED, PROCESSING, DELIVERED, CANCELLED
            delivery_content TEXT DEFAULT '',
            delivery_file_id TEXT DEFAULT '',
            delivery_file_type TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now')),
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            product_id TEXT,
            product_name TEXT,
            price REAL,
            qty INTEGER,
            subtotal REAL
        );

        CREATE TABLE IF NOT EXISTS shop_cart_items (
            user_id INTEGER,
            product_id TEXT,
            qty INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS shop_cart_coupon (
            user_id INTEGER PRIMARY KEY,
            code TEXT
        );

        CREATE TABLE IF NOT EXISTS shop_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount_type TEXT DEFAULT 'PERCENT', -- PERCENT, FLAT
            discount_value REAL DEFAULT 0.0,
            min_order REAL DEFAULT 0.0,
            max_usage INTEGER DEFAULT 0,
            per_user_limit INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            start_at INTEGER DEFAULT (strftime('%s','now')),
            expiry_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS shop_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            kind TEXT DEFAULT 'OFFER',
            enabled INTEGER DEFAULT 1,
            start_at INTEGER DEFAULT (strftime('%s','now')),
            expiry_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS shop_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            admin_id INTEGER,
            kind TEXT,
            is_resend INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_topups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            reference TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target TEXT,
            detail TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS shop_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT,
            amount REAL,
            order_id TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        """)

init_db()

# ═══════════════════════════════════════════════════════════════════════════
# 🎨 ফরম্যাটিং ও ইউটিলিটি
# ═══════════════════════════════════════════════════════════════════════════
def sget(key: str, default: str = "") -> str:
    with conn() as c:
        row = c.execute("SELECT value FROM shop_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def sset(key: str, val: str):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?,?)", (key, str(val)))

def currency() -> str:
    return sget("currency", "BDT")

def money(v) -> str:
    try:
        return f"{float(v):,.2f} {currency()}"
    except Exception:
        return f"0.00 {currency()}"

def sep(char="━", n=26) -> str:
    return char * n

def esc(text) -> str:
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def now_ts() -> int:
    return int(time.time())

def fmt_ts(ts) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))

def is_admin(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_ID)

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
            return False, "Insufficient balance"
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
        return False, str(exc)
    finally:
        c.close()
    
    with conn() as db:
        db.execute(
            "INSERT INTO shop_activity_logs (admin_id, action, target, detail) VALUES (?,?,?,?)",
            (admin_id, "BALANCE", str(user_id), f"{delta:+.2f} {reason}")
        )
    return True, "ok"

def log_activity(admin_id: int, action: str, target: str = "", detail: str = ""):
    with conn() as c:
        c.execute(
            "INSERT INTO shop_activity_logs (admin_id, action, target, detail) VALUES (?,?,?,?)",
            (admin_id, action, target, detail)
        )

# ═══════════════════════════════════════════════════════════════════════════
# 📱 কীবোর্ড মেনু
# ═══════════════════════════════════════════════════════════════════════════
def user_main_keyboard(uid: int):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🛍️ Browse Products"),
        KeyboardButton("🛒 My Cart"),
        KeyboardButton("💳 Add Balance"),
        KeyboardButton("📦 My Orders"),
        KeyboardButton("👤 Profile"),
        KeyboardButton("ℹ️ How To Buy / FAQ")
    )
    if is_admin(uid):
        kb.add(KeyboardButton("👑 Admin Panel"))
    return kb

ADMIN_MENUS = {
    "admin": [
        [KeyboardButton("📦 Product Management"), KeyboardButton("🗃️ Stock Management")],
        [KeyboardButton("🧾 Order Management"), KeyboardButton("🚚 Delivery Management")],
        [KeyboardButton("🎟️ Coupons & Offers"), KeyboardButton("👥 Users & Balance")],
        [KeyboardButton("📊 Reports"), KeyboardButton("⚙️ Shop Settings")],
        [KeyboardButton("🗂️ Shop Logs")],
        [KeyboardButton("🔙 Exit Admin")]
    ],
    "admin_products": [
        [KeyboardButton("➕ Add Product"), KeyboardButton("🗑️ Delete Product")],
        [KeyboardButton("📃 Product List"), KeyboardButton("🔁 Toggle Enabled")],
        [KeyboardButton("⭐ Featured Toggle"), KeyboardButton("🖼️ Set Image")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_stock": [
        [KeyboardButton("➕ Add Stock"), KeyboardButton("🔢 Set Stock")],
        [KeyboardButton("⚠️ Low Stock Report"), KeyboardButton("🤖 Auto Delivery Items")],
        [KeyboardButton("📜 Stock Logs")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_orders": [
        [KeyboardButton("⏳ Pending Orders"), KeyboardButton("✅ Confirmed Orders")],
        [KeyboardButton("🚚 Processing Orders"), KeyboardButton("📤 Delivered Orders")],
        [KeyboardButton("❌ Cancelled Orders"), KeyboardButton("🔎 Find Order")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_delivery": [
        [KeyboardButton("📤 Deliver Order"), KeyboardButton("🤖 Auto Deliver")],
        [KeyboardButton("📜 Delivery Logs")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_promos": [
        [KeyboardButton("➕ Add Coupon"), KeyboardButton("📃 Coupon List")],
        [KeyboardButton("🗑️ Delete Coupon"), KeyboardButton("🎁 Add Offer")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_users": [
        [KeyboardButton("➕ Add User Balance"), KeyboardButton("➖ Remove User Balance")],
        [KeyboardButton("💳 Top-up Requests"), KeyboardButton("🔎 User Lookup")],
        [KeyboardButton("📢 Send Notice")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_reports": [
        [KeyboardButton("📈 Sales Report"), KeyboardButton("🏆 Top Products")],
        [KeyboardButton("💰 Revenue Summary"), KeyboardButton("📊 Order Stats")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_settings": [
        [KeyboardButton("🏪 Shop Name"), KeyboardButton("💱 Currency")],
        [KeyboardButton("🧮 Minimum Order"), KeyboardButton("💳 Payment Info")],
        [KeyboardButton("🛠️ Maintenance Mode"), KeyboardButton("💬 Support Contact")],
        [KeyboardButton("🔙 Admin Menu")]
    ],
    "admin_logs": [
        [KeyboardButton("🗂️ Activity Logs"), KeyboardButton("📜 Stock Log List")],
        [KeyboardButton("💸 Shop Transactions")],
        [KeyboardButton("🔙 Admin Menu")]
    ]
}

def render_admin_menu(chat_id, menu_key="admin"):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for row in ADMIN_MENUS.get(menu_key, ADMIN_MENUS["admin"]):
        kb.row(*row)
    title = f"👑 <b>SHOP CONTROL: {menu_key.upper()}</b>\n{sep()}"
    bot.send_message(chat_id, title, reply_markup=kb)

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 ইউজার শপ লজিক (Browse, Cart, Checkout)
# ═══════════════════════════════════════════════════════════════════════════
def show_categories(chat_id):
    with conn() as c:
        rows = c.execute("SELECT DISTINCT category FROM shop_products WHERE is_deleted=0 AND enabled=1").fetchall()
    
    if not rows:
        bot.send_message(chat_id, "📭 বর্তমানে কোনো প্রোডাক্ট পাওয়া যায়নি।")
        return
        
    kb = InlineKeyboardMarkup(row_width=2)
    for r in rows:
        cat = r["category"] or "General"
        kb.add(InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat:{cat}"))
    bot.send_message(chat_id, f"🛍️ <b>ক্যাটাগরি নির্বাচন করুন:</b>\n{sep()}", reply_markup=kb)

def show_category_products(chat_id, cat_name):
    with conn() as c:
        products = c.execute(
            "SELECT * FROM shop_products WHERE category=? AND is_deleted=0 AND enabled=1",
            (cat_name,)
        ).fetchall()
        
    if not products:
        bot.send_message(chat_id, "📭 এই ক্যাটাগরিতে কোনো প্রোডাক্ট নেই।")
        return

    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        marks = ("⭐ " if p["featured"] else "") + ("🔥 " if p["popular"] else "")
        label = f"{marks}{p['name']} — {money(p['price'])} (Stock: {p['stock']})"
        kb.add(InlineKeyboardButton(label, callback_data=f"prod_view:{p['product_id']}"))
    kb.add(InlineKeyboardButton("🔙 Back to Categories", callback_data="back_cats"))
    bot.send_message(chat_id, f"📁 <b>{cat_name}</b> এর প্রোডাক্ট সমূহ:\n{sep()}", reply_markup=kb)

def show_product_detail(chat_id, pid):
    with conn() as c:
        p = c.execute("SELECT * FROM shop_products WHERE product_id=?", (pid,)).fetchone()
    if not p:
        bot.send_message(chat_id, "⛔ প্রোডাক্ট পাওয়া যায়নি।")
        return

    text = (
        f"🛍️ <b>{esc(p['name'])}</b>\n{sep()}\n"
        f"📝 {esc(p['description']) or 'কোনো বিবরণ নেই'}\n\n"
        f"💰 <b>Price:</b> {money(p['price'])}\n"
        f"📦 <b>In Stock:</b> <b>{p['stock']}</b>\n"
        f"🚚 <b>Delivery Type:</b> <code>{p['delivery_type']}</code>\n"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    if p["stock"] > 0:
        kb.add(
            InlineKeyboardButton("🛒 Add to Cart", callback_data=f"cart_add:{pid}"),
            InlineKeyboardButton("⚡ Instant Buy", callback_data=f"buy_direct:{pid}")
        )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"cat:{p['category']}"))
    
    if p["image_file_id"]:
        try:
            bot.send_photo(chat_id, p["image_file_id"], caption=text, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

def render_cart(chat_id, uid):
    with conn() as c:
        items = c.execute("""
            SELECT c.product_id, c.qty, p.name, p.price, p.stock
            FROM shop_cart_items c
            JOIN shop_products p ON p.product_id=c.product_id
            WHERE c.user_id=?
        """, (uid,)).fetchall()
        coupon_row = c.execute("SELECT code FROM shop_cart_coupon WHERE user_id=?", (uid,)).fetchone()
    
    if not items:
        bot.send_message(chat_id, "🛒 <b>আপনার কার্ট সম্পূর্ণ খালি!</b>")
        return

    subtotal = sum(it["price"] * it["qty"] for it in items)
    discount = 0.0
    coupon_code = coupon_row["code"] if coupon_row else None
    
    if coupon_code:
        with conn() as c:
            coup = c.execute("SELECT * FROM shop_coupons WHERE code=? AND enabled=1", (coupon_code,)).fetchone()
            if coup:
                if coup["discount_type"] == "PERCENT":
                    discount = (subtotal * coup["discount_value"]) / 100.0
                else:
                    discount = coup["discount_value"]
    
    total = max(0.0, subtotal - discount)
    lines = [f"🛒 <b>SHOPPING CART</b>\n{sep()}"]
    kb = InlineKeyboardMarkup(row_width=2)
    
    for it in items:
        lines.append(f"• <b>{esc(it['name'])}</b> x{it['qty']} — {money(it['price'] * it['qty'])}")
        kb.add(
            InlineKeyboardButton(f"➖ {it['product_id']}", callback_data=f"cart_dec:{it['product_id']}"),
            InlineKeyboardButton(f"❌ Remove", callback_data=f"cart_rem:{it['product_id']}")
        )
    
    lines.append(sep("─"))
    lines.append(f"💵 Subtotal: <b>{money(subtotal)}</b>")
    if discount > 0:
        lines.append(f"🎟️ Discount ({coupon_code}): <b>-{money(discount)}</b>")
    lines.append(f"💰 <b>Total Payable:</b> <b>{money(total)}</b>")
    
    kb.row(
        InlineKeyboardButton("🎟️ Apply Coupon", callback_data="cart_apply_coupon"),
        InlineKeyboardButton("💳 Checkout", callback_data="cart_checkout")
    )
    bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)

def process_checkout(chat_id, uid):
    with conn() as c:
        items = [dict(r) for r in c.execute("""
            SELECT c.product_id, c.qty, p.name, p.price, p.stock, p.delivery_type
            FROM shop_cart_items c
            JOIN shop_products p ON p.product_id=c.product_id
            WHERE c.user_id=?
        """, (uid,)).fetchall()]
        coupon_row = c.execute("SELECT code FROM shop_cart_coupon WHERE user_id=?", (uid,)).fetchone()

    if not items:
        bot.send_message(chat_id, "⛔ কার্ট খালি।")
        return

    # Check stock
    for it in items:
        if it["stock"] < it["qty"]:
            bot.send_message(chat_id, f"⛔ <b>{esc(it['name'])}</b> এর পর্যাপ্ত স্টক নেই!")
            return

    subtotal = sum(it["price"] * it["qty"] for it in items)
    discount = 0.0
    if coupon_row:
        with conn() as c:
            coup = c.execute("SELECT * FROM shop_coupons WHERE code=? AND enabled=1", (coupon_row["code"],)).fetchone()
            if coup:
                if coup["discount_type"] == "PERCENT":
                    discount = (subtotal * coup["discount_value"]) / 100.0
                else:
                    discount = coup["discount_value"]
    
    total = max(0.0, subtotal - discount)
    bal = user_balance(uid)
    
    if bal < total:
        bot.send_message(
            chat_id,
            f"⛔ <b>অপর্যাপ্ত ব্যালেন্স!</b>\nপ্রয়োজন: <b>{money(total)}</b>\nআপনার আছে: <b>{money(bal)}</b>\nদয়া করে ব্যালেন্স যোগ করুন।"
        )
        return

    # ACID Transaction
    db = raw_conn()
    order_id = "ORD-" + str(int(time.time()))[-6:]
    auto_deliveries = []
    
    try:
        db.execute("BEGIN IMMEDIATE")
        # Deduct wallet
        db.execute("UPDATE wallet SET balance=balance-? WHERE user_id=?", (total, uid))
        db.execute(
            "INSERT INTO shop_transactions (user_id, kind, amount, order_id, note) VALUES (?,?,?,?,?)",
            (uid, "DEBIT", total, order_id, "Order checkout")
        )
        # Create order
        db.execute(
            "INSERT INTO shop_orders (order_id, user_id, total, discount, order_status) VALUES (?,?,?,?,?)",
            (order_id, uid, total, discount, "PROCESSING")
        )
        for it in items:
            db.execute(
                "INSERT INTO shop_order_items (order_id, product_id, product_name, price, qty, subtotal) VALUES (?,?,?,?,?,?)",
                (order_id, it["product_id"], it["name"], it["price"], it["qty"], it["price"] * it["qty"])
            )
            db.execute("UPDATE shop_products SET stock=stock-?, sold=sold+? WHERE product_id=?", (it["qty"], it["qty"], it["product_id"]))
            
            # If Auto delivery
            if it["delivery_type"] == "AUTO":
                auto_rows = db.execute(
                    "SELECT id, content FROM shop_auto_items WHERE product_id=? AND used=0 LIMIT ?",
                    (it["product_id"], it["qty"])
                ).fetchall()
                for ar in auto_rows:
                    db.execute("UPDATE shop_auto_items SET used=1 WHERE id=?", (ar["id"],))
                    auto_deliveries.append(f"📦 <b>{esc(it['name'])}:</b>\n<code>{esc(ar['content'])}</code>")

        # Clear cart
        db.execute("DELETE FROM shop_cart_items WHERE user_id=?", (uid,))
        db.execute("DELETE FROM shop_cart_coupon WHERE user_id=?", (uid,))
        
        if auto_deliveries:
            db.execute(
                "UPDATE shop_orders SET order_status='DELIVERED', delivery_content=? WHERE order_id=?",
                ("\n\n".join(auto_deliveries), order_id)
            )
        db.execute("COMMIT")
    except Exception as exc:
        db.execute("ROLLBACK")
        bot.send_message(chat_id, f"⛔ অর্ডার প্রসেস করতে ব্যর্থ হয়েছে: {exc}")
        db.close()
        return
    finally:
        db.close()

    success_msg = (
        f"✅ <b>অর্ডার সফল হয়েছে!</b>\n{sep()}\n"
        f"🧾 <b>Order ID:</b> <code>{order_id}</code>\n"
        f"💰 <b>Paid:</b> <b>{money(total)}</b>\n"
        f"🏦 <b>Remaining Balance:</b> <b>{money(user_balance(uid))}</b>\n"
    )
    if auto_deliveries:
        success_msg += f"\n🔑 <b>ডেলিভারি ডাটা:</b>\n" + "\n\n".join(auto_deliveries)
    else:
        success_msg += "\n⏳ আপনার অর্ডারটি প্রসেসিং এ আছে। অ্যাডমিন খুব শীঘ্রই ডেলিভারি সম্পন্ন করবেন।"
    
    bot.send_message(chat_id, success_msg)
    
    # Notify Admin
    bot.send_message(
        ADMIN_ID,
        f"🔔 <b>নতুন অর্ডার এসেছে!</b>\n{sep()}\n"
        f"🧾 <b>Order ID:</b> <code>{order_id}</code>\n"
        f"👤 <b>User:</b> <code>{uid}</code>\n"
        f"💰 <b>Total:</b> {money(total)}\n"
        f"📌 <b>Status:</b> {'DELIVERED (AUTO)' if auto_deliveries else 'PROCESSING'}"
    )

# ═══════════════════════════════════════════════════════════════════════════
# 💬 বট মেসেজ হ্যান্ডলার
# ═══════════════════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    with conn() as c:
        c.execute(
            "INSERT INTO users (id, first_name, username, last_active_at) VALUES (?,?,?,strftime('%s','now')) "
            "ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name, username=excluded.username, last_active_at=strftime('%s','now')",
            (uid, message.from_user.first_name or "", message.from_user.username or "")
        )
        c.execute("INSERT OR IGNORE INTO wallet (user_id, balance) VALUES (?, 0.0)", (uid,))
    
    shop_name = sget("shop_name", "Telegram Digital Shop")
    welcome_msg = (
        f"👋 <b>Welcome to {shop_name}, {message.from_user.first_name}!</b>\n{sep()}\n"
        f"💰 আপনার বর্তমান ব্যালেন্স: <b>{money(user_balance(uid))}</b>\n\n"
        f"কেনাকাটা শুরু করতে নিচের মেনু ব্যবহার করুন।"
    )
    bot.send_message(message.chat.id, welcome_msg, reply_markup=user_main_keyboard(uid))

@bot.message_handler(content_types=["text"])
def handle_all_text(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()

    # Admin submenus
    if is_admin(uid):
        admin_routes = {
            "📦 Product Management": "admin_products",
            "🗃️ Stock Management": "admin_stock",
            "🧾 Order Management": "admin_orders",
            "🚚 Delivery Management": "admin_delivery",
            "🎟️ Coupons & Offers": "admin_promos",
            "👥 Users & Balance": "admin_users",
            "📊 Reports": "admin_reports",
            "⚙️ Shop Settings": "admin_settings",
            "🗂️ Shop Logs": "admin_logs",
            "🔙 Admin Menu": "admin",
        }
        if text in admin_routes:
            render_admin_menu(chat_id, admin_routes[text])
            return
        if text == "🔙 Exit Admin":
            bot.send_message(chat_id, "প্রধান মেনু:", reply_markup=user_main_keyboard(uid))
            return

    # Handle States
    if uid in user_states:
        handle_state_input(message)
        return

    # User Button routing
    if text == "🛍️ Browse Products":
        show_categories(chat_id)
    elif text == "🛒 My Cart":
        render_cart(chat_id, uid)
    elif text == "💳 Add Balance":
        p_info = sget("payment_info", "Send payment to:\n📱 bKash/Nagad: 017XXXXXXXX\nThen click Submit TrxID.")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📝 Submit Payment TrxID", callback_data="topup_start"))
        bot.send_message(chat_id, f"💳 <b>ADD BALANCE</b>\n{sep()}\n{p_info}", reply_markup=kb)
    elif text == "📦 My Orders":
        show_my_orders(chat_id, uid)
    elif text == "👤 Profile":
        bal = user_balance(uid)
        bot.send_message(
            chat_id,
            f"👤 <b>USER PROFILE</b>\n{sep()}\n"
            f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
            f"💰 <b>Wallet Balance:</b> <b>{money(bal)}</b>\n"
        )
    elif text == "ℹ️ How To Buy / FAQ":
        faq = sget("faq_text", "যেকোনো প্রশ্নের জন্য সাপোর্টে যোগাযোগ করুন।")
        supp = sget("support_contact", "@SupportUsername")
        bot.send_message(chat_id, f"ℹ️ <b>FAQ & SUPPORT</b>\n{sep()}\n{faq}\n\n💬 Support: {supp}")
    elif text == "👑 Admin Panel" and is_admin(uid):
        render_admin_menu(chat_id, "admin")
    
    # Admin Specific Menu Buttons
    elif is_admin(uid):
        handle_admin_button(message)

# ═══════════════════════════════════════════════════════════════════════════
# 👑 অ্যাডমিন মেনু হ্যান্ডলার
# ═══════════════════════════════════════════════════════════════════════════
def handle_admin_button(message):
    uid, chat_id, text = message.from_user.id, message.chat.id, message.text.strip()
    
    # Products
    if text == "➕ Add Product":
        user_states[uid] = {"step": "ap_name", "data": {}}
        bot.send_message(chat_id, "📝 প্রোডাক্টের নাম লিখুন:")
    elif text == "📃 Product List":
        with conn() as c:
            rows = c.execute("SELECT * FROM shop_products WHERE is_deleted=0 ORDER BY id DESC").fetchall()
        if not rows:
            bot.send_message(chat_id, "📭 কোনো প্রোডাক্ট নেই।")
            return
        lines = [f"📃 <b>PRODUCT LIST</b>\n{sep()}"]
        for p in rows:
            flag = "🟢" if p["enabled"] else "🔴"
            lines.append(f"{flag} <code>{p['product_id']}</code> — <b>{esc(p['name'])}</b> | {money(p['price'])} | Stock: {p['stock']}")
        bot.send_message(chat_id, "\n".join(lines))
    
    elif text == "🗑️ Delete Product":
        user_states[uid] = {"step": "ap_delete"}
        bot.send_message(chat_id, "🗑️ মুছে ফেলতে চাওয়া Product ID (যেমন P1001) পাঠান:")

    # Stock
    elif text == "➕ Add Stock":
        user_states[uid] = {"step": "as_add_id"}
        bot.send_message(chat_id, "🔢 যে প্রোডাক্টে স্টক যোগ করবেন তার Product ID পাঠান:")
    elif text == "🤖 Auto Delivery Items":
        user_states[uid] = {"step": "as_auto_id"}
        bot.send_message(chat_id, "🤖 Auto Items যোগ করার জন্য Product ID পাঠান:")

    # Orders
    elif text in ("⏳ Pending Orders", "✅ Confirmed Orders", "🚚 Processing Orders", "📤 Delivered Orders", "❌ Cancelled Orders"):
        st_map = {
            "⏳ Pending Orders": "PENDING",
            "✅ Confirmed Orders": "CONFIRMED",
            "🚚 Processing Orders": "PROCESSING",
            "📤 Delivered Orders": "DELIVERED",
            "❌ Cancelled Orders": "CANCELLED"
        }
        status = st_map[text]
        with conn() as c:
            rows = c.execute("SELECT * FROM shop_orders WHERE order_status=? ORDER BY id DESC LIMIT 10", (status,)).fetchall()
        if not rows:
            bot.send_message(chat_id, f"📭 {status} কোনো অর্ডার নেই।")
            return
        for o in rows:
            kb = InlineKeyboardMarkup(row_width=2)
            if status != "DELIVERED" and status != "CANCELLED":
                kb.add(
                    InlineKeyboardButton("📤 Deliver", callback_data=f"adm_ord_del:{o['order_id']}"),
                    InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"adm_ord_can:{o['order_id']}")
                )
            bot.send_message(
                chat_id,
                f"🧾 <b>Order:</b> <code>{o['order_id']}</code>\n👤 User: <code>{o['user_id']}</code>\n💰 Total: {money(o['total'])}\n📌 Status: <b>{o['order_status']}</b>",
                reply_markup=kb if len(kb.keyboard) > 0 else None
            )

    # Users & Balance
    elif text == "➕ Add User Balance":
        user_states[uid] = {"step": "aub_uid", "mode": "add"}
        bot.send_message(chat_id, "👤 ইউজারের Telegram Numeric ID পাঠান:")
    elif text == "➖ Remove User Balance":
        user_states[uid] = {"step": "aub_uid", "mode": "remove"}
        bot.send_message(chat_id, "👤 ইউজারের Telegram Numeric ID পাঠান:")
    elif text == "📢 Send Notice":
        user_states[uid] = {"step": "a_notice"}
        bot.send_message(chat_id, "📢 সকল ইউজারকে পাঠানোর নোটিশ টেক্সট লিখুন:")

    # Reports
    elif text == "📊 Order Stats":
        with conn() as c:
            rows = c.execute("SELECT order_status, COUNT(*) n FROM shop_orders GROUP BY order_status").fetchall()
        lines = [f"📊 <b>ORDER STATS</b>\n{sep()}"]
        for r in rows:
            lines.append(f"• {r['order_status']}: <b>{r['n']}</b>")
        bot.send_message(chat_id, "\n".join(lines))
    elif text == "💰 Revenue Summary":
        with conn() as c:
            rev = c.execute("SELECT COALESCE(SUM(total),0) t FROM shop_orders WHERE order_status='DELIVERED'").fetchone()["t"]
            top = c.execute("SELECT COALESCE(SUM(amount),0) t FROM shop_topups WHERE status='APPROVED'").fetchone()["t"]
        bot.send_message(
            chat_id,
            f"💰 <b>REVENUE SUMMARY</b>\n{sep()}\n"
            f"🧾 Delivered Sales: <b>{money(rev)}</b>\n"
            f"💳 Total Top-ups Approved: <b>{money(top)}</b>"
        )

# ═══════════════════════════════════════════════════════════════════════════
# 🔄 স্টেট মেশিন হ্যান্ডলার (Input Processing)
# ═══════════════════════════════════════════════════════════════════════════
def handle_state_input(message):
    uid, chat_id = message.from_user.id, message.chat.id
    st = user_states[uid]
    step = st.get("step")
    text = message.text.strip() if message.text else ""

    if text == "/cancel":
        user_states.pop(uid, None)
        bot.send_message(chat_id, "❌ বাতিল করা হয়েছে।")
        return

    # Add Product Flow
    if step == "ap_name":
        st["data"]["name"] = text
        st["step"] = "ap_cat"
        bot.send_message(chat_id, "📁 ক্যাটাগরি নাম লিখুন (যেমন: Gaming, Accounts, Software):")
    elif step == "ap_cat":
        st["data"]["cat"] = text
        st["step"] = "ap_price"
        bot.send_message(chat_id, "💰 প্রোডাক্টের দাম লিখুন (যেমন: 150):")
    elif step == "ap_price":
        try:
            st["data"]["price"] = float(text)
            st["step"] = "ap_stock"
            bot.send_message(chat_id, "📦 স্টক পরিমাণ লিখুন (যেমন: 10):")
        except ValueError:
            bot.send_message(chat_id, "⛔ সঠিক মূল্য লিখুন:")
    elif step == "ap_stock":
        try:
            st["data"]["stock"] = int(text)
            st["step"] = "ap_type"
            bot.send_message(chat_id, "🚚 ডেলিভারি টাইপ নির্বাচন করুন (AUTO / TEXT / FILE):")
        except ValueError:
            bot.send_message(chat_id, "⛔ সঠিক সংখ্যা লিখুন:")
    elif step == "ap_type":
        dt = text.upper()
        if dt not in ("AUTO", "TEXT", "FILE"):
            bot.send_message(chat_id, "⛔ AUTO, TEXT বা FILE লিখুন:")
            return
        st["data"]["dtype"] = dt
        st["step"] = "ap_desc"
        bot.send_message(chat_id, "📝 প্রোডাক্টের বিবরণ লিখুন (বা বাদ দিতে - লিখুন):")
    elif step == "ap_desc":
        desc = "" if text == "-" else text
        d = st["data"]
        with conn() as c:
            cnt = c.execute("SELECT COUNT(*) n FROM shop_products").fetchone()["n"]
            pid = f"P{1001 + cnt}"
            c.execute(
                "INSERT INTO shop_products (product_id, name, category, description, price, stock, delivery_type) VALUES (?,?,?,?,?,?,?)",
                (pid, d["name"], d["cat"], desc, d["price"], d["stock"], d["dtype"])
            )
        user_states.pop(uid, None)
        bot.send_message(
            chat_id,
            f"✅ <b>প্রোডাক্ট তৈরি সফল!</b>\n🆔 <code>{pid}</code>\n🛍️ {d['name']}\n💰 {money(d['price'])}\n📦 Stock: {d['stock']}"
        )

    # Topup Submission
    elif step == "topup_amount":
        try:
            amt = float(text)
            st["amount"] = amt
            st["step"] = "topup_ref"
            bot.send_message(chat_id, "📝 আপনার পেমেন্ট Transaction ID (TrxID) বা প্রমাণ পাঠান:")
        except ValueError:
            bot.send_message(chat_id, "⛔ সঠিক টাকার পরিমাণ লিখুন:")
    elif step == "topup_ref":
        amt = st["amount"]
        ref = text
        with conn() as c:
            cur = c.execute("INSERT INTO shop_topups (user_id, amount, reference) VALUES (?,?,?)", (uid, amt, ref))
            req_id = cur.lastrowid
        user_states.pop(uid, None)
        bot.send_message(chat_id, "✅ ডিপোজিট রিকোয়েস্ট জমা দেওয়া হয়েছে! অ্যাডমিন দ্রুত চেক করবেন।")
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"adm_top_app:{req_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"adm_top_rej:{req_id}")
        )
        bot.send_message(
            ADMIN_ID,
            f"💳 <b>নতুন টপ-আপ রিকোয়েস্ট #{req_id}</b>\n{sep()}\n"
            f"🆔 User: <code>{uid}</code>\n💰 Amount: {money(amt)}\n📝 TrxID: <code>{esc(ref)}</code>",
            reply_markup=kb
        )

    # User Balance Adjust
    elif step == "aub_uid":
        try:
            st["target_uid"] = int(text)
            st["step"] = "aub_amt"
            bot.send_message(chat_id, f"💰 ব্যালেন্স পরিমাণ লিখুন (বর্তমান: {money(user_balance(int(text)))}):")
        except ValueError:
            bot.send_message(chat_id, "⛔ সঠিক Numeric Telegram ID দিন:")
    elif step == "aub_amt":
        try:
            amt = float(text)
            target = st["target_uid"]
            mode = st["mode"]
            delta = amt if mode == "add" else -amt
            ok, msg = adjust_balance(target, delta, uid, "Admin manual")
            user_states.pop(uid, None)
            if ok:
                bot.send_message(chat_id, f"✅ ব্যালেন্স আপডেট হয়েছে! নতুন ব্যালেন্স: {money(user_balance(target))}")
                bot.send_message(target, f"🔔 আপনার ওয়ালেটে <b>{'+' if delta>0 else ''}{money(delta)}</b> আপডেট হয়েছে।")
            else:
                bot.send_message(chat_id, f"⛔ ব্যর্থ: {msg}")
        except ValueError:
            bot.send_message(chat_id, "⛔ সঠিক সংখ্যা লিখুন:")

    # Broadcast
    elif step == "a_notice":
        user_states.pop(uid, None)
        with conn() as c:
            users = c.execute("SELECT id FROM users").fetchall()
        sent = 0
        for u in users:
            try:
                bot.send_message(u["id"], f"📢 <b>NOTICE:</b>\n{sep()}\n{text}")
                sent += 1
            except Exception:
                pass
        bot.send_message(chat_id, f"✅ মোট {sent} জনের কাছে নোটিশ পৌঁছেছে।")

    # Auto items import
    elif step == "as_auto_id":
        with conn() as c:
            p = c.execute("SELECT * FROM shop_products WHERE product_id=?", (text,)).fetchone()
        if not p:
            bot.send_message(chat_id, "⛔ প্রোডাক্ট পাওয়া যায়নি।")
            user_states.pop(uid, None)
            return
        st["pid"] = text
        st["step"] = "as_auto_items"
        bot.send_message(chat_id, "🤖 প্রতি লাইনে একটি করে একাউন্ট/কি দিন:")
    elif step == "as_auto_items":
        items = [ln.strip() for ln in text.splitlines() if ln.strip()]
        pid = st["pid"]
        with conn() as c:
            for it in items:
                c.execute("INSERT INTO shop_auto_items (product_id, content) VALUES (?,?)", (pid, it))
            c.execute("UPDATE shop_products SET stock=stock+? WHERE product_id=?", (len(items), pid))
        user_states.pop(uid, None)
        bot.send_message(chat_id, f"✅ মোট {len(items)} টি আইটেম যোগ হয়েছে এবং স্টক আপডেট করা হয়েছে!")

# ═══════════════════════════════════════════════════════════════════════════
# 🔘 ইনলাইন কলব্যাক কুয়েরি হ্যান্ডলার
# ═══════════════════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    uid, data = call.from_user.id, call.data
    chat_id = call.message.chat.id

    if data == "back_cats":
        bot.delete_message(chat_id, call.message.message_id)
        show_categories(chat_id)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("cat:"):
        cat = data.split(":", 1)[1]
        bot.delete_message(chat_id, call.message.message_id)
        show_category_products(chat_id, cat)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("prod_view:"):
        pid = data.split(":", 1)[1]
        bot.delete_message(chat_id, call.message.message_id)
        show_product_detail(chat_id, pid)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("cart_add:"):
        pid = data.split(":", 1)[1]
        with conn() as c:
            c.execute(
                "INSERT INTO shop_cart_items (user_id, product_id, qty) VALUES (?,?,1) "
                "ON CONFLICT(user_id, product_id) DO UPDATE SET qty=qty+1", (uid, pid)
            )
        bot.answer_callback_query(call.id, "✅ কার্টে যোগ করা হয়েছে!", show_alert=False)
        return

    if data.startswith("cart_rem:"):
        pid = data.split(":", 1)[1]
        with conn() as c:
            c.execute("DELETE FROM shop_cart_items WHERE user_id=? AND product_id=?", (uid, pid))
        bot.delete_message(chat_id, call.message.message_id)
        render_cart(chat_id, uid)
        bot.answer_callback_query(call.id)
        return

    if data == "cart_checkout":
        bot.delete_message(chat_id, call.message.message_id)
        process_checkout(chat_id, uid)
        bot.answer_callback_query(call.id)
        return

    if data == "topup_start":
        user_states[uid] = {"step": "topup_amount"}
        bot.send_message(chat_id, "💵 আপনি কত টাকা ডিপোজিট করতে চান? (সংখ্যা লিখুন):")
        bot.answer_callback_query(call.id)
        return

    # Admin Topup
    if data.startswith("adm_top_app:"):
        req_id = int(data.split(":", 1)[1])
        with conn() as c:
            req = c.execute("SELECT * FROM shop_topups WHERE id=? AND status='PENDING'", (req_id,)).fetchone()
            if not req:
                bot.answer_callback_query(call.id, "ইতিমধ্যে সম্পন্ন।")
                return
            c.execute("UPDATE shop_topups SET status='APPROVED' WHERE id=?", (req_id,))
        adjust_balance(req["user_id"], req["amount"], uid, f"Topup #{req_id}")
        bot.send_message(req["user_id"], f"✅ আপনার {money(req['amount'])} ডিপোজিট সম্পন্ন হয়েছে!")
        bot.edit_message_text(f"{call.message.text}\n\n✅ APPROVED", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "Approved!")
        return

    if data.startswith("adm_top_rej:"):
        req_id = int(data.split(":", 1)[1])
        with conn() as c:
            c.execute("UPDATE shop_topups SET status='REJECTED' WHERE id=?", (req_id,))
        bot.edit_message_text(f"{call.message.text}\n\n❌ REJECTED", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "Rejected!")
        return

def show_my_orders(chat_id, uid):
    with conn() as c:
        orders = c.execute("SELECT * FROM shop_orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,)).fetchall()
    if not orders:
        bot.send_message(chat_id, "📭 কোনো অর্ডার হিস্ট্রি নেই।")
        return
    lines = [f"📦 <b>MY RECENT ORDERS</b>\n{sep()}"]
    for o in orders:
        lines.append(
            f"🧾 <code>{o['order_id']}</code> | <b>{o['order_status']}</b>\n"
            f"💰 Total: {money(o['total'])}\n"
            f"🔑 Content: {esc(o['delivery_content']) or 'N/A'}\n"
        )
    bot.send_message(chat_id, "\n".join(lines))

# ═══════════════════════════════════════════════════════════════════════════
# 🌐 RENDER 24/7 FLASK SERVER
# ═══════════════════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Professional Shop Bot is Running on Render 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ═══════════════════════════════════════════════════════════════════════════
# 🏁 মেইন এক্সিকিউশন
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("🚀 Advanced Shop Bot is running successfully...")
    bot.infinity_polling(skip_pending=True)