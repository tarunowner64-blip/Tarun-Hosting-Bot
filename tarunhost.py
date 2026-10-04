#!/usr/bin/env python3
# ============================================================
#   24x7 Danger Hosting Bot
#   All Credit by @SAGARMODX
# ============================================================
#
#   ⚠️  WARNING: This watermark is protected.
#   Removing or changing the credit will break the bot.
#   Do NOT touch the watermark section below.
#
# ============================================================

import os, sys, subprocess, threading, time, shutil, zipfile
import tarfile, sqlite3, ast, importlib, importlib.util
import html as html_lib, logging, hashlib, base64, csv, io
import urllib.parse, urllib.request
from datetime import datetime, timedelta

# ╔══════════════════════════════════════════════════════╗
# ║           ★  CONFIGURATION — EDIT HERE  ★           ║
# ╠══════════════════════════════════════════════════════╣
# ║  Bot Token  → Get from @BotFather on Telegram       ║
BOT_TOKEN      = "8813499189:AAHbRw9Gh1gIdznrkGhA8xsd885g9ZVG_hE"
# ║                                                      ║
# ║  Admin Chat ID  → Your Telegram numeric user ID     ║
ADMIN_ID       = 8846715332
# ║                                                      ║
# ║  Channel Username  → e.g. @MyChannel                ║
CHANNEL_LINK   = "https://t.me/+P37bm7m23yJiOGVl"
# ║                                                      ║
# ║  Channel URL  → Full link shown to users            ║
CHANNEL_URL    = "https://t.me/+P37bm7m23yJiOGVl"
UPI_ID         = "tarunpandit6969@ptaxis"
# ╚══════════════════════════════════════════════════════╝
# ============================================================
#   ⚠️  WATERMARK PROTECTION — DO NOT MODIFY BELOW
#   Changing or removing this section will corrupt the bot.
# ============================================================
_WM_AUTHOR  = "SHARMAMODX"
_WM_HANDLE  = "@SHARMAJIIX9"
_WM_CREDIT  = "All Credit by @SHARMAJIIX9"
_WM_HASH    = hashlib.sha256((_WM_AUTHOR + _WM_HANDLE + _WM_CREDIT).encode()).hexdigest()
_WM_ENCODED = base64.b64encode(_WM_CREDIT.encode()).decode()

def _verify_watermark():
    """Verify watermark integrity on startup. Do NOT modify."""
    try:
        decoded  = base64.b64decode(_WM_ENCODED.encode()).decode()
        expected = _WM_AUTHOR + _WM_HANDLE + _WM_CREDIT
        chk      = hashlib.sha256(expected.encode()).hexdigest()
        if chk != _WM_HASH or decoded != _WM_CREDIT:
            raise RuntimeError("Watermark tampered")
        with open(__file__, "r", encoding="utf-8") as _f:
            _src = _f.read()
        for _key in (_WM_AUTHOR, _WM_HANDLE, _WM_CREDIT):
            if _key not in _src:
                raise RuntimeError("Watermark removed from source")
    except RuntimeError:
        import traceback, random, string
        print("\n" + "="*60)
        print("💀 FATAL ERROR: Watermark has been tampered with.")
        print("   This bot is protected by @SAGARMODX.")
        print("   Restoring original credit is required to run.")
        print("="*60 + "\n")
        # Corrupt runtime to make bot non-functional
        raise SystemExit(
            "".join(random.choices(string.ascii_letters, k=512))
        )
    except Exception:
        pass  # File read errors are non-fatal

_verify_watermark()
# ============================================================
#   END OF WATERMARK PROTECTION
# ============================================================

# Auto install required packages
def install_requirements():
    pkgs = {"pyTelegramBotAPI": "telebot", "requests": "requests", "psutil": "psutil"}
    for pkg, mod in pkgs.items():
        try:
            __import__(mod)
        except ImportError:
            print(f"📦 Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_requirements()

import psutil
import telebot
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                            ReplyKeyboardMarkup, KeyboardButton)

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Thresholds (env overridable) ─────────────────────────
CPU_THRESHOLD        = float(os.environ.get("CPU_THRESHOLD", "90.0"))
MEMORY_THRESHOLD     = float(os.environ.get("MEMORY_THRESHOLD", "90.0"))
MAX_RUNNING_PROCESSES = int(os.environ.get("MAX_RUNNING_PROCESSES", "50"))
MAX_FILES_PER_USER   = int(os.environ.get("MAX_FILES_PER_USER", "3"))

# ── Stability / Recovery Modes ────────────────────────────
AUTO_RESTART_ON_CRASH = os.environ.get("AUTO_RESTART_ON_CRASH", "1") == "1"
MAX_AUTO_RESTARTS = int(os.environ.get("MAX_AUTO_RESTARTS", "3"))
AUTO_RESTART_DELAY = int(os.environ.get("AUTO_RESTART_DELAY", "5"))
START_RETRY_COUNT = int(os.environ.get("START_RETRY_COUNT", "2"))
STALE_STATUS_CHECK = os.environ.get("STALE_STATUS_CHECK", "1") == "1"

# ── Directories ───────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
DB_PATH    = os.path.join(DATA_DIR, "metadata.db")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
LOGS_DIR   = os.path.join(DATA_DIR, "logs")
TEMP_DIR   = os.path.join(DATA_DIR, "temp")

for _d in [DATA_DIR, UPLOADS_DIR, LOGS_DIR, TEMP_DIR]:
    os.makedirs(_d, exist_ok=True)

START_TIME = datetime.utcnow()

# ── Database ──────────────────────────────────────────────
# SQLite connection: wait for temporary locks instead of failing immediately.
conn    = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60)
conn.row_factory = sqlite3.Row
db_lock = threading.RLock()

# Give SQLite a generous busy timeout. WAL also reduces read/write contention.
try:
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
except sqlite3.OperationalError as e:
    logger_msg = f"SQLite startup pragma warning: {e}"
    print(logger_msg)

def _init_db_once():
    with db_lock:
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, filename TEXT,
            orig_name TEXT, path TEXT, uploaded_at TEXT,
            file_type TEXT, pid INTEGER, status TEXT DEFAULT 'Stopped', approval_status TEXT DEFAULT 'approved',
            auto_stop_at TEXT DEFAULT NULL, db_path TEXT DEFAULT NULL
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER, started_at TEXT, finished_at TEXT,
            pid INTEGER, log_path TEXT, exit_code INTEGER
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT,
            joined_at TEXT, last_seen TEXT
        )''')
        try:
            cur.execute("ALTER TABLE users ADD COLUMN joined_channel INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE files ADD COLUMN approval_status TEXT DEFAULT 'approved'")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE files ADD COLUMN auto_stop_at TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE files ADD COLUMN db_path TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        conn.commit()

# Retry database initialization when another process/session temporarily
# holds SQLite's schema lock.
def init_db():
    last_error = None
    for attempt in range(1, 11):
        try:
            _init_db_once()
            return
        except sqlite3.OperationalError as e:
            last_error = e
            if "locked" not in str(e).lower():
                raise
            print(f"⚠️ SQLite database is locked; retry {attempt}/10...")
            time.sleep(min(2 * attempt, 10))
    raise sqlite3.OperationalError(
        f"database is still locked after 10 retries: {last_error}"
    )

init_db()

# Any process from a previous bot session is not managed by this process.
# Reset persisted RUNNING flags so the UI reflects the real current session.
with db_lock:
    conn.execute("UPDATE files SET status='Stopped', pid=NULL WHERE status='Running'")
    conn.commit()

# ── Admin Settings ────────────────────────────────────────
def init_admin_settings():
    with db_lock:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('python_approval','1')")
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('maintenance','0')")
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('premium_panel','1')")
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('max_files_per_user',?)", (str(MAX_FILES_PER_USER),))
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('how_to_use_link','https://t.me/your_channel')")
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('auto_cleanup_days','30')")
        cur.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES ('global_auto_stop_at','')")
        cur.execute("CREATE TABLE IF NOT EXISTS admin_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT, target TEXT, created_at TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, details TEXT, created_at TEXT)")
        try:
            cur.execute("ALTER TABLE users ADD COLUMN blocked INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE users ADD COLUMN max_files INTEGER DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE users ADD COLUMN auto_stop_at TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        conn.commit()

def python_approval_enabled():
    cur = conn.cursor(); cur.execute("SELECT value FROM bot_settings WHERE key='python_approval'")
    row = cur.fetchone(); return bool(row and str(row[0]) == "1")

def set_python_approval(enabled):
    with db_lock:
        conn.execute("INSERT OR REPLACE INTO bot_settings (key,value) VALUES ('python_approval',?)", ("1" if enabled else "0",))
        if not enabled:
            conn.execute("UPDATE files SET approval_status='approved' WHERE approval_status='pending'")
        conn.commit()

init_admin_settings()

# ── Premium Membership ─────────────────────────────────────
def init_premium():
    with db_lock:
        conn.execute("""CREATE TABLE IF NOT EXISTS premium_members (
            user_id INTEGER PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'Premium',
            status TEXT NOT NULL DEFAULT 'active', started_at TEXT NOT NULL,
            expires_at TEXT DEFAULT NULL)""")
        conn.commit()

def premium_row(user_id):
    try:
        row = conn.execute("SELECT * FROM premium_members WHERE user_id=?", (user_id,)).fetchone()
        if row and row["expires_at"] and row["status"] == "active":
            try: expired = datetime.fromisoformat(row["expires_at"]) <= datetime.utcnow()
            except Exception: expired = True
            if expired:
                with db_lock:
                    conn.execute("UPDATE premium_members SET status='expired' WHERE user_id=?", (user_id,))
                    conn.commit()
                row = conn.execute("SELECT * FROM premium_members WHERE user_id=?", (user_id,)).fetchone()
        return row
    except Exception:
        return None

def premium_status_text(user_id):
    row = premium_row(user_id)
    if not row or row["status"] != "active": return "FREE"
    if not row["expires_at"]: return "💎 PREMIUM • Lifetime"
    try:
        left=max(0,int((datetime.fromisoformat(row["expires_at"])-datetime.utcnow()).total_seconds()))
        d,h=divmod(left,86400)[0],divmod(divmod(left,86400)[1],3600)[0]
        return f"💎 PREMIUM • {d}d {h}h left"
    except Exception: return "💎 PREMIUM"

def grant_premium(user_id, days):
    now=datetime.utcnow()
    expires=None if days == 0 else (now+timedelta(days=days)).isoformat()
    with db_lock:
        conn.execute("""INSERT INTO premium_members(user_id,plan,status,started_at,expires_at)
                        VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                        plan=excluded.plan,status='active',started_at=excluded.started_at,
                        expires_at=excluded.expires_at""",
                     (user_id,"Premium","active",now.isoformat(),expires))
        conn.commit()
    return expires

def revoke_premium(user_id):
    with db_lock:
        conn.execute("UPDATE premium_members SET status='revoked' WHERE user_id=?", (user_id,))
        conn.commit()

def premium_menu_kb():
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💎 My Premium",callback_data="premium_status"),
           InlineKeyboardButton("✨ Benefits",callback_data="premium_benefits"))
    kb.add(InlineKeyboardButton("📅 30 Days — ₹99",callback_data="premium_plan:30"))
    kb.add(InlineKeyboardButton("🔙 Main Menu",callback_data="premium_back"))
    return kb

def premium_plans_text():
    return ("💎 <b>PREMIUM PLANS</b>\n\n"
            "📅 <b>30 Days</b> — ₹99\n\n"
            "👇 Select a plan to pay via UPI and submit your payment screenshot.")

def premium_text(user_id):
    row = premium_row(user_id)
    plan_name = (row["plan"] if row and row["status"] == "active" else "FREE")
    return ("💎 <b>PREMIUM CENTER</b>\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📦 Plan: <b>{html_lib.escape(plan_name)}</b>\n"
            f"🏷 Status: <b>{premium_status_text(user_id)}</b>\n\n"
            "✨ <b>Premium Benefits</b>\n"
            "• Premium account badge\n• Priority support\n"
            "• Premium access managed by Admin\n• Automatic expiry tracking\n\n"
            "💳 For activation, contact the owner.")

def premium_admin_menu(chat_id,message_id=None):
    active=conn.execute("SELECT COUNT(*) FROM premium_members WHERE status='active'").fetchone()[0] or 0
    expired=conn.execute("SELECT COUNT(*) FROM premium_members WHERE status='expired'").fetchone()[0] or 0
    text=(f"💎 <b>PREMIUM MANAGER</b>\n\n🟢 Active Premium: <b>{active}</b>\n"
          f"⌛ Expired: <b>{expired}</b>\n\nManage Premium access for users.")
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Grant Premium",callback_data="admin_premium_grant"),
           InlineKeyboardButton("➖ Revoke",callback_data="admin_premium_revoke"))
    kb.add(InlineKeyboardButton("👑 Premium Users",callback_data="admin_premium_users"))
    kb.add(InlineKeyboardButton("🔙 Back",callback_data="admin_back"))
    _edit_or_send(chat_id,message_id,text,kb)

def premium_users_list(chat_id,message_id=None):
    rows=conn.execute("SELECT user_id,status,expires_at FROM premium_members ORDER BY user_id DESC LIMIT 100").fetchall()
    text="💎 <b>PREMIUM USERS</b>\n\n"
    text += "\n".join(f"{'🟢' if r['status']=='active' else '⚪'} <code>{r['user_id']}</code> — {r['status'].upper()} — {'Lifetime' if not r['expires_at'] else r['expires_at'][:19]+' UTC'}" for r in rows) or "No Premium users yet."
    kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔙 Premium Manager",callback_data="admin_premium_manager"))
    _edit_or_send(chat_id,message_id,text,kb)

init_premium()

# ── Premium Payment Requests ───────────────────────────────
def init_premium_payments():
    with db_lock:
        conn.execute("""CREATE TABLE IF NOT EXISTS premium_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_days INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            screenshot_file_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT DEFAULT NULL
        )""")
        conn.commit()

init_premium_payments()
pending_premium_plan = {}

PREMIUM_PLANS = {
    30: 99,
}

def premium_plan_text(days):
    amount = PREMIUM_PLANS[days]
    return f"📅 <b>{days} Days Premium</b> — ₹{amount}"

def premium_payment_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📅 30 Days — ₹99", callback_data="premium_plan:30"))
    kb.add(InlineKeyboardButton("🔙 Premium", callback_data="premium_status"))
    return kb

def premium_upi_link(days):
    amount = PREMIUM_PLANS[days]
    params = {
        "pa": UPI_ID,
        "pn": "TARUN PANEL SELLING",
        "am": f"{amount:.2f}",
        "cu": "INR",
    }
    return "upi://pay?" + urllib.parse.urlencode(params)

def send_premium_qr(chat_id, days):
    amount = PREMIUM_PLANS[days]
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?" + urllib.parse.urlencode({
        "size": "500x500",
        "data": premium_upi_link(days),
    })
    try:
        with urllib.request.urlopen(qr_url, timeout=15) as response:
            qr_data = response.read()
        caption = (
            f"💎 <b>{days} DAYS PREMIUM</b>\n\n"
            f"💰 Amount: <b>₹{amount}</b>\n"
            f"📲 UPI ID: <code>{html_lib.escape(UPI_ID)}</code>\n\n"
            "📷 <b>Scan this QR to pay.</b>\n"
            "After payment, send the payment screenshot here.\n\n"
            "⚠️ Do not send your UPI PIN, OTP, or password."
        )
        bot.send_photo(chat_id, io.BytesIO(qr_data), caption=caption)
        return True
    except Exception:
        logger.exception("Premium QR generation failed")
        bot.send_message(
            chat_id,
            f"⚠️ QR generate नहीं हो पाया.\n\n📲 UPI ID: <code>{html_lib.escape(UPI_ID)}</code>\n"
            f"💰 Amount: <b>₹{amount}</b>\n\n"
            "इस UPI ID पर payment करें और screenshot भेजें."
        )
        return False

def premium_payment_request_text(days):
    amount = PREMIUM_PLANS[days]
    return (f"💎 <b>{days} DAYS PREMIUM</b>\n\n"
            f"💰 Amount: <b>₹{amount}</b>\n"
            f"📲 UPI ID: <code>{html_lib.escape(UPI_ID)}</code>\n\n"
            "📷 QR ऊपर भेजा जाएगा — scan करके payment करें.\n"
            "1️⃣ Pay exactly the amount shown.\n"
            "2️⃣ After payment, send the <b>payment screenshot</b> here.\n"
            "3️⃣ Admin will verify it.\n"
            f"4️⃣ After approval, Premium will be activated for <b>{days} days</b>.\n\n"
            "⚠️ Do not send your UPI PIN, OTP, or password.")

def create_premium_payment(user_id, days, screenshot_file_id):
    amount = PREMIUM_PLANS[days]
    with db_lock:
        cur = conn.cursor()
        cur.execute("""INSERT INTO premium_payments
            (user_id,plan_days,amount,screenshot_file_id,status,created_at)
            VALUES (?,?,?,?,?,?)""", (user_id,days,amount,screenshot_file_id,'pending',datetime.utcnow().isoformat()))
        conn.commit()
        return cur.lastrowid

def get_pending_payment(payment_id):
    return conn.execute("SELECT * FROM premium_payments WHERE id=?", (payment_id,)).fetchone()

def get_setting(key, default=None):
    try:
        cur = conn.cursor(); cur.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else default
    except Exception:
        return default

def set_setting(key, value):
    with db_lock:
        conn.execute("INSERT OR REPLACE INTO bot_settings (key,value) VALUES (?,?)", (key, str(value)))
        conn.commit()

def maintenance_enabled():
    return str(get_setting('maintenance','0')) == '1'

def premium_panel_enabled():
    return str(get_setting('premium_panel','1')) == '1'

def set_premium_panel_enabled(enabled):
    set_setting('premium_panel', '1' if enabled else '0')

def effective_max_files():
    try: return max(1, int(get_setting('max_files_per_user', MAX_FILES_PER_USER)))
    except Exception: return MAX_FILES_PER_USER

def effective_user_max_files(user_id):
    """Return this user's custom upload limit, or the global limit when not customized."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT max_files FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row["max_files"] is not None:
            return max(1, int(row["max_files"]))
    except Exception:
        pass
    return effective_max_files()

def set_user_max_files(user_id, limit):
    """Set a per-user upload limit. Use None to return the user to the global limit."""
    with db_lock:
        conn.execute("UPDATE users SET max_files=? WHERE user_id=?", (limit, user_id))
        conn.commit()

def log_admin(action, target=''):
    try:
        with db_lock:
            conn.execute("INSERT INTO admin_logs(admin_id,action,target,created_at) VALUES (?,?,?,?)", (ADMIN_ID, action, str(target), datetime.utcnow().isoformat()))
            conn.commit()
    except Exception: pass

def log_activity(user_id, action, details=''):
    try:
        with db_lock:
            conn.execute("INSERT INTO activity_logs(user_id,action,details,created_at) VALUES (?,?,?,?)", (user_id, action, str(details), datetime.utcnow().isoformat()))
            conn.commit()
    except Exception: pass

# ── DB Helpers ────────────────────────────────────────────
def add_file_record(user_id, username, filename, orig_name, path, file_type):
    with db_lock:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO files (user_id,username,filename,orig_name,path,uploaded_at,file_type) VALUES (?,?,?,?,?,?,?)",
            (user_id, username, filename, orig_name, path, datetime.utcnow().isoformat(), file_type)
        )
        conn.commit()
        return cur.lastrowid

def list_user_files(user_id):
    cur = conn.cursor()
    cur.execute("SELECT id,filename,orig_name,uploaded_at,file_type,status,pid FROM files WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    # UI status must come from the live process registry, not stale DB values.
    result = []
    with proc_lock:
        for row in rows:
            running = False
            entry = processes.get(row[0])
            if entry:
                try:
                    running = entry['process'].poll() is None
                except Exception:
                    running = False
            result.append((row[0], row[1], row[2], row[3], row[4],
                           'Running' if running else 'Stopped',
                           row[6] if running else None))
    return result

def is_file_running(file_id):
    """Return the real runtime state for a file; never trust a stale DB flag."""
    with proc_lock:
        entry = processes.get(file_id)
        if not entry:
            return False
        try:
            if entry['process'].poll() is None:
                return True
        except Exception:
            pass
        return False

def get_file_record(file_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=?", (file_id,))
    return cur.fetchone()

def remove_file_record(file_id):
    with db_lock:
        cur = conn.cursor()
        cur.execute("DELETE FROM files WHERE id=?", (file_id,))
        conn.commit()

def record_run_start(file_id, pid, log_path):
    with db_lock:
        cur = conn.cursor()
        cur.execute("INSERT INTO runs (file_id,started_at,pid,log_path) VALUES (?,?,?,?)",
                    (file_id, datetime.utcnow().isoformat(), pid, log_path))
        conn.commit()
        return cur.lastrowid

def record_run_finish(run_id, exit_code):
    with db_lock:
        cur = conn.cursor()
        cur.execute("UPDATE runs SET finished_at=?,exit_code=? WHERE id=?",
                    (datetime.utcnow().isoformat(), exit_code, run_id))
        conn.commit()

def update_file_status(file_id, pid, status):
    with db_lock:
        cur = conn.cursor()
        cur.execute("UPDATE files SET pid=?,status=? WHERE id=?", (pid, status, file_id))
        conn.commit()

def update_user_joined(user_id, joined):
    with db_lock:
        cur = conn.cursor()
        cur.execute("UPDATE users SET joined_channel=? WHERE user_id=?", (1 if joined else 0, user_id))
        conn.commit()

# ── Access Check ───────────────────────────────────────────
def require_join(func):
    # Channel join verification disabled: users can use the bot directly.
    return func

# ── Process Store ─────────────────────────────────────────
processes = {}
proc_lock = threading.Lock()

# Crash-recovery counters are kept in memory and reset after a successful
# manual start. They prevent endless restart loops for broken projects.
auto_restart_counts = {}
auto_restart_lock = threading.Lock()

# Project names entered through 📤 Upload File. The name is applied to
# the very next document uploaded by that user.
pending_upload_names = {}

# ── System Monitoring ─────────────────────────────────────
def get_system_load():
    try:
        return float(psutil.cpu_percent(interval=0.1)), float(psutil.virtual_memory().percent), len(processes)
    except Exception:
        return 0.0, 0.0, 0

def should_stop_due_to_load():
    cpu, mem, cnt = get_system_load()
    if cnt >= MAX_RUNNING_PROCESSES:
        return True, f"Too many running processes ({cnt}/{MAX_RUNNING_PROCESSES})"
    if cpu >= CPU_THRESHOLD:
        return True, f"High CPU load ({cpu}%)"
    if mem >= MEMORY_THRESHOLD:
        return True, f"High memory usage ({mem}%)"
    return False, None

# ── File Utilities ────────────────────────────────────────
def get_file_type(filename):
    if not filename: return "unknown"
    n = filename.lower()
    if n.endswith(".py"):   return "python"
    if n.endswith(".js"):   return "javascript"
    if n.endswith(".zip"):  return "zip"
    if any(n.endswith(e) for e in [".tar", ".tar.gz", ".tgz"]): return "archive"
    return "unknown"

def extract_archive(file_path, extract_dir):
    try:
        if file_path.lower().endswith(".zip"):
            with zipfile.ZipFile(file_path, 'r') as z: z.extractall(extract_dir)
        elif file_path.lower().endswith((".tar.gz", ".tgz")):
            with tarfile.open(file_path, 'r:gz') as t: t.extractall(extract_dir)
        elif file_path.lower().endswith(".tar"):
            with tarfile.open(file_path, 'r') as t: t.extractall(extract_dir)
        else:
            return False, "Unsupported archive format"
        return True, None
    except Exception as e:
        return False, str(e)

def find_main_file(directory):
    priority = ["main.py","bot.py","app.py","server.py","index.py","script.py",
                "main.js","bot.js","app.js","server.js","index.js","script.js"]
    for f in priority:
        p = os.path.join(directory, f)
        if os.path.isfile(p): return p
    for root, _, files in os.walk(directory):
        for f in priority:
            if f in files: return os.path.join(root, f)
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith((".py", ".js")): return os.path.join(root, f)
    return None

def install_requirements_from_file(req_path, chat_id, file_name):
    if not os.path.exists(req_path): return False, "requirements.txt not found"
    with open(req_path) as f:
        reqs = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    if not reqs: return True, "No requirements"
    ok, fail, failed = 0, 0, []
    for pkg in reqs:
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0: ok += 1
            else: fail += 1; failed.append(pkg)
        except Exception as e:
            fail += 1; failed.append(f"{pkg} ({e})")
    msg = f"Installed {ok} packages"
    if fail: msg += f", failed {fail}: {', '.join(failed[:5])}"
    return fail == 0, msg

def extract_imports(file_path):
    imports = set()
    try:
        with open(file_path, encoding='utf-8') as f: content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names: imports.add(a.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0: imports.add(node.module.split('.')[0])
    except Exception as e:
        logger.error(f"Import parse error: {e}")
    return imports

def install_missing_imports(imports, chat_id, file_name):
    pip_map = {'telebot':'pyTelegramBotAPI','PIL':'Pillow','cv2':'opencv-python',
               'Crypto':'pycryptodome','bs4':'beautifulsoup4'}
    missing = [m for m in imports if not importlib.util.find_spec(m)]
    if not missing: return True, "All imports available"
    ok, fail, failed = 0, 0, []
    for mod in missing:
        pkg = pip_map.get(mod, mod)
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0: ok += 1
            else: fail += 1; failed.append(mod)
        except Exception as e:
            fail += 1; failed.append(mod)
    msg = f"Installed {ok} modules"
    if fail: msg += f", failed {fail}: {', '.join(failed)}"
    return fail == 0, msg

# ── Bot Instance ──────────────────────────────────────────
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ── Keyboards ─────────────────────────────────────────────
def user_feature_center_text(user_id):
    premium = premium_is_active(user_id)
    return ("🧩 <b>HOSTING FEATURE CENTER</b>\n\n"
            "📁 <b>Project Management</b>\n"
            "• Upload / Download / Delete\n"
            "• Start / Stop / Restart\n"
            "• Change Main File\n"
            "• Database upload / download\n\n"
            "🛡️ <b>Reliability</b>\n"
            "• Auto-Recovery / Watchdog\n"
            "• Crash detection & restart history\n"
            "• Server-restart recovery\n"
            "• CPU / RAM protection\n\n"
            "📊 <b>Monitoring</b>\n"
            "• Live status / PID / uptime\n"
            "• Bot speed / system usage\n"
            "• Logs / activity history\n\n"
            "💎 <b>Premium</b>: " + ("🟢 Active — Premium tools unlocked" if premium else "🔒 Upgrade to unlock Premium tools"))

def user_feature_center_kb(user_id):
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📁 My Projects",callback_data="back_to_files"),
           InlineKeyboardButton("⚡ Bot Speed",callback_data="feature_speed"))
    kb.add(InlineKeyboardButton("📊 Statistics",callback_data="feature_stats"),
           InlineKeyboardButton("🧾 Activity",callback_data="feature_activity"))
    if premium_is_active(user_id):
        kb.add(InlineKeyboardButton("💎 Premium Control Center",callback_data="premium_hub"),
               InlineKeyboardButton("🛡️ Reliability",callback_data="premium_features"))
    else:
        kb.add(InlineKeyboardButton("💎 Premium Plans",callback_data="premium_plans"))
    kb.add(InlineKeyboardButton("🔙 Main Menu",callback_data="back_to_main"))
    return kb

def admin_feature_center_text():
    return ("🧩 <b>ADMIN FEATURE CONTROL CENTER</b>\n\n"
            "👥 <b>User & Premium</b>\n"
            "• User Manager / Search / Block\n"
            "• Premium users / Grant / Revoke\n"
            "• Plan & Premium-panel controls\n\n"
            "🖥️ <b>Hosting Control</b>\n"
            "• Running processes / Start All / Stop All\n"
            "• 50 concurrent-process ceiling\n"
            "• Auto Stop / Maintenance\n"
            "• Python approval / Pending queue\n\n"
            "🛡️ <b>Reliability & Security</b>\n"
            "• Health Check / Watchdog monitoring\n"
            "• CPU / RAM / Disk protection\n"
            "• Crash & run history / cleanup\n\n"
            "📊 <b>Operations</b>\n"
            "• Analytics / Broadcast / User messaging\n"
            "• Logs / DB Manager / Backups\n"
            "• Export / How-To link / System status")

def admin_feature_center_kb():
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📊 Dashboard",callback_data="admin_dashboard"),
           InlineKeyboardButton("🖥️ Processes",callback_data="admin_processes"))
    kb.add(InlineKeyboardButton("🩺 Health Check",callback_data="admin_health_check"),
           InlineKeyboardButton("🖥️ System Status",callback_data="admin_system"))
    kb.add(InlineKeyboardButton("💎 Premium Manager",callback_data="admin_premium_manager"),
           InlineKeyboardButton("⚙️ Settings",callback_data="admin_settings"))
    kb.add(InlineKeyboardButton("🧹 Cleanup",callback_data="admin_cleanup"),
           InlineKeyboardButton("💾 DB Backup",callback_data="admin_backup"))
    kb.add(InlineKeyboardButton("🔙 Admin Panel",callback_data="admin_back"))
    return kb

def main_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📢 Updates Channel"))
    kb.add(KeyboardButton("📤 Upload File"), KeyboardButton("📁 My Files"))
    kb.add(KeyboardButton("📖 How To Use Bot"))
    kb.add(KeyboardButton("⚡ Bot Speed"), KeyboardButton("📊 Statistics"))
    kb.add(KeyboardButton("🧩 Feature Center"))
    kb.add(KeyboardButton("📞 Contact Owner"))
    kb.add(KeyboardButton("👤 My Profile"), KeyboardButton("🧾 My Activity"))
    if premium_panel_enabled():
        kb.add(KeyboardButton("👑 Premium Hub"))
        kb.add(KeyboardButton("💎 Premium"))
    return kb

def admin_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard"), InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics"))
    kb.add(InlineKeyboardButton("🔎 Search User", callback_data="admin_search_user"), InlineKeyboardButton("👥 User Manager", callback_data="admin_manage_users"))
    kb.add(InlineKeyboardButton("📁 File Manager", callback_data="admin_manage_files"), InlineKeyboardButton("📦 Export Users", callback_data="admin_export_users"))
    kb.add(InlineKeyboardButton("🖥️ Processes", callback_data="admin_processes"), InlineKeyboardButton("⚡ Process On", callback_data="admin_process_on"))
    kb.add(InlineKeyboardButton("⏰ Auto Stop", callback_data="admin_auto_stop_menu"))
    kb.add(InlineKeyboardButton("📢 Advanced Broadcast", callback_data="admin_broadcast_menu"), InlineKeyboardButton("💬 Message User", callback_data="admin_message_user"))
    kb.add(InlineKeyboardButton("🗄️ DB Manager", callback_data="admin_db_manager"), InlineKeyboardButton("💾 DB Backup", callback_data="admin_backup"))
    kb.add(InlineKeyboardButton("👑 User Fills Set", callback_data="admin_user_files_set_menu"))
    kb.add(InlineKeyboardButton("💎 Premium Manager", callback_data="admin_premium_manager"))
    kb.add(InlineKeyboardButton("📖 Set How To Use Link", callback_data="admin_set_how_to_use"), InlineKeyboardButton("🧹 Cleanup", callback_data="admin_cleanup"))
    kb.add(InlineKeyboardButton("📜 Admin Logs", callback_data="admin_logs"), InlineKeyboardButton("🖥️ System Status", callback_data="admin_system"))
    kb.add(InlineKeyboardButton("🩺 Health Check", callback_data="admin_health_check"), InlineKeyboardButton("📋 Pending Queue", callback_data="admin_pending_queue"))
    kb.add(InlineKeyboardButton("🧩 Feature Control Center", callback_data="admin_feature_center"))
    kb.add(InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("🐍 Python Approval: " + ("ON 🟢" if python_approval_enabled() else "OFF 🔴"), callback_data="admin_python_approval_off" if python_approval_enabled() else "admin_python_approval_on"))
    kb.add(InlineKeyboardButton("❌ Exit Admin", callback_data="admin_exit"))
    return kb
def file_actions_kb(file_id, is_running=False):
    kb = InlineKeyboardMarkup()
    if is_running:
        kb.row(InlineKeyboardButton("⏹ Stop",    callback_data=f"stop:{file_id}"),
               InlineKeyboardButton("🔁 Restart", callback_data=f"restart:{file_id}"))
    else:
        kb.row(InlineKeyboardButton("▶️ Start",   callback_data=f"start:{file_id}"),
               InlineKeyboardButton("🔁 Restart", callback_data=f"restart:{file_id}"))
    kb.row(
        InlineKeyboardButton("🗑 Delete",   callback_data=f"delete:{file_id}"),
        InlineKeyboardButton("📄 Logs",     callback_data=f"logs:{file_id}"),
        InlineKeyboardButton("⬇️ Download", callback_data=f"download:{file_id}")
    )
    kb.row(
        InlineKeyboardButton("🗄️ Upload .db", callback_data=f"upload_db:{file_id}"),
        InlineKeyboardButton("📥 Download .db", callback_data=f"download_db:{file_id}")
    )
    kb.row(InlineKeyboardButton("✏️ Change Main File", callback_data=f"change_main_file:{file_id}"))
    kb.row(InlineKeyboardButton("⬅️ Back", callback_data="back_to_files"))
    return kb

# ── Handlers ──────────────────────────────────────────────
@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    user = message.from_user
    user_id = user.id
    if user_id != ADMIN_ID and maintenance_enabled():
        bot.send_message(message.chat.id, "🛠️ <b>Maintenance Mode</b>\n\nBot is temporarily under maintenance. Please try again later.")
        return
    if user_id != ADMIN_ID:
        cur = conn.cursor(); cur.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            bot.send_message(message.chat.id, "🚫 <b>You are blocked by Admin.</b>\n\nYou cannot use this bot.")
            return
    with db_lock:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """INSERT INTO users (user_id,username,joined_at,last_seen)
               VALUES (?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                   username=excluded.username,
                   last_seen=excluded.last_seen""",
            (user_id, user.username or "", now, now)
        )
        conn.commit()

    file_count = len(list_user_files(user_id))
    max_files = effective_user_max_files(user_id)
    premium_row_data = premium_row(user_id)
    is_premium = bool(premium_row_data and premium_row_data["status"] == "active")
    rank_text = "💎 Premium User" if is_premium else "🆓 Free User"
    if is_premium:
        if premium_row_data["expires_at"]:
            try:
                expiry_text = datetime.fromisoformat(premium_row_data["expires_at"]).strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                expiry_text = "Active"
        else:
            expiry_text = "Lifetime"
    else:
        expiry_text = "Not Active"
    display_name = user.first_name or user.username or "User"
    bot.send_message(message.chat.id, f"""
🚀 🔥 <b>24x7 Danger Hosting Bot</b>
<i>All Credit by @SHARMAJIIX9</i>
━━━━━━━━━━━━━━━━━━━━

👋 Hey <b>{html_lib.escape(display_name)}</b> !! 🤝, welcome back!

━━━━━━━━━━━━━━━━━━━━
🆔 <b>ID:</b> <code>{user_id}</code>
🟢 <b>Username:</b> @{html_lib.escape(user.username or 'Not Set')}
🏆 <b>Rank:</b> {rank_text}
📅 <b>Subscription expires:</b> {html_lib.escape(expiry_text)}
📁 <b>Projects:</b> {file_count} / {max_files}
━━━━━━━━━━━━━━━━━━━━

⚡ <b>What can I do for you?</b>
› Upload .py / .js scripts or .zip archives
› Run &amp; manage your bots 24/7
› Auto-install missing packages

👇 <b>Tap a button below to get started!</b>
    """, reply_markup=main_menu_kb())

@bot.message_handler(func=lambda m: (m.text or '').strip() == '👑 Premium Hub')
def premium_hub_handler(message):
    uid=message.from_user.id
    if not premium_panel_enabled():
        bot.send_message(message.chat.id, '💎 <b>Premium panel is currently hidden by Admin.</b>')
        return
    bot.send_message(message.chat.id,premium_hub_text(uid),reply_markup=premium_hub_kb(uid))

@bot.message_handler(commands=['premium'])
def premium_command(message):
    if not premium_panel_enabled():
        bot.send_message(message.chat.id, '💎 <b>Premium panel is currently hidden by Admin.</b>')
        return
    bot.send_message(message.chat.id,premium_text(message.from_user.id),reply_markup=premium_menu_kb())

@bot.message_handler(func=lambda m: (m.text or '').strip() == '💎 Premium')
def premium_button_handler(message):
    if not premium_panel_enabled():
        return
    bot.send_message(message.chat.id,premium_text(message.from_user.id),reply_markup=premium_menu_kb())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Not authorized.")
        return
    msg = bot.reply_to(message, "🔐 Enter the admin password:")
    bot.register_next_step_handler(msg, check_admin_password)

def check_admin_password(message):
    if message.text == "tarun":
        bot.send_message(message.chat.id, "✅ Access granted. Welcome to Admin Panel.",
                         reply_markup=admin_panel_kb())
    else:
        bot.reply_to(message, "❌ Incorrect password.")

def how_to_use_link():
    return str(get_setting('how_to_use_link', 'https://t.me/your_channel') or '').strip()

def admin_user_files_set_receive(message, uid):
    if (message.text or '').strip() == '/cancel':
        bot.send_message(message.chat.id, '❌ Cancelled.', reply_markup=admin_panel_kb())
        return
    raw = (message.text or '').strip()
    try:
        n = int(raw)
        if not 1 <= n <= 500:
            raise ValueError
        set_user_max_files(uid, n)
        log_admin('user_max_files', f'user={uid},limit={n}')
        bot.send_message(
            message.chat.id,
            f'✅ <b>User Fills Set</b> updated.\n\n👤 User ID: <code>{uid}</code>\n📁 Upload limit: <b>{n} files</b>',
            reply_markup=admin_panel_kb()
        )
    except Exception:
        bot.send_message(message.chat.id, '❌ Invalid value. Enter a number from 1 to 500, or /cancel.')

def admin_set_how_to_use_link_receive(message):
    if (message.text or '').strip() == '/cancel':
        bot.send_message(message.chat.id, '❌ Cancelled.', reply_markup=admin_panel_kb())
        return
    link = (message.text or '').strip()
    if not (link.startswith('https://') or link.startswith('http://') or link.startswith('tg://')):
        bot.send_message(message.chat.id, '❌ Invalid link. Send a full URL, for example: https://t.me/yourchannel')
        return
    set_setting('how_to_use_link', link)
    log_admin('how_to_use_link', link)
    bot.send_message(message.chat.id, f'✅ How To Use link updated:\n{html_lib.escape(link)}', reply_markup=admin_panel_kb())

def admin_set_max_files_receive(message):
    if (message.text or '').strip() == '/cancel': bot.send_message(message.chat.id,'❌ Cancelled.'); return
    try:
        n=int((message.text or '').strip())
        if not 1 <= n <= 500: raise ValueError
        set_setting('max_files_per_user',n); log_admin('max_files_per_user',n)
        bot.send_message(message.chat.id,f'✅ Max files per user set to <b>{n}</b>.',reply_markup=admin_panel_kb())
    except Exception: bot.send_message(message.chat.id,'❌ Invalid value. Enter a number from 1 to 500.')

# ── Advanced Admin Helpers ─────────────────────────────────
def admin_dashboard_text():
    cur=conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users"); total=cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM users WHERE blocked=1"); blocked=cur.fetchone()[0] or 0
    cutoff=(datetime.utcnow()-timedelta(hours=24)).isoformat()
    cur.execute("SELECT COUNT(*) FROM users WHERE last_seen>=?",(cutoff,)); active=cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM files"); files=cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM files WHERE approval_status='pending'"); pending=cur.fetchone()[0] or 0
    running=sum(1 for fid in list_process_ids() if is_file_running(fid))
    cpu,mem,_=get_system_load(); up=datetime.utcnow()-START_TIME
    return (f"🚀 <b>ADVANCED ADMIN DASHBOARD</b>\n\n👥 Users: <b>{total}</b>\n🟢 Active 24h: <b>{active}</b>\n🚫 Blocked: <b>{blocked}</b>\n📁 Files: <b>{files}</b>\n🟢 Running: <b>{running}</b>\n⏳ Pending Python: <b>{pending}</b>\n⚡ CPU: <b>{cpu:.1f}%</b>\n💾 RAM: <b>{mem:.1f}%</b>\n⏱ Uptime: <b>{up.days}d {up.seconds//3600}h {(up.seconds%3600)//60}m</b>\n🛡 Maintenance: <b>{'ON' if maintenance_enabled() else 'OFF'}</b>")

def list_process_ids():
    with proc_lock: return list(processes.keys())

def admin_analytics_text():
    cur=conn.cursor(); now=datetime.utcnow()
    periods=[('24h',now-timedelta(hours=24)),('7d',now-timedelta(days=7)),('30d',now-timedelta(days=30))]
    out=['📈 <b>BOT ANALYTICS</b>','']
    for label,dt in periods:
        iso=dt.isoformat()
        cur.execute("SELECT COUNT(*) FROM users WHERE joined_at>=?",(iso,)); joins=cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM activity_logs WHERE created_at>=?",(iso,)); acts=cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM files WHERE uploaded_at>=?",(iso,)); uploads=cur.fetchone()[0] or 0
        out.append(f"📅 <b>{label}</b> — New Users: {joins} | Uploads: {uploads} | Actions: {acts}")
    cur.execute("SELECT action,COUNT(*) c FROM activity_logs GROUP BY action ORDER BY c DESC LIMIT 8")
    rows=cur.fetchall(); out += ['', '🔥 <b>Top Activities</b>']
    out += [f"• {html_lib.escape(r['action'])}: {r['c']}" for r in rows] or ['• No activity yet']
    return '\n'.join(out)

def admin_search_user_result(chat_id, query):
    q=(query or '').strip().lstrip('@')
    cur=conn.cursor()
    if q.isdigit(): cur.execute("SELECT * FROM users WHERE user_id=?",(int(q),))
    else: cur.execute("SELECT * FROM users WHERE username LIKE ? ORDER BY last_seen DESC LIMIT 10",('%'+q+'%',))
    rows=cur.fetchall()
    if not rows: bot.send_message(chat_id,'❌ User not found.'); return
    kb=InlineKeyboardMarkup(row_width=1)
    text='🔎 <b>SEARCH RESULTS</b>\n\n'
    for u in rows:
        name=html_lib.escape(u['username'] or str(u['user_id']))
        text+=f"👤 <b>{name}</b> — <code>{u['user_id']}</code> — {'🚫 Blocked' if u['blocked'] else '🟢 Active'}\n"
        kb.add(InlineKeyboardButton(f"👤 Open {name[:20]}",callback_data=f"admin_profile:{u['user_id']}"))
    kb.add(InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
    bot.send_message(chat_id,text,reply_markup=kb)

def admin_user_files_set_menu(chat_id, page=0, message_id=None):
    """Dedicated admin menu for setting an individual user's upload limit."""
    cur = conn.cursor()
    cur.execute("SELECT user_id,username,max_files FROM users ORDER BY user_id")
    users = cur.fetchall()
    per_page = 20
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_users = users[page * per_page:(page + 1) * per_page]

    text = f"👑 <b>User Fills Set</b> — Page {page + 1}/{total_pages}\\n\\n"
    text += "Select a user to set their maximum upload files (1-500).\\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for u in page_users:
        uid = u["user_id"]
        name = html_lib.escape(u["username"] or str(uid))
        current = u["max_files"] if u["max_files"] is not None else effective_max_files()
        text += f"👤 <b>{name}</b> — Limit: <b>{current}</b>\\n"
        kb.add(InlineKeyboardButton(
            f"👑 SET • {name[:20]}",
            callback_data=f"admin_user_files_set:{uid}"
        ))
    if page > 0:
        kb.add(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_user_files_set_page:{page-1}"))
    if page < total_pages - 1:
        kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"admin_user_files_set_page:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    _edit_or_send(chat_id, message_id, text, kb)

def parse_duration(text):
    """Parse e.g. '30 minutes', '2 hours', '1 day'. Returns seconds."""
    raw = (text or '').strip().lower()
    if raw == '/cancel':
        return None
    import re
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)', raw)
    if not m:
        raise ValueError("Use e.g. 30 minutes, 2 hours, or 1 day.")
    value = float(m.group(1)); unit = m.group(2)
    if value <= 0: raise ValueError("Duration must be greater than 0.")
    if unit.startswith('m'): seconds = value * 60
    elif unit.startswith('h'): seconds = value * 3600
    else: seconds = value * 86400
    if seconds > 365 * 86400: raise ValueError("Maximum duration is 365 days.")
    return int(seconds)

def format_deadline(iso_value):
    try:
        dt = datetime.fromisoformat(str(iso_value))
        now = datetime.utcnow()
        remaining = max(0, int((dt - now).total_seconds()))
        if remaining <= 0: return 'Expired'
        d, rem = divmod(remaining, 86400); h, rem = divmod(rem, 3600); m, _ = divmod(rem, 60)
        parts=[]
        if d: parts.append(f'{d}d')
        if h: parts.append(f'{h}h')
        if m and not d: parts.append(f'{m}m')
        return f"{', '.join(parts) or '<1m'} left • {dt.strftime('%Y-%m-%d %H:%M UTC')}"
    except Exception:
        return 'OFF'

def set_user_auto_stop(uid, seconds):
    deadline = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
    with db_lock:
        conn.execute("UPDATE users SET auto_stop_at=? WHERE user_id=?", (deadline, uid)); conn.commit()
    return deadline

def clear_user_auto_stop(uid):
    with db_lock:
        conn.execute("UPDATE users SET auto_stop_at=NULL WHERE user_id=?", (uid,)); conn.commit()

def set_user_files_auto_stop(uid, seconds):
    """Set the same one-time auto-stop deadline on every file belonging to a user."""
    deadline = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
    with db_lock:
        conn.execute("UPDATE files SET auto_stop_at=? WHERE user_id=?", (deadline, uid))
        conn.commit()
    return deadline

def clear_user_files_auto_stop(uid):
    with db_lock:
        conn.execute("UPDATE files SET auto_stop_at=NULL WHERE user_id=?", (uid,))
        conn.commit()

def set_file_auto_stop(file_id, seconds):
    deadline = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
    with db_lock:
        conn.execute("UPDATE files SET auto_stop_at=? WHERE id=?", (deadline, file_id))
        conn.commit()
    return deadline

def clear_file_auto_stop(file_id):
    with db_lock:
        conn.execute("UPDATE files SET auto_stop_at=NULL WHERE id=?", (file_id,))
        conn.commit()

def set_global_auto_stop(seconds):
    deadline = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
    set_setting('global_auto_stop_at', deadline)
    return deadline

def clear_global_auto_stop():
    set_setting('global_auto_stop_at', '')

def auto_stop_all_running(reason='Global auto-stop'):
    cur=conn.cursor(); cur.execute("SELECT id FROM files")
    stopped=0
    for row in cur.fetchall():
        fid=row['id']
        if is_file_running(fid):
            try: stop_file_process(fid); stopped += 1
            except Exception: logger.exception('Auto-stop failed for file %s', fid)
    return stopped

def auto_stop_user_running(uid):
    cur=conn.cursor(); cur.execute("SELECT id FROM files WHERE user_id=?", (uid,))
    stopped=0
    for row in cur.fetchall():
        if is_file_running(row['id']):
            try: stop_file_process(row['id']); stopped += 1
            except Exception: logger.exception('User auto-stop failed for file %s', row['id'])
    return stopped

def auto_stop_worker():
    """Background one-shot scheduler for global and per-user auto-stop deadlines."""
    while True:
        try:
            now = datetime.utcnow()
            global_at = get_setting('global_auto_stop_at', '')
            if global_at:
                try:
                    if datetime.fromisoformat(global_at) <= now:
                        stopped = auto_stop_all_running()
                        clear_global_auto_stop()
                        log_admin('global_auto_stop', f'stopped={stopped}')
                        try: bot.send_message(ADMIN_ID, f'⏰ <b>Global Auto Stop completed.</b>\n\n🛑 Files stopped: <b>{stopped}</b>\n\nUsers can start their files again manually.')
                        except Exception: pass
                except Exception: clear_global_auto_stop()
            cur=conn.cursor(); cur.execute("SELECT user_id,auto_stop_at FROM users WHERE auto_stop_at IS NOT NULL AND auto_stop_at!=''")
            expired=[]
            for r in cur.fetchall():
                try:
                    if datetime.fromisoformat(r['auto_stop_at']) <= now: expired.append(r['user_id'])
                except Exception:
                    expired.append(r['user_id'])
            for uid in expired:
                stopped=auto_stop_user_running(uid)
                clear_user_auto_stop(uid)
                log_admin('user_auto_stop', f'user={uid},stopped={stopped}')
                try: bot.send_message(uid, f'⏰ <b>Auto Stop completed.</b>\n\n🛑 Your running files were stopped automatically.\n\n▶️ You can start your files again from 📁 My Files.')
                except Exception: pass
            # Per-file deadlines: every file can have its own timer.
            cur=conn.cursor()
            cur.execute("SELECT id,user_id,orig_name,auto_stop_at FROM files WHERE auto_stop_at IS NOT NULL AND auto_stop_at!=''")
            expired_files=[]
            for r in cur.fetchall():
                try:
                    if datetime.fromisoformat(r['auto_stop_at']) <= now:
                        expired_files.append(r)
                except Exception:
                    expired_files.append(r)
            for r in expired_files:
                fid = r['id']
                uid = r['user_id']
                stopped = 0
                if is_file_running(fid):
                    try:
                        stop_file_process(fid)
                        stopped = 1
                    except Exception:
                        logger.exception('File auto-stop failed for file %s', fid)
                clear_file_auto_stop(fid)
                log_admin('file_auto_stop', f'file={fid},user={uid},stopped={stopped}')
                try:
                    bot.send_message(
                        uid,
                        f'⏰ <b>File Auto Stop completed.</b>\n\n'
                        f'📄 File: <b>{html_lib.escape(r["orig_name"] or str(fid))}</b>\n'
                        f'🛑 The file was stopped automatically.'
                    )
                except Exception:
                    pass
        except Exception:
            logger.exception('Auto-stop worker error')
        time.sleep(5)

def admin_auto_stop_users_menu(chat_id, page=0, message_id=None):
    """Select one user and apply one timer to all of that user's files."""
    cur = conn.cursor()
    cur.execute("SELECT user_id,username FROM users ORDER BY user_id")
    users = cur.fetchall()
    per_page = 20
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_users = users[page * per_page:(page + 1) * per_page]

    text = f"📂 <b>USER FILES AUTO STOP</b> — Page {page + 1}/{total_pages}\n\n"
    text += "Select a user. The timer will be applied to <b>ALL files</b> currently belonging to that user.\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for u in page_users:
        uid = u["user_id"]
        name = html_lib.escape(u["username"] or str(uid))
        cur.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (uid,))
        count = cur.fetchone()[0] or 0
        text += f"👤 <b>{name}</b> — 📁 {count} files\n"
        kb.add(InlineKeyboardButton(
            f"⏰ SET ALL • {name[:20]}",
            callback_data=f"admin_user_files_autostop:{uid}"
        ))
    if page > 0:
        kb.add(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_auto_stop_users_page:{page-1}"))
    if page < total_pages - 1:
        kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"admin_auto_stop_users_page:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Auto Stop", callback_data="admin_auto_stop_menu"))
    _edit_or_send(chat_id, message_id, text, kb)


def admin_user_files_autostop_receive(message, uid):
    if (message.text or '').strip().lower() == '/cancel':
        bot.send_message(message.chat.id, '❌ Cancelled.', reply_markup=admin_panel_kb())
        return
    try:
        seconds = parse_duration(message.text)
        deadline = set_user_files_auto_stop(uid, seconds)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (uid,))
        count = cur.fetchone()[0] or 0
        log_admin('user_files_auto_stop_set', f'user={uid},files={count},deadline={deadline}')
        bot.send_message(
            message.chat.id,
            f'✅ <b>All User Files Auto Stop set</b>\n\n'
            f'👤 User ID: <code>{uid}</code>\n'
            f'📁 Files updated: <b>{count}</b>\n'
            f'⏰ Duration: <b>{html_lib.escape(message.text.strip())}</b>\n'
            f'🕒 Deadline: <code>{deadline[:19]} UTC</code>\n\n'
            f'Every file of this user now has the same auto-stop deadline.',
            reply_markup=admin_panel_kb()
        )
    except ValueError as e:
        bot.send_message(
            message.chat.id,
            f'❌ {html_lib.escape(str(e))}\n\nExample: <code>30 minutes</code>, <code>2 hours</code>, <code>1 day</code>.'
        )
        msg = bot.send_message(message.chat.id, '⏰ Send duration again, or /cancel.')
        bot.register_next_step_handler(msg, admin_user_files_autostop_receive, uid)


def admin_file_autostop_receive(message, fid):
    if (message.text or '').strip().lower() == '/cancel':
        bot.send_message(message.chat.id, '❌ Cancelled.', reply_markup=admin_panel_kb())
        return
    try:
        seconds = parse_duration(message.text)
        deadline = set_file_auto_stop(fid, seconds)
        rec = get_file_record(fid)
        log_admin('file_auto_stop_set', f'file={fid},deadline={deadline}')
        bot.send_message(
            message.chat.id,
            f'✅ <b>File Auto Stop set</b>\n\n'
            f'📄 File: <b>{html_lib.escape(rec["orig_name"] if rec else str(fid))}</b>\n'
            f'⏰ Duration: <b>{html_lib.escape(message.text.strip())}</b>\n'
            f'🕒 Deadline: <code>{deadline[:19]} UTC</code>',
            reply_markup=admin_panel_kb()
        )
    except ValueError as e:
        bot.send_message(message.chat.id, f'❌ {html_lib.escape(str(e))}\n\nExample: <code>30 minutes</code>, <code>2 hours</code>, <code>1 day</code>.')
        msg = bot.send_message(message.chat.id, '⏰ Send duration again, or /cancel.')
        bot.register_next_step_handler(msg, admin_file_autostop_receive, fid)


def admin_auto_stop_menu(chat_id, message_id=None):
    g = get_setting('global_auto_stop_at', '')
    text = "⏰ <b>AUTO STOP CONTROL</b>\n\n"
    text += f"🌐 Global timer: <b>{html_lib.escape(format_deadline(g) if g else 'OFF')}</b>\n\n"
    text += "Set a one-time timer. When it expires, every currently running hosted file is stopped. Users can start their files again manually."
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('🌐 Set Global Timer', callback_data='admin_global_autostop_set'))
    kb.add(InlineKeyboardButton('📂 User Files Timer', callback_data='admin_auto_stop_users'))
    if g: kb.add(InlineKeyboardButton('❌ Cancel Global Timer', callback_data='admin_global_autostop_clear'))
    kb.add(InlineKeyboardButton('🔙 Back', callback_data='admin_back'))
    _edit_or_send(chat_id, message_id, text, kb)

def admin_global_autostop_receive(message):
    if (message.text or '').strip().lower() == '/cancel':
        bot.send_message(message.chat.id, '❌ Cancelled.', reply_markup=admin_panel_kb()); return
    try:
        seconds=parse_duration(message.text)
        deadline=set_global_auto_stop(seconds)
        log_admin('global_auto_stop_set', deadline)
        bot.send_message(message.chat.id, f'✅ <b>Global Auto Stop ON</b>\n\n⏰ Files will automatically stop after <b>{html_lib.escape(message.text.strip())}</b>.\n🕒 Deadline: <code>{deadline[:19]} UTC</code>\n\nUsers can start their files again after they are stopped.', reply_markup=admin_panel_kb())
    except ValueError as e:
        bot.send_message(message.chat.id, f'❌ {html_lib.escape(str(e))}\n\nExample: <code>30 minutes</code>, <code>2 hours</code>, <code>1 day</code>.')
        msg=bot.send_message(message.chat.id, '⏰ Send duration again, or /cancel.')
        bot.register_next_step_handler(msg, admin_global_autostop_receive)

def admin_user_autostop_receive(message, uid):
    if (message.text or '').strip().lower() == '/cancel':
        bot.send_message(message.chat.id, '❌ Cancelled.', reply_markup=admin_panel_kb()); return
    try:
        seconds=parse_duration(message.text)
        deadline=set_user_auto_stop(uid, seconds)
        log_admin('user_auto_stop_set', f'user={uid},deadline={deadline}')
        bot.send_message(message.chat.id, f'✅ <b>User Auto Stop set</b>\n\n👤 User ID: <code>{uid}</code>\n⏰ Duration: <b>{html_lib.escape(message.text.strip())}</b>\n🕒 Deadline: <code>{deadline[:19]} UTC</code>\n\nAll files currently running for this user will stop at the deadline. The user can start them again manually.', reply_markup=admin_panel_kb())
    except ValueError as e:
        bot.send_message(message.chat.id, f'❌ {html_lib.escape(str(e))}\n\nExample: <code>30 minutes</code>, <code>2 hours</code>, <code>1 day</code>.')
        msg=bot.send_message(message.chat.id, '⏰ Send duration again, or /cancel.')
        bot.register_next_step_handler(msg, admin_user_autostop_receive, uid)

def admin_user_autostop_menu(chat_id, uid, message_id=None):
    cur=conn.cursor(); cur.execute('SELECT username,auto_stop_at FROM users WHERE user_id=?',(uid,)); u=cur.fetchone()
    if not u: _edit_or_send(chat_id,message_id,'❌ User not found.',admin_panel_kb()); return
    current=format_deadline(u['auto_stop_at']) if u['auto_stop_at'] else 'OFF'
    text=f"⏰ <b>USER AUTO STOP</b>\n\n👤 User: <b>{html_lib.escape(u['username'] or str(uid))}</b>\n🆔 ID: <code>{uid}</code>\n⏰ Current: <b>{html_lib.escape(current)}</b>\n\nSet a one-time timer for this user. At expiry, all their currently running files will be stopped. They can start them again manually."
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('⏰ Set Timer',callback_data=f'admin_user_autostop_set:{uid}'))
    if u['auto_stop_at']: kb.add(InlineKeyboardButton('❌ Cancel Timer',callback_data=f'admin_user_autostop_clear:{uid}'))
    kb.add(InlineKeyboardButton('🔙 Profile',callback_data=f'admin_profile:{uid}'))
    _edit_or_send(chat_id,message_id,text,kb)

def admin_profile(chat_id, uid, message_id=None):
    cur=conn.cursor(); cur.execute("SELECT * FROM users WHERE user_id=?",(uid,)); u=cur.fetchone()
    if not u: _edit_or_send(chat_id,message_id,'❌ User not found.',admin_panel_kb()); return
    cur.execute("SELECT COUNT(*) FROM files WHERE user_id=?",(uid,)); fc=cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM files WHERE user_id=? AND status='Running'",(uid,)); rc=cur.fetchone()[0] or 0
    custom_limit = u['max_files'] if 'max_files' in u.keys() else None
    limit_text = str(custom_limit) if custom_limit is not None else f"{effective_max_files()} (Global)"
    auto_stop_at = u['auto_stop_at'] if 'auto_stop_at' in u.keys() else None
    auto_text = format_deadline(auto_stop_at) if auto_stop_at else 'OFF'
    text=f"👤 <b>USER PROFILE</b>\n\n🆔 ID: <code>{uid}</code>\n👤 Username: <b>{html_lib.escape(u['username'] or 'None')}</b>\n📅 Joined: <code>{html_lib.escape(u['joined_at'] or '-')}</code>\n👀 Last Seen: <code>{html_lib.escape(u['last_seen'] or '-')}</code>\n📁 Files: <b>{fc}</b>\n📌 Upload Limit: <b>{limit_text}</b>\n🟢 Running: <b>{rc}</b>\n⏰ Auto Stop: <b>{html_lib.escape(auto_text)}</b>\n🔐 Status: <b>{'BLOCKED' if u['blocked'] else 'ACTIVE'}</b>"
    kb=InlineKeyboardMarkup(row_width=2)
    if uid!=ADMIN_ID: kb.add(InlineKeyboardButton('🔓 Unblock' if u['blocked'] else '🚫 Block',callback_data=f"admin_unblock_user:{uid}" if u['blocked'] else f"admin_block_user:{uid}"))
    kb.add(InlineKeyboardButton('💀 User Fills Set',callback_data=f'admin_user_files_set:{uid}'))
    if uid != ADMIN_ID:
        kb.add(InlineKeyboardButton('⏰ Set User Auto Stop', callback_data=f'admin_user_autostop:{uid}'))
    kb.add(InlineKeyboardButton('📂 Files',callback_data=f'admin_user_files:{uid}'),InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
    _edit_or_send(chat_id,message_id,text,kb)

def admin_process_on(chat_id, message_id=None):
    """Show stopped, approved files and provide Start All."""
    cur = conn.cursor()
    cur.execute("SELECT id,orig_name,user_id,approval_status FROM files ORDER BY id DESC")

    stopped = []
    for r in cur.fetchall():
        if r['approval_status'] == 'approved' and not is_file_running(r['id']):
            stopped.append(r)

    text = (
        "⚡ <b>PROCESS ON</b>\n\n"
        f"🔴 Stopped Files: <b>{len(stopped)}</b>\n\n"
        + (
            "\n".join(
                f"🔴 <b>{html_lib.escape(r['orig_name'])}</b> — User <code>{r['user_id']}</code>"
                for r in stopped
            )
            or "✅ No stopped approved files."
        )
    )

    kb = InlineKeyboardMarkup(row_width=1)
    for r in stopped:
        kb.add(InlineKeyboardButton(
            f"▶️ START • {r['orig_name'][:25]}",
            callback_data=f"admin_start_file:{r['id']}"
        ))

    if stopped:
        kb.add(InlineKeyboardButton("🚀 START ALL", callback_data="admin_start_all"))

    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    _edit_or_send(chat_id, message_id, text, kb)


def admin_start_all(chat_id, message_id=None):
    """Start every stopped approved file."""
    cur = conn.cursor()
    cur.execute("SELECT id,approval_status FROM files ORDER BY id DESC")

    started = 0
    for r in cur.fetchall():
        if r['approval_status'] != 'approved' or is_file_running(r['id']):
            continue
        try:
            start_file_process(r['id'], chat_id)
            time.sleep(0.5)
            if is_file_running(r['id']):
                started += 1
        except Exception as e:
            logger.error(f"Start All error for file {r['id']}: {e}")

    log_admin("start_all", started)
    admin_process_on(chat_id, message_id)


def admin_processes(chat_id,message_id=None):
    cur=conn.cursor(); cur.execute("SELECT id,orig_name,user_id FROM files ORDER BY id DESC")
    rows=[]
    for r in cur.fetchall():
        if is_file_running(r['id']): rows.append(r)
    text=f"🖥️ <b>PROCESS MONITOR</b>\n\nRunning: <b>{len(rows)}</b>\n\n" + ('\n'.join(f"🟢 <b>{html_lib.escape(r['orig_name'])}</b> — User <code>{r['user_id']}</code>" for r in rows) or 'No running processes.')
    kb=InlineKeyboardMarkup(row_width=1)
    for r in rows: kb.add(InlineKeyboardButton(f"⏹ STOP • {r['orig_name'][:25]}",callback_data=f"admin_stop_file:{r['id']}"))
    if rows: kb.add(InlineKeyboardButton('🛑 STOP ALL',callback_data='admin_stop_all_confirm'))
    kb.add(InlineKeyboardButton('🔄 Refresh',callback_data='admin_processes'),InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
    _edit_or_send(chat_id,message_id,text,kb)

def admin_system_text():
    cpu,mem,cnt=get_system_load(); du=shutil.disk_usage(BASE_DIR); up=datetime.utcnow()-START_TIME
    return f"🖥️ <b>SYSTEM STATUS</b>\n\n⚡ CPU: <b>{cpu:.1f}%</b>\n💾 RAM: <b>{mem:.1f}%</b>\n🧵 Managed Processes: <b>{cnt}</b>\n💽 Disk: <b>{du.used/du.total*100:.1f}%</b> used\n📦 Disk Free: <b>{du.free/(1024**3):.2f} GB</b>\n⏱ Uptime: <b>{up.days}d {up.seconds//3600}h {(up.seconds%3600)//60}m</b>\n🐍 Python: <code>{sys.version.split()[0]}</code>"

def admin_settings_menu(chat_id,message_id=None):
    maxf=effective_max_files(); maint=maintenance_enabled(); appr=python_approval_enabled(); prem=premium_panel_enabled()
    text=f"⚙️ <b>BOT SETTINGS</b>\n\n📁 Max files/user: <b>{maxf}</b>\n🛡 Maintenance: <b>{'ON' if maint else 'OFF'}</b>\n🐍 Python approval: <b>{'ON' if appr else 'OFF'}</b>\n💎 Premium panel: <b>{'ON 🟢' if prem else 'OFF 🔴'}</b>"
    kb=InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('📁 Set Max Files',callback_data='admin_set_max_files'),InlineKeyboardButton('🛡 Toggle Maintenance',callback_data='admin_toggle_maintenance'))
    kb.add(InlineKeyboardButton('🐍 Toggle Python Approval',callback_data='admin_toggle_python'))
    kb.add(InlineKeyboardButton('💎 Premium Panel: '+('ON 🟢' if prem else 'OFF 🔴'),callback_data='admin_toggle_premium_panel'))
    kb.add(InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
    _edit_or_send(chat_id,message_id,text,kb)

def admin_broadcast_menu(chat_id,message_id=None):
    kb=InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('📢 All Users',callback_data='admin_broadcast:all'))
    kb.add(InlineKeyboardButton('🟢 Active 24h',callback_data='admin_broadcast:active'))
    kb.add(InlineKeyboardButton('👤 Unblocked Only',callback_data='admin_broadcast:unblocked'))
    kb.add(InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
    _edit_or_send(chat_id,message_id,'📢 <b>ADVANCED BROADCAST</b>\n\nSelect audience:',kb)

def broadcast_advanced_receive(message, mode):
    if message.content_type=='text' and (message.text or '').strip()=='/cancel': bot.send_message(message.chat.id,'❌ Cancelled.'); return
    cur=conn.cursor(); cutoff=(datetime.utcnow()-timedelta(hours=24)).isoformat()
    if mode=='active': cur.execute("SELECT user_id FROM users WHERE last_seen>=? AND blocked=0",(cutoff,))
    elif mode=='unblocked': cur.execute("SELECT user_id FROM users WHERE blocked=0")
    else: cur.execute("SELECT user_id FROM users")
    users=cur.fetchall(); ok=fail=0
    status=bot.send_message(message.chat.id,f'📢 Sending to <b>{len(users)}</b> users...')
    for r in users:
        try: bot.copy_message(r['user_id'],message.chat.id,message.message_id); ok+=1
        except Exception: fail+=1
        time.sleep(0.04)
    log_admin('broadcast',mode)
    bot.send_message(message.chat.id,f'✅ <b>Broadcast Done</b>\n\nAudience: {mode}\nSuccess: {ok}\nFailed: {fail}')

def admin_backup(chat_id):
    os.makedirs(os.path.join(DATA_DIR,'backups'),exist_ok=True)
    name=f"bot_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"; path=os.path.join(DATA_DIR,'backups',name)
    with db_lock:
        src=sqlite3.connect(DB_PATH); dst=sqlite3.connect(path); src.backup(dst); dst.close(); src.close()
    with open(path,'rb') as f: bot.send_document(chat_id,f,caption=f'💾 Database backup: {name}')
    log_admin('database_backup',name)

def admin_logs_view(chat_id,message_id=None):
    cur=conn.cursor(); cur.execute("SELECT action,target,created_at FROM admin_logs ORDER BY id DESC LIMIT 15"); rows=cur.fetchall()
    text='📜 <b>ADMIN ACTIVITY LOG</b>\n\n' + ('\n'.join(f"• <b>{html_lib.escape(r['action'])}</b> | {html_lib.escape(r['target'] or '-')}\n  <code>{r['created_at'][:19]}</code>" for r in rows) or 'No logs yet.')
    kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton('🧹 Clear Logs',callback_data='admin_clear_logs_confirm'),InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
    _edit_or_send(chat_id,message_id,text,kb)

# ── Extra Advanced Admin Tools ─────────────────────────────
def admin_export_users(chat_id):
    path=os.path.join(TEMP_DIR,f"users_export_{int(time.time())}.csv")
    try:
        cur=conn.cursor(); cur.execute("SELECT user_id,username,joined_at,last_seen,blocked,joined_channel FROM users ORDER BY joined_at DESC"); rows=cur.fetchall()
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["user_id","username","joined_at","last_seen","blocked","joined_channel"])
            for r in rows: w.writerow([r["user_id"],r["username"] or "",r["joined_at"] or "",r["last_seen"] or "",r["blocked"] or 0,r["joined_channel"] or 0])
        with open(path,"rb") as f: bot.send_document(chat_id,f,caption=f"📦 Users Export • {len(rows)} users")
        log_admin("export_users",len(rows))
    finally:
        try: os.remove(path)
        except Exception: pass

def admin_message_user_receive(message):
    if (message.text or '').strip()=='/cancel': bot.send_message(message.chat.id,'❌ Cancelled.',reply_markup=admin_panel_kb()); return
    q=(message.text or '').strip().lstrip('@'); cur=conn.cursor()
    if q.isdigit(): cur.execute("SELECT user_id,username FROM users WHERE user_id=?",(int(q),))
    else: cur.execute("SELECT user_id,username FROM users WHERE username LIKE ? LIMIT 1",('%'+q+'%',))
    u=cur.fetchone()
    if not u: bot.send_message(message.chat.id,'❌ User not found.',reply_markup=admin_panel_kb()); return
    prompt=bot.send_message(message.chat.id,f"💬 Send message for <b>{html_lib.escape(u['username'] or str(u['user_id']))}</b>.\n/cancel to abort")
    bot.register_next_step_handler(prompt,lambda m: admin_message_user_send(m,int(u['user_id'])))

def admin_message_user_send(message,uid):
    if message.content_type=='text' and (message.text or '').strip()=='/cancel': bot.send_message(message.chat.id,'❌ Cancelled.',reply_markup=admin_panel_kb()); return
    try:
        bot.copy_message(uid,message.chat.id,message.message_id); log_admin('message_user',uid)
        bot.send_message(message.chat.id,f'✅ Message sent to <code>{uid}</code>.',reply_markup=admin_panel_kb())
    except Exception as e: bot.send_message(message.chat.id,f'❌ Failed: {html_lib.escape(str(e))}',reply_markup=admin_panel_kb())

def admin_restart_all_confirm(chat_id,message_id):
    kb=InlineKeyboardMarkup(row_width=2); kb.add(InlineKeyboardButton('⚠️ YES, RESTART ALL',callback_data='admin_restart_all'),InlineKeyboardButton('❌ Cancel',callback_data='admin_back'))
    _edit_or_send(chat_id,message_id,'⚠️ <b>Restart All Hosted Bots?</b>\n\nEvery currently running hosted process will be restarted.',kb)

def admin_restart_all(chat_id,message_id):
    ids=list_process_ids(); stopped=started=0
    for fid in ids:
        try: stop_file_process(fid); stopped+=1
        except Exception: pass
    time.sleep(1)
    for fid in ids:
        try:
            rec=get_file_record(fid)
            if rec and rec['approval_status']=='approved': start_file_process(fid,chat_id); started+=1
        except Exception: pass
    log_admin('restart_all',f'stopped={stopped},started={started}')
    _edit_or_send(chat_id,message_id,f'🔄 <b>Restart All Complete</b>\n\nStopped: <b>{stopped}</b>\nRestart requested: <b>{started}</b>',admin_panel_kb())

def admin_cleanup_dead_runs(chat_id):
    cutoff=(datetime.utcnow()-timedelta(days=30)).isoformat()
    with db_lock:
        deleted=conn.execute('DELETE FROM runs WHERE finished_at IS NOT NULL AND finished_at<?',(cutoff,)).rowcount; conn.commit()
    log_admin('cleanup_runs',deleted); bot.send_message(chat_id,f'🧹 Removed <b>{deleted}</b> old run records.',reply_markup=admin_panel_kb())

def admin_health_check_text():
    """Compact health report for the admin panel."""
    cpu, mem, managed = get_system_load()
    du = shutil.disk_usage(BASE_DIR)
    running = 0
    with proc_lock:
        for entry in processes.values():
            proc = entry.get("process")
            if proc and proc.poll() is None:
                running += 1
    try:
        db_ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except Exception:
        db_ok = False
    try:
        pending_py = conn.execute("SELECT COUNT(*) FROM files WHERE approval_status='pending'").fetchone()[0] or 0
    except Exception:
        pending_py = 0
    try:
        pending_pay = conn.execute("SELECT COUNT(*) FROM premium_payments WHERE status='pending'").fetchone()[0] or 0
    except Exception:
        pending_pay = 0
    return (
        "🩺 <b>HOSTING HEALTH CHECK</b>\n\n"
        f"🗄️ Database: <b>{'OK 🟢' if db_ok else 'ERROR 🔴'}</b>\n"
        f"🟢 Running: <b>{running}/{MAX_RUNNING_PROCESSES}</b>\n"
        f"⚡ CPU: <b>{cpu:.1f}%</b>\n"
        f"💾 RAM: <b>{mem:.1f}%</b>\n"
        f"💽 Disk: <b>{du.used/du.total*100:.1f}%</b> used\n"
        f"📥 Pending Python: <b>{pending_py}</b>\n"
        f"💳 Pending Premium: <b>{pending_pay}</b>\n"
        f"🛡 Maintenance: <b>{'ON' if maintenance_enabled() else 'OFF'}</b>"
    )

def admin_pending_queue_text():
    try:
        py = conn.execute("SELECT COUNT(*) FROM files WHERE approval_status='pending'").fetchone()[0] or 0
    except Exception:
        py = 0
    try:
        pay = conn.execute("SELECT COUNT(*) FROM premium_payments WHERE status='pending'").fetchone()[0] or 0
    except Exception:
        pay = 0
    return (
        "📋 <b>PENDING QUEUE</b>\n\n"
        f"🐍 Python approvals: <b>{py}</b>\n"
        f"💳 Premium payments: <b>{pay}</b>\n\n"
        "Python approval requests are sent to this Admin chat. "
        "Premium payment requests can be reviewed from the payment messages."
    )

# ── Premium User Tools ─────────────────────────────────────
def premium_is_active(user_id):
    row = premium_row(user_id)
    return bool(row and row["status"] == "active")

def premium_hub_text(user_id):
    row = premium_row(user_id)
    if not row or row["status"] != "active":
        return ("👑 <b>PREMIUM HUB</b>\n\n"
                "🔒 Premium-only tools are locked.\n"
                "Upgrade to unlock quick bot controls and usage tools.")
    rows = conn.execute("SELECT id,approval_status FROM files WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    total = len(rows); running = sum(1 for r in rows if is_file_running(r["id"]))
    approved = sum(1 for r in rows if r["approval_status"] == "approved")
    pending = sum(1 for r in rows if r["approval_status"] == "pending")
    limit = effective_user_max_files(user_id)
    return ("👑 <b>PREMIUM CONTROL CENTER</b>\n\n"
            f"💎 Status: <b>{html_lib.escape(premium_status_text(user_id))}</b>\n"
            f"📁 Projects: <b>{total}/{limit}</b>\n"
            f"🟢 Running: <b>{running}</b>\n"
            f"✅ Approved: <b>{approved}</b>\n"
            f"⏳ Pending: <b>{pending}</b>\n\n"
            "⚡ Use the quick tools below to manage your hosted projects.")

def premium_hub_kb(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    if premium_is_active(user_id):
        kb.add(InlineKeyboardButton("🚀 Start All", callback_data="premium_start_all"),
               InlineKeyboardButton("🔄 Restart All", callback_data="premium_restart_all_confirm"))
        kb.add(InlineKeyboardButton("📊 Usage", callback_data="premium_usage"),
               InlineKeyboardButton("🧾 Activity", callback_data="premium_activity"))
        kb.add(InlineKeyboardButton("🛡️ Premium Features", callback_data="premium_features"))
    kb.add(InlineKeyboardButton("💎 My Premium", callback_data="premium_status"))
    kb.add(InlineKeyboardButton("🔙 Main Menu", callback_data="premium_back"))
    return kb

def premium_usage_text(user_id):
    if not premium_is_active(user_id):
        return "🔒 <b>Premium Usage</b>\n\nThis tool is available to active Premium users."
    rows = conn.execute("SELECT id,approval_status FROM files WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    return ("📊 <b>PREMIUM USAGE</b>\n\n"
            f"📁 Total projects: <b>{len(rows)}/{effective_user_max_files(user_id)}</b>\n"
            f"🟢 Running now: <b>{sum(1 for r in rows if is_file_running(r['id']))}</b>\n"
            f"🔴 Stopped: <b>{sum(1 for r in rows if not is_file_running(r['id']))}</b>\n"
            f"⏳ Pending approval: <b>{sum(1 for r in rows if r['approval_status']=='pending')}</b>")

def premium_activity_text(user_id):
    if not premium_is_active(user_id):
        return "🔒 <b>Premium Activity</b>\n\nThis tool is available to active Premium users."
    rows = conn.execute("SELECT action,details,created_at FROM activity_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 15", (user_id,)).fetchall()
    if not rows: return "🧾 <b>PREMIUM ACTIVITY</b>\n\nNo recent activity found."
    lines=["🧾 <b>PREMIUM ACTIVITY</b>",""]
    for r in rows:
        lines.append(f"• <b>{html_lib.escape(str(r['action'] or 'Action'))}</b> — {html_lib.escape(str(r['details'] or ''))[:100]}\n  <code>{html_lib.escape(str(r['created_at'] or '')[:19])} UTC</code>")
    return "\n".join(lines)

def premium_start_all(chat_id, user_id):
    if not premium_is_active(user_id):
        bot.send_message(chat_id, "🔒 Premium-only tool. Please activate Premium first."); return
    rows=conn.execute("SELECT id,approval_status FROM files WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall(); requested=0
    for r in rows:
        if r['approval_status']!='approved' or is_file_running(r['id']): continue
        try:
            start_file_process(r['id'],chat_id,notify=False); requested+=1; time.sleep(0.25)
        except Exception: logger.exception("Premium Start All error for file %s",r['id'])
    log_activity(user_id,"premium_start_all",f"requested={requested}")
    bot.send_message(chat_id,f"🚀 <b>Premium Start All</b>\n\nStart requested for <b>{requested}</b> approved stopped projects.",reply_markup=main_menu_kb())

def premium_restart_all(chat_id, user_id):
    if not premium_is_active(user_id):
        bot.send_message(chat_id, "🔒 Premium-only tool. Please activate Premium first."); return
    rows=conn.execute("SELECT id,approval_status FROM files WHERE user_id=? ORDER BY id DESC",(user_id,)).fetchall()
    ids=[r['id'] for r in rows if r['approval_status']=='approved' and is_file_running(r['id'])]
    for fid in ids:
        try: stop_file_process(fid)
        except Exception: logger.exception("Premium Restart stop error for file %s",fid)
    time.sleep(0.5); restarted=0
    for fid in ids:
        try: start_file_process(fid,chat_id,notify=False); restarted+=1; time.sleep(0.25)
        except Exception: logger.exception("Premium Restart start error for file %s",fid)
    log_activity(user_id,"premium_restart_all",f"restarted={restarted}")
    bot.send_message(chat_id,f"🔄 <b>Premium Restart All</b>\n\nRestart requested for <b>{restarted}</b> running projects.",reply_markup=main_menu_kb())

# ── Admin Callbacks ───────────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith("premium_") and not c.data.startswith(("premium_pay_approve:", "premium_pay_reject:")))
def premium_callback(call):
    data=call.data; chat_id=call.message.chat.id; uid=call.from_user.id
    if not premium_panel_enabled():
        bot.answer_callback_query(call.id, 'Premium panel is currently hidden.')
        return
    if data=="premium_status":
        _edit_or_send(chat_id,call.message.message_id,premium_text(uid),premium_menu_kb())
    elif data=="premium_hub":
        if not premium_panel_enabled():
            bot.answer_callback_query(call.id, "Premium panel is currently hidden.")
            return
        _edit_or_send(chat_id,call.message.message_id,premium_hub_text(uid),premium_hub_kb(uid))
    elif data=="premium_usage":
        kb=InlineKeyboardMarkup(row_width=1); kb.add(InlineKeyboardButton("🔄 Refresh",callback_data="premium_usage"),InlineKeyboardButton("🔙 Premium Hub",callback_data="premium_hub"))
        _edit_or_send(chat_id,call.message.message_id,premium_usage_text(uid),kb)
    elif data=="premium_activity":
        kb=InlineKeyboardMarkup(row_width=1); kb.add(InlineKeyboardButton("🔄 Refresh",callback_data="premium_activity"),InlineKeyboardButton("🔙 Premium Hub",callback_data="premium_hub"))
        _edit_or_send(chat_id,call.message.message_id,premium_activity_text(uid),kb)
    elif data=="premium_start_all":
        premium_start_all(chat_id,uid); bot.answer_callback_query(call.id,"Start requested"); return
    elif data=="premium_restart_all_confirm":
        if not premium_is_active(uid): bot.answer_callback_query(call.id,"Premium required"); return
        kb=InlineKeyboardMarkup(row_width=2); kb.add(InlineKeyboardButton("⚠️ YES, RESTART",callback_data="premium_restart_all"),InlineKeyboardButton("❌ Cancel",callback_data="premium_hub"))
        _edit_or_send(chat_id,call.message.message_id,"⚠️ <b>Restart your running Premium projects?</b>\n\nOnly your currently running approved projects will be restarted.",kb)
    elif data=="premium_restart_all":
        premium_restart_all(chat_id,uid); bot.answer_callback_query(call.id,"Restart requested"); return
    elif data=="premium_benefits":
        kb=InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📅 View Premium Plans",callback_data="premium_plans"))
        kb.add(InlineKeyboardButton("🔙 Premium",callback_data="premium_status"))
        _edit_or_send(chat_id,call.message.message_id,
                      "✨ <b>PREMIUM BENEFITS</b>\n\n💎 Premium badge\n🚀 Quick Start All for your approved projects\n🔄 Quick Restart All for your running projects\n📊 Premium usage overview\n🧾 Extended activity history\n⚡ Priority support\n🛡 Admin-managed Premium access\n⏰ Automatic expiry tracking",kb)
    elif data=="premium_plans":
        _edit_or_send(chat_id,call.message.message_id,premium_plans_text(),premium_payment_kb())
    elif data.startswith("premium_plan:"):
        try:
            days=int(data.split(":",1)[1])
            if days not in PREMIUM_PLANS: raise ValueError
        except ValueError:
            bot.answer_callback_query(call.id,"Invalid plan")
            return
        pending_premium_plan[uid]=days
        amount=PREMIUM_PLANS[days]
        bot.send_message(chat_id,premium_payment_request_text(days))
        send_premium_qr(chat_id, days)
        bot.send_message(chat_id,
            f"📸 <b>Now send the payment screenshot here.</b>\n\n"
            f"Selected: <b>{days} Days — ₹{amount}</b>")
    elif data=="premium_contact":
        _edit_or_send(chat_id,call.message.message_id,premium_plans_text(),premium_payment_kb())
    elif data=="premium_features":
        if premium_is_active(call.from_user.id):
            text = ("🛡️ <b>PREMIUM HOSTING FEATURES</b>\n\n"
                    "🚀 Priority project controls\n"
                    "🔄 Auto-Recovery / Watchdog\n"
                    "❤️ 24/7 process monitoring\n"
                    "📊 Live uptime / CPU / RAM / PID\n"
                    "📜 Advanced logs & crash history\n"
                    "🔔 Failure / recovery notifications\n"
                    "🔁 Server-restart recovery\n"
                    "💾 Database & project backup tools\n"
                    "🧹 Project/log cleanup tools\n\n"
                    "These controls work within the server's resource limits.")
        else:
            text = "🔒 <b>Premium Features</b>\n\nActivate Premium to unlock the Premium Hosting Control Center."
        kb=InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("🔄 Refresh",callback_data="premium_features"),
               InlineKeyboardButton("🔙 Premium Hub",callback_data="premium_hub"))
        _edit_or_send(chat_id,call.message.message_id,text,kb)
    elif data=="premium_back":
        bot.send_message(chat_id,"🏠 <b>Main Menu</b>\n\nChoose an option below.",reply_markup=main_menu_kb())
    bot.answer_callback_query(call.id)


def admin_premium_grant_receive(message):
    if (message.text or '').strip().lower()=='/cancel':
        bot.send_message(message.chat.id,'❌ Cancelled.',reply_markup=admin_panel_kb()); return
    try:
        parts=(message.text or '').strip().split()
        if len(parts)!=2: raise ValueError("Use USER_ID DAYS")
        uid=int(parts[0]); days=int(parts[1])
        if uid<=0 or days<0 or days>3650: raise ValueError("Days must be 0-3650.")
        if not conn.execute("SELECT 1 FROM users WHERE user_id=?",(uid,)).fetchone():
            raise ValueError("User not found in this bot.")
        exp=grant_premium(uid,days)
        log_admin('premium_grant',f'user={uid},days={days}')
        exp_text="Lifetime" if not exp else exp[:19]+" UTC"
        bot.send_message(message.chat.id,f"✅ <b>Premium Granted</b>\n\n👤 <code>{uid}</code>\n💎 Premium\n⏰ {exp_text}",reply_markup=admin_panel_kb())
        try: bot.send_message(uid,f"💎 <b>Premium Activated!</b>\n\n⏰ Expiry: <b>{exp_text}</b>")
        except Exception: pass
    except Exception as e:
        bot.send_message(message.chat.id,f"❌ {html_lib.escape(str(e))}\n\nExample: <code>123456789 30</code>")
        msg=bot.send_message(message.chat.id,"💎 Send again or /cancel."); bot.register_next_step_handler(msg,admin_premium_grant_receive)

def admin_premium_grant_plan_receive(message, days):
    if (message.text or '').strip().lower()=='/cancel':
        bot.send_message(message.chat.id,'❌ Cancelled.',reply_markup=admin_panel_kb()); return
    try:
        uid=int((message.text or '').strip())
        if uid<=0: raise ValueError("Invalid User ID.")
        if not conn.execute("SELECT 1 FROM users WHERE user_id=?",(uid,)).fetchone():
            raise ValueError("User not found in this bot.")
        exp=grant_premium(uid,days)
        plan_name="Lifetime" if days == 0 else f"{days} Days"
        with db_lock:
            conn.execute("UPDATE premium_members SET plan=? WHERE user_id=?", (plan_name, uid))
            conn.commit()
        exp_text="Lifetime" if not exp else exp[:19]+" UTC"
        bot.send_message(message.chat.id,f"✅ <b>Premium Granted</b>\n\n👤 User ID: <code>{uid}</code>\n💎 Plan: <b>{plan_name}</b>\n⏰ Expiry: <b>{exp_text}</b>",reply_markup=admin_panel_kb())
        try: bot.send_message(uid,f"💎 <b>Premium Activated!</b>\n\n📦 Plan: <b>{plan_name}</b>\n⏰ Expiry: <b>{exp_text}</b>")
        except Exception: pass
    except Exception as e:
        bot.send_message(message.chat.id,f"❌ {html_lib.escape(str(e))}")
        msg=bot.send_message(message.chat.id,"💎 Send the User ID again or /cancel")
        bot.register_next_step_handler(msg,admin_premium_grant_plan_receive,days)

def admin_premium_revoke_receive(message):
    if (message.text or '').strip().lower()=='/cancel':
        bot.send_message(message.chat.id,'❌ Cancelled.',reply_markup=admin_panel_kb()); return
    try:
        uid=int((message.text or '').strip()); revoke_premium(uid); log_admin('premium_revoke',f'user={uid}')
        bot.send_message(message.chat.id,f"✅ <b>Premium Revoked</b>\n\n👤 <code>{uid}</code>",reply_markup=admin_panel_kb())
        try: bot.send_message(uid,"ℹ️ Your Premium access has been revoked by Admin.")
        except Exception: pass
    except Exception:
        msg=bot.send_message(message.chat.id,"❌ Invalid User ID. Send again or /cancel."); bot.register_next_step_handler(msg,admin_premium_revoke_receive)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("premium_pay_approve:", "premium_pay_reject:")))
def premium_payment_review_callback(call):
    """Fast, idempotent payment review handler.

    The Telegram callback is acknowledged immediately. Database activation,
    user notification and admin-message editing happen in a background worker,
    so the Approve/Reject button does not stay in the loading state while
    SQLite/network operations are running.
    """
    if call.from_user.id != ADMIN_ID:
        try:
            bot.answer_callback_query(call.id, "Not authorized.")
        except Exception:
            pass
        return

    try:
        action, pid_text = call.data.split(":", 1)
        pid = int(pid_text)
    except (ValueError, AttributeError):
        try:
            bot.answer_callback_query(call.id, "Invalid payment request.")
        except Exception:
            pass
        return

    row = get_pending_payment(pid)
    if not row:
        try:
            bot.answer_callback_query(call.id, "Payment request not found.")
        except Exception:
            pass
        return

    new_status = "approved" if action == "premium_pay_approve" else "rejected"

    # Atomically claim the pending payment. Only the first tap can process it.
    try:
        with db_lock:
            cur = conn.execute(
                """UPDATE premium_payments
                   SET status=?, reviewed_at=?
                   WHERE id=? AND status='pending'""",
                (new_status, datetime.utcnow().isoformat(), pid)
            )
            conn.commit()
            claimed = (cur.rowcount == 1)
    except Exception:
        logger.exception("Could not claim payment %s", pid)
        try:
            bot.answer_callback_query(call.id, "Database error. Try again.")
        except Exception:
            pass
        return

    if not claimed:
        try:
            bot.answer_callback_query(call.id, "Already processed.")
        except Exception:
            pass
        return

    # IMPORTANT: answer the Telegram callback before doing any slow work.
    try:
        bot.answer_callback_query(
            call.id,
            "✅ Approval accepted" if new_status == "approved" else "❌ Rejection accepted"
        )
    except Exception:
        pass

    def finish_review():
        try:
            if new_status == "approved":
                # Activate premium after the callback has already been answered.
                exp = grant_premium(row["user_id"], row["plan_days"])
                plan_name = f"{row['plan_days']} Days"
                with db_lock:
                    conn.execute(
                        "UPDATE premium_members SET plan=? WHERE user_id=?",
                        (plan_name, row["user_id"])
                    )
                    conn.commit()

                exp_text = "Lifetime" if not exp else exp[:19] + " UTC"

                try:
                    bot.send_message(
                        row["user_id"],
                        f"✅ <b>Payment Approved!</b>\n\n"
                        f"💎 Premium: <b>{row['plan_days']} Days</b>\n"
                        f"⏰ Expires: <b>{exp_text}</b>"
                    )
                except Exception:
                    logger.exception("Could not notify user %s after approval", row["user_id"])

                try:
                    bot.edit_message_caption(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        caption=(
                            f"✅ <b>PAYMENT APPROVED</b>\n\n"
                            f"👤 User ID: <code>{row['user_id']}</code>\n"
                            f"💎 Plan: <b>{row['plan_days']} Days</b>\n"
                            f"💰 Amount: <b>₹{row['amount']}</b>\n"
                            f"⏰ Expires: <b>{exp_text}</b>"
                        ),
                        reply_markup=None
                    )
                except Exception:
                    logger.exception("Could not update admin payment message %s", pid)

            else:
                try:
                    bot.send_message(
                        row["user_id"],
                        f"❌ <b>Payment Rejected</b>\n\n"
                        f"Your payment screenshot for <b>{row['plan_days']} Days Premium</b> "
                        f"was not approved. Please contact Admin and submit a valid screenshot."
                    )
                except Exception:
                    logger.exception("Could not notify user %s after rejection", row["user_id"])

                try:
                    bot.edit_message_caption(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        caption=(
                            f"❌ <b>PAYMENT REJECTED</b>\n\n"
                            f"👤 User ID: <code>{row['user_id']}</code>\n"
                            f"💎 Plan: <b>{row['plan_days']} Days</b>\n"
                            f"💰 Amount: <b>₹{row['amount']}</b>"
                        ),
                        reply_markup=None
                    )
                except Exception:
                    logger.exception("Could not update admin payment message %s", pid)

        except Exception as e:
            logger.exception("Premium payment review worker failed for %s", pid)
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"⚠️ Payment <code>{pid}</code> was marked <b>{new_status}</b>, "
                    f"but the final processing failed. Check the bot logs."
                )
            except Exception:
                pass

    threading.Thread(
        target=finish_review,
        daemon=True,
        name=f"payment-review-{pid}"
    ).start()

@bot.callback_query_handler(func=lambda c: c.data in ("feature_speed","feature_stats","feature_activity"))
def feature_center_callback(call):
    uid=call.from_user.id
    data=call.data
    if data=="feature_speed":
        started=time.perf_counter()
        cpu,mem,cnt=get_system_load()
        elapsed=(time.perf_counter()-started)*1000
        text=("⚡ <b>BOT SPEED</b>\n\n"
              f"🚀 Response: <b>{elapsed:.2f} ms</b>\n"
              f"💻 CPU: <b>{cpu:.1f}%</b>\n"
              f"💾 RAM: <b>{mem:.1f}%</b>\n"
              f"🖥️ Processes: <b>{cnt}/{MAX_RUNNING_PROCESSES}</b>")
    elif data=="feature_stats":
        total=conn.execute("SELECT COUNT(*) FROM files WHERE user_id=?",(uid,)).fetchone()[0] or 0
        running=sum(1 for r in conn.execute("SELECT id FROM files WHERE user_id=?",(uid,)).fetchall() if is_file_running(r[0]))
        text=("📊 <b>HOSTING STATISTICS</b>\n\n"
              f"📁 Projects: <b>{total}/{effective_user_max_files(uid)}</b>\n"
              f"🟢 Running: <b>{running}</b>\n"
              f"🔴 Stopped: <b>{total-running}</b>")
    else:
        text=premium_activity_text(uid) if premium_is_active(uid) else "🧾 <b>ACTIVITY</b>\n\nUse My Activity to view recent account actions."
    kb=InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🧩 Feature Center",callback_data="back_to_main"))
    _edit_or_send(call.message.chat.id,call.message.message_id,text,kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def admin_panel_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Not authorized.")
        return
    data    = call.data
    chat_id = call.message.chat.id
    if data == "admin_feature_center":
        _edit_or_send(chat_id,call.message.message_id,admin_feature_center_text(),admin_feature_center_kb())
        bot.answer_callback_query(call.id,"Feature center opened")
        return
    if data == "admin_health_check":
        kb=InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Refresh", callback_data="admin_health_check"), InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
        _edit_or_send(chat_id,call.message.message_id,admin_health_check_text(),kb)
        bot.answer_callback_query(call.id,"Health checked")
        return
    if data == "admin_pending_queue":
        kb=InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("💎 Premium Manager", callback_data="admin_premium_manager"))
        kb.add(InlineKeyboardButton("🐍 Python Approvals", callback_data="admin_manage_files"))
        kb.add(InlineKeyboardButton("🔄 Refresh", callback_data="admin_pending_queue"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
        _edit_or_send(chat_id,call.message.message_id,admin_pending_queue_text(),kb)
        bot.answer_callback_query(call.id,"Queue refreshed")
        return
    if data=="admin_premium_manager":
        premium_admin_menu(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data=="admin_premium_users":
        premium_users_list(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data=="admin_premium_grant":
        kb=InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📅 30 Days",callback_data="admin_premium_grant_plan:30"))
        kb.add(InlineKeyboardButton("♾️ Lifetime",callback_data="admin_premium_grant_plan:0"))
        kb.add(InlineKeyboardButton("🔙 Premium Manager",callback_data="admin_premium_manager"))
        _edit_or_send(chat_id,call.message.message_id,"💎 <b>GRANT PREMIUM</b>\n\nSelect a Premium plan:",kb)
        bot.answer_callback_query(call.id); return
    if data.startswith("admin_premium_grant_plan:"):
        days=int(data.split(":")[1])
        plan_name="Lifetime" if days == 0 else f"{days} Days"
        msg=bot.send_message(chat_id,f"💎 Selected plan: <b>{plan_name}</b>\n\nNow send: <code>USER_ID</code>\n/cancel")
        bot.register_next_step_handler(msg,admin_premium_grant_plan_receive,days)
        bot.answer_callback_query(call.id); return
    if data=="admin_premium_revoke":
        msg=bot.send_message(chat_id,"➖ Send the User ID to revoke Premium.\n/cancel")
        bot.register_next_step_handler(msg,admin_premium_revoke_receive); bot.answer_callback_query(call.id); return


    if data == "admin_dashboard":
        _edit_or_send(chat_id, call.message.message_id, admin_dashboard_text(), admin_panel_kb()); bot.answer_callback_query(call.id); return
    if data == "admin_analytics":
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔄 Refresh",callback_data="admin_analytics"),InlineKeyboardButton("🔙 Back",callback_data="admin_back"))
        _edit_or_send(chat_id,call.message.message_id,admin_analytics_text(),kb); bot.answer_callback_query(call.id); return
    if data == "admin_search_user":
        msg=bot.send_message(chat_id,"🔎 Send user ID or @username:\n\n/cancel to abort")
        bot.register_next_step_handler(msg, lambda m: admin_search_user_result(m.chat.id,m.text) if (m.text or '').strip()!='/cancel' else bot.send_message(m.chat.id,'❌ Cancelled.'))
        bot.answer_callback_query(call.id); return
    if data == "admin_export_users":
        try: admin_export_users(chat_id); bot.answer_callback_query(call.id,"Export sent")
        except Exception as e: bot.answer_callback_query(call.id,"Export failed"); bot.send_message(chat_id,f"❌ Export failed: {html_lib.escape(str(e))}")
        return
    if data == "admin_message_user":
        msg=bot.send_message(chat_id,"💬 Send user ID or @username:\n\n/cancel to abort"); bot.register_next_step_handler(msg,admin_message_user_receive); bot.answer_callback_query(call.id); return
    if data == "admin_restart_all_confirm":
        admin_restart_all_confirm(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_restart_all":
        bot.answer_callback_query(call.id,"Restarting..."); admin_restart_all(chat_id,call.message.message_id); return
    if data == "admin_user_files_set_menu":
        admin_user_files_set_menu(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("admin_user_files_set_page:"):
        page = int(data.split(':')[1])
        admin_user_files_set_menu(chat_id, page, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    if data == "admin_auto_stop_menu":
        admin_auto_stop_menu(chat_id, call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_auto_stop_users":
        admin_auto_stop_users_menu(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("admin_auto_stop_users_page:"):
        admin_auto_stop_users_menu(chat_id, int(data.split(':')[1]), call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("admin_user_files_autostop:"):
        uid = int(data.split(':')[1])
        msg = bot.send_message(
            chat_id,
            f"📂 <b>User Files Auto Stop</b>\n\n👤 User ID: <code>{uid}</code>\n"
            "This will set the SAME timer on every file of this user.\n\n"
            "Send duration: <code>30 minutes</code>, <code>2 hours</code>, or <code>1 day</code>.\n"
            "/cancel to abort"
        )
        bot.register_next_step_handler(msg, admin_user_files_autostop_receive, uid)
        bot.answer_callback_query(call.id)
        return
    if data == "admin_global_autostop_set":
        msg=bot.send_message(chat_id, "⏰ <b>Global Auto Stop</b>\n\nSend duration, e.g. <code>30 minutes</code>, <code>2 hours</code>, <code>1 day</code>.\n/cancel to abort")
        bot.register_next_step_handler(msg, admin_global_autostop_receive); bot.answer_callback_query(call.id); return
    if data == "admin_global_autostop_clear":
        clear_global_auto_stop(); log_admin('global_auto_stop_clear'); admin_auto_stop_menu(chat_id, call.message.message_id); bot.answer_callback_query(call.id, 'Timer cancelled.'); return
    if data.startswith("admin_user_autostop:"):
        uid=int(data.split(':')[1]); admin_user_autostop_menu(chat_id, uid, call.message.message_id); bot.answer_callback_query(call.id); return
    if data.startswith("admin_user_autostop_set:"):
        uid=int(data.split(':')[1]); msg=bot.send_message(chat_id, f"⏰ <b>User Auto Stop</b>\n\n👤 User ID: <code>{uid}</code>\nSend duration: <code>30 minutes</code>, <code>2 hours</code>, or <code>1 day</code>.\n/cancel to abort")
        bot.register_next_step_handler(msg, admin_user_autostop_receive, uid); bot.answer_callback_query(call.id); return
    if data.startswith("admin_user_autostop_clear:"):
        uid=int(data.split(':')[1]); clear_user_auto_stop(uid); log_admin('user_auto_stop_clear',uid); admin_user_autostop_menu(chat_id, uid, call.message.message_id); bot.answer_callback_query(call.id, 'Timer cancelled.'); return
    if data.startswith("admin_user_files_set:"):
        uid = int(data.split(':')[1])
        cur = conn.cursor()
        cur.execute("SELECT username,max_files FROM users WHERE user_id=?", (uid,))
        u = cur.fetchone()
        if not u:
            bot.answer_callback_query(call.id, "❌ User not found.")
            return
        current = u["max_files"] if u["max_files"] is not None else effective_max_files()
        msg = bot.send_message(
            chat_id,
            f"💀 <b>User Fills Set</b>\n\n"
            f"👤 User: <b>{html_lib.escape(u['username'] or str(uid))}</b>\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📁 Current limit: <b>{current}</b>\n\n"
            "Send the maximum number of files this user can upload (1-500).\n"
            "This changes only this user's limit.\n/cancel to abort"
        )
        bot.register_next_step_handler(msg, admin_user_files_set_receive, uid)
        bot.answer_callback_query(call.id)
        return
    if data.startswith("admin_profile:"):
        admin_profile(chat_id,int(data.split(':')[1]),call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_processes":
        admin_processes(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_process_on":
        admin_process_on(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_start_all":
        bot.answer_callback_query(call.id, "🚀 Starting all stopped files...")
        admin_start_all(chat_id, call.message.message_id)
        return
    if data == "admin_stop_all_confirm":
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton('⚠️ YES, STOP ALL',callback_data='admin_stop_all'),InlineKeyboardButton('❌ Cancel',callback_data='admin_processes'))
        _edit_or_send(chat_id,call.message.message_id,'⚠️ <b>Confirm STOP ALL</b>\n\nThis will stop every currently running hosted process.',kb); bot.answer_callback_query(call.id); return
    if data == "admin_stop_all":
        count=0
        for fid in list_process_ids(): stop_file_process(fid); count+=1
        log_admin('stop_all',count); admin_processes(chat_id,call.message.message_id); bot.answer_callback_query(call.id,f'Stopped {count}'); return
    if data == "admin_system":
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton('🔄 Refresh',callback_data='admin_system'),InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
        _edit_or_send(chat_id,call.message.message_id,admin_system_text(),kb); bot.answer_callback_query(call.id); return
    if data == "admin_settings":
        admin_settings_menu(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_toggle_maintenance":
        val=not maintenance_enabled(); set_setting('maintenance','1' if val else '0'); log_admin('maintenance',val); admin_settings_menu(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_toggle_python":
        val=not python_approval_enabled(); set_python_approval(val); log_admin('python_approval',val); admin_settings_menu(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_toggle_premium_panel":
        val=not premium_panel_enabled(); set_premium_panel_enabled(val); log_admin('premium_panel',val); admin_settings_menu(chat_id,call.message.message_id); bot.answer_callback_query(call.id, 'Premium panel '+('enabled' if val else 'hidden')); return
    if data == "admin_set_max_files":
        msg=bot.send_message(chat_id,'📁 Send new max files per user (1-500):\n\n/cancel to abort')
        bot.register_next_step_handler(msg, admin_set_max_files_receive); bot.answer_callback_query(call.id); return
    if data == "admin_broadcast_menu":
        admin_broadcast_menu(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data.startswith('admin_broadcast:'):
        mode=data.split(':',1)[1]; msg=bot.send_message(chat_id,f'📢 <b>{mode.upper()}</b> broadcast selected.\nSend the message/media now.\n/cancel to abort')
        bot.register_next_step_handler(msg,broadcast_advanced_receive,mode); bot.answer_callback_query(call.id); return
    if data == "admin_set_how_to_use":
        msg = bot.send_message(chat_id, f"📖 <b>Set How To Use Bot Link</b>\n\nCurrent: <code>{html_lib.escape(how_to_use_link())}</code>\n\nSend the new full URL.\n/cancel to abort")
        bot.register_next_step_handler(msg, admin_set_how_to_use_link_receive)
        bot.answer_callback_query(call.id)
        return
    if data == "admin_backup":
        try: admin_backup(chat_id); bot.answer_callback_query(call.id,'Backup sent')
        except Exception as e: bot.answer_callback_query(call.id,'Backup failed'); bot.send_message(chat_id,f'❌ Backup failed: {html_lib.escape(str(e))}')
        return
    if data == "admin_logs":
        admin_logs_view(chat_id,call.message.message_id); bot.answer_callback_query(call.id); return
    if data == "admin_clear_logs_confirm":
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton('⚠️ CLEAR',callback_data='admin_clear_logs'),InlineKeyboardButton('❌ Cancel',callback_data='admin_logs'))
        _edit_or_send(chat_id,call.message.message_id,'⚠️ Clear admin logs?',kb); bot.answer_callback_query(call.id); return
    if data == "admin_clear_logs":
        with db_lock: conn.execute('DELETE FROM admin_logs'); conn.commit()
        bot.answer_callback_query(call.id,'Logs cleared'); admin_logs_view(chat_id,call.message.message_id); return
    if data == "admin_cleanup":
        kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton('🧹 Cleanup Old Logs',callback_data='admin_cleanup_logs'),InlineKeyboardButton('🗃 Cleanup Old Runs',callback_data='admin_cleanup_runs'))
        kb.add(InlineKeyboardButton('🔙 Back',callback_data='admin_back'))
        _edit_or_send(chat_id,call.message.message_id,'🧹 <b>CLEANUP TOOLS</b>\n\nRemoves admin/activity logs older than 30 days. Hosted files are not deleted.',kb); bot.answer_callback_query(call.id); return
    if data == "admin_cleanup_runs":
        admin_cleanup_dead_runs(chat_id); bot.answer_callback_query(call.id,"Cleanup complete"); return
    if data == "admin_cleanup_logs":
        cutoff=(datetime.utcnow()-timedelta(days=30)).isoformat()
        with db_lock:
            a=conn.execute('DELETE FROM admin_logs WHERE created_at<?',(cutoff,)).rowcount
            b=conn.execute('DELETE FROM activity_logs WHERE created_at<?',(cutoff,)).rowcount
            conn.commit()
        log_admin('cleanup_logs', f'admin={a},activity={b}')
        bot.answer_callback_query(call.id,'Cleanup complete'); admin_settings_menu(chat_id,call.message.message_id); return

    if data == "admin_dashboard":
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users"); total_users = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM users WHERE blocked=1"); blocked = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM files"); total_files = cur.fetchone()[0] or 0
        with proc_lock:
            running = sum(1 for e in processes.values() if e.get('process') and e['process'].poll() is None)
        cpu, mem, _ = get_system_load()
        uptime = datetime.utcnow() - START_TIME
        bot.send_message(chat_id,
            f"📊 <b>Advanced Dashboard</b>\n\n"
            f"👥 Users: <b>{total_users}</b>\n"
            f"🚫 Blocked: <b>{blocked}</b>\n"
            f"📁 Files: <b>{total_files}</b>\n"
            f"🟢 Running: <b>{running}</b>/{MAX_RUNNING_PROCESSES}\n"
            f"⚡ CPU: <b>{cpu:.1f}%</b>\n"
            f"💾 RAM: <b>{mem:.1f}%</b>\n"
            f"⏱ Uptime: <b>{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m</b>")
        bot.answer_callback_query(call.id)

    elif data == "admin_analytics":
        cur = conn.cursor()
        now = datetime.utcnow()
        def count_since(days):
            since = (now - __import__('datetime').timedelta(days=days)).isoformat()
            cur.execute("SELECT COUNT(*) FROM users WHERE joined_at>=?", (since,))
            return cur.fetchone()[0] or 0
        bot.send_message(chat_id,
            "📈 <b>Analytics</b>\n\n"
            f"🆕 New users (24h): <b>{count_since(1)}</b>\n"
            f"🆕 New users (7d): <b>{count_since(7)}</b>\n"
            f"🆕 New users (30d): <b>{count_since(30)}</b>")
        bot.answer_callback_query(call.id)

    elif data == "admin_total_users":
        cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM users")
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"👥 Total users: {cur.fetchone()[0] or 0}")

    elif data == "admin_total_files":
        cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM files")
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"📁 Total files: {cur.fetchone()[0] or 0}")

    elif data == "admin_view_users":
        admin_view_users(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_manage_users":
        admin_manage_users(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_db_manager":
        admin_db_manager(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_db_user:"):
        admin_view_user_files(chat_id, int(data.split(":")[1]), 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_manage_files":
        admin_manage_files_list(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_stop_process":
        admin_manage_files_list(chat_id, 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_broadcast":
        msg = bot.send_message(
            chat_id,
            "📢 <b>Broadcast Mode</b>\n\nSend <b>any one</b> of these:\n💬 Message / Text\n🎙️ Voice\n🎨 Sticker\n🖼️ Photo\n🎬 Video\n🎵 Audio\n📄 Document\n\n/cancel to abort"
        )
        bot.register_next_step_handler(msg, broadcast_send)
        bot.answer_callback_query(call.id)

    elif data in ("admin_python_approval_on", "admin_python_approval_off"):
        enabled = data == "admin_python_approval_on"
        set_python_approval(enabled)
        bot.answer_callback_query(call.id, "Python Approval " + ("ON 🟢" if enabled else "OFF 🔴"))
        try: bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=admin_panel_kb())
        except Exception: pass

    elif data == "admin_exit":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👋 Exited admin panel.", reply_markup=main_menu_kb())

    elif data.startswith("admin_users_page:"):
        page = int(data.split(":")[1])
        admin_view_users(chat_id, page, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_db_manager_page:"):
        page = int(data.split(":")[1])
        admin_db_manager(chat_id, page, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_block_user:"):
        uid = int(data.split(":")[1])
        if uid == ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Cannot block Admin.")
        else:
            with db_lock:
                cur = conn.cursor()
                cur.execute("SELECT blocked FROM users WHERE user_id=?", (uid,))
                row = cur.fetchone()
                was_blocked = bool(row["blocked"]) if row else False
                conn.execute("UPDATE users SET blocked=1 WHERE user_id=?", (uid,))
                conn.commit()

            # Notify the affected user immediately after the status changes.
            if not was_blocked:
                try:
                    bot.send_message(
                        uid,
                        "🚫 <b>You have been blocked by the Admin.</b>\n\n"
                        "You can no longer use this bot.\n"
                        "If you think this was a mistake, please contact the Admin."
                    )
                except Exception:
                    logging.exception("Block notification failed for user %s", uid)

            bot.answer_callback_query(call.id, "🚫 User blocked.")
            admin_manage_users(chat_id, 0, call.message.message_id)

    elif data.startswith("admin_unblock_user:"):
        uid = int(data.split(":")[1])
        with db_lock:
            cur = conn.cursor()
            cur.execute("SELECT blocked FROM users WHERE user_id=?", (uid,))
            row = cur.fetchone()
            was_blocked = bool(row["blocked"]) if row else False
            conn.execute("UPDATE users SET blocked=0 WHERE user_id=?", (uid,))
            conn.commit()

        # Notify the affected user immediately after the status changes.
        if was_blocked:
            try:
                bot.send_message(
                    uid,
                    "✅ <b>You have been unblocked by the Admin.</b>\n\n"
                    "You can use the bot again. Welcome back! 🤗"
                )
            except Exception:
                logging.exception("Unblock notification failed for user %s", uid)

        bot.answer_callback_query(call.id, "✅ User unblocked.")
        admin_manage_users(chat_id, 0, call.message.message_id)

    elif data.startswith("admin_users_manage_page:"):
        page = int(data.split(":")[1])
        admin_manage_users(chat_id, page, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_user_files:"):
        admin_view_user_files(chat_id, int(data.split(":")[1]), 0, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_user_files_page:"):
        _, uid, pg = data.split(":")
        admin_view_user_files(chat_id, int(uid), int(pg), call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_files_page:"):
        page = int(data.split(":")[1])
        admin_manage_files_list(chat_id, page, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_download_file:"):
        admin_download_file(chat_id, int(data.split(":")[1]), call.id)

    elif data.startswith("admin_download_db:"):
        admin_download_db(chat_id, int(data.split(":")[1]), call.id)

    elif data.startswith("admin_upload_db:"):
        bot.answer_callback_query(call.id, "📤 Send .db file")
        admin_upload_db_prompt(chat_id, int(data.split(":")[1]))

    elif data.startswith("admin_delete_file_confirm:"):
        fid = int(data.split(":")[1])
        bot.answer_callback_query(call.id, "🗑️ Deleting...")
        admin_delete_file(chat_id, fid, call.message.message_id)

    elif data.startswith("admin_delete_file:"):
        fid = int(data.split(":")[1])
        admin_delete_file_confirm(chat_id, fid, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data.startswith("admin_file_autostop:"):
        fid = int(data.split(":")[1])
        rec = get_file_record(fid)
        if not rec:
            bot.answer_callback_query(call.id, "❌ File not found.")
        else:
            msg = bot.send_message(
                chat_id,
                f"⏰ <b>File Auto Stop</b>\n\n"
                f"📄 File: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
                "Send duration: <code>30 minutes</code>, <code>2 hours</code>, or <code>1 day</code>.\n"
                "/cancel to abort"
            )
            bot.register_next_step_handler(msg, admin_file_autostop_receive, fid)
            bot.answer_callback_query(call.id)
        return

    elif data.startswith("admin_stop_file:"):
        fid = int(data.split(":")[1])
        stop_file_process(fid)
        bot.answer_callback_query(call.id, "✅ Stopped.")
        admin_manage_files_list(chat_id, 0, call.message.message_id)

    elif data.startswith("admin_start_file:"):
        fid = int(data.split(":")[1])
        rec = get_file_record(fid)
        if not rec:
            bot.answer_callback_query(call.id, "❌ File not found.")
        else:
            bot.answer_callback_query(call.id, "▶️ Starting...")
            start_file_process(fid, chat_id)
            time.sleep(1)
            admin_process_on(chat_id, call.message.message_id)

    elif data == "admin_back":
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=admin_panel_kb())
        bot.answer_callback_query(call.id)

    else:
        bot.answer_callback_query(call.id, "Unknown action")

# ── Admin Helpers ─────────────────────────────────────────
def admin_manage_users(chat_id, page=0, message_id=None):
    cur = conn.cursor(); cur.execute("SELECT user_id,username,blocked FROM users ORDER BY user_id")
    users = cur.fetchall(); per_page = 20
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_users = users[page*per_page:(page+1)*per_page]
    text = f"👥 <b>Manage Users (Page {page+1}/{total_pages})</b>\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for u in page_users:
        name = html_lib.escape(u['username'] or str(u['user_id']))
        state = "🚫 BLOCKED" if u['blocked'] else "🟢 ACTIVE"
        text += f"👤 <b>{name}</b> | ID: <code>{u['user_id']}</code> | {state}\n"
        if u['user_id'] != ADMIN_ID:
            if u['blocked']:
                kb.add(InlineKeyboardButton(f"✅ UNBLOCK • {name[:20]}", callback_data=f"admin_unblock_user:{u['user_id']}"))
            else:
                kb.add(InlineKeyboardButton(f"🚫 BLOCK • {name[:20]}", callback_data=f"admin_block_user:{u['user_id']}"))
            kb.add(InlineKeyboardButton(f"👤 PROFILE / TIMER • {name[:18]}", callback_data=f"admin_profile:{u['user_id']}"))
        else:
            text += "🔐 Admin account cannot be blocked.\n"
    if page > 0: kb.add(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users_manage_page:{page-1}"))
    if page < total_pages-1: kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"admin_users_manage_page:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    _edit_or_send(chat_id, message_id, text, kb)

def admin_db_manager(chat_id, page=0, message_id=None):
    """Dedicated admin DB manager: select a user, then manage that user's project DB files."""
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM users ORDER BY user_id")
    users = cur.fetchall()

    # DB Manager is intentionally a single page (1/1).
    total_pages = 1
    page = 0
    page_users = users

    text = "🗄️ <b>DB Manager</b> — Page 1/1\n\n"
    text += "Select a user to view their projects and manage .db files.\n"

    kb = InlineKeyboardMarkup(row_width=1)
    for u in page_users:
        uid = u["user_id"]
        name = html_lib.escape(u["username"] or str(uid))
        cur.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (uid,))
        file_count = cur.fetchone()[0] or 0
        text += f"\n👤 <b>{name}</b> | ID: <code>{uid}</code> | 📁 {file_count} projects"
        kb.add(InlineKeyboardButton(
            f"🗄️ {name[:24]}",
            callback_data=f"admin_db_user:{uid}"
        ))

    # No Prev/Next buttons: DB Manager always stays on Page 1/1.
    kb.add(InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_back"))

    _edit_or_send(chat_id, message_id, text, kb)


def admin_view_users(chat_id, page=0, message_id=None):
    cur = conn.cursor(); cur.execute("SELECT user_id,username,joined_at FROM users ORDER BY user_id")
    users = cur.fetchall(); per_page = 20
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    page_users  = users[page*per_page:(page+1)*per_page]
    text = f"👥 <b>Users (Page {page+1}/{total_pages})</b>\n\n"
    for u in page_users:
        text += f"👤 <b>{html_lib.escape(u['username'] or 'None')}</b> (ID: <code>{u['user_id']}</code>)\n"
    kb = InlineKeyboardMarkup()
    for u in page_users:
        kb.add(InlineKeyboardButton(f"📂 {html_lib.escape(u['username'] or str(u['user_id']))}",
                                    callback_data=f"admin_user_files:{u['user_id']}"))
    if page > 0:              kb.add(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users_page:{page-1}"))
    if page < total_pages-1:  kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"admin_users_page:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    _edit_or_send(chat_id, message_id, text, kb)

def admin_view_user_files(chat_id, user_id, page=0, message_id=None):
    cur = conn.cursor()
    cur.execute("SELECT id,orig_name,file_type,status FROM files WHERE user_id=? ORDER BY id DESC", (user_id,))
    files = cur.fetchall(); per_page = 500
    total_pages = max(1, (len(files) + per_page - 1) // per_page)
    page_files  = files[page*per_page:(page+1)*per_page]
    cur.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone(); username = row["username"] if row else "Unknown"
    text = f"📂 <b>{html_lib.escape(username)} (ID {user_id})</b> — Page {page+1}/{total_pages}\n\n"
    for f in page_files:
        running = is_file_running(f['id'])
        live_status = "🟢 START / Running" if running else "🔴 STOP / Stopped"
        text += f"📄 <b>{html_lib.escape(f['orig_name'])}</b> | {f['file_type']} | {live_status}\n"
    kb = InlineKeyboardMarkup()
    for f in page_files:
        kb.add(InlineKeyboardButton(f"⬇️ {html_lib.escape(f['orig_name'])}", callback_data=f"admin_download_file:{f['id']}"))
        kb.row(
            InlineKeyboardButton("🗄️ GET .db", callback_data=f"admin_download_db:{f['id']}"),
            InlineKeyboardButton("📤 UPLOAD .db", callback_data=f"admin_upload_db:{f['id']}")
        )
        kb.add(InlineKeyboardButton("⏰ Set File Auto Stop", callback_data=f"admin_file_autostop:{f['id']}"))
        kb.add(InlineKeyboardButton("🗑️ DELETE FILE", callback_data=f"admin_delete_file:{f['id']}"))
    if page > 0:              kb.add(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_user_files_page:{user_id}:{page-1}"))
    if page < total_pages-1:  kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"admin_user_files_page:{user_id}:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Users", callback_data="admin_view_users"))
    _edit_or_send(chat_id, message_id, text, kb)

def admin_delete_file_confirm(chat_id, file_id, message_id=None):
    """Show a confirmation before permanently deleting a user's hosted file."""
    rec = get_file_record(file_id)
    if not rec:
        _edit_or_send(chat_id, message_id, "❌ File not found.", admin_panel_kb())
        return
    running = is_file_running(file_id)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚠️ YES, DELETE", callback_data=f"admin_delete_file_confirm:{file_id}"),
        InlineKeyboardButton("❌ CANCEL", callback_data="admin_manage_files")
    )
    text = (
        "⚠️ <b>DELETE FILE?</b>\n\n"
        f"📄 File: <b>{html_lib.escape(rec['orig_name'] or str(file_id))}</b>\n"
        f"👤 User ID: <code>{rec['user_id']}</code>\n"
        f"📊 Status: <b>{'🟢 Running' if running else '🔴 Stopped'}</b>\n\n"
        "This permanently removes the hosted file/project and its database record.\n"
        "<b>This action cannot be undone.</b>"
    )
    _edit_or_send(chat_id, message_id, text, kb)


def admin_delete_file(chat_id, file_id, message_id=None):
    """Stop, remove files from disk, and delete the file DB record."""
    rec = get_file_record(file_id)
    if not rec:
        bot.answer_callback_query(message_id, "❌ File already deleted.") if message_id else None
        return

    # Stop a live hosted process first so it cannot recreate/use the deleted file.
    try:
        if is_file_running(file_id):
            stop_file_process(file_id)
    except Exception:
        logger.exception("Failed stopping file before admin deletion: %s", file_id)

    path = rec["path"]
    removed_disk = False
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed_disk = not os.path.exists(path)
        elif path and os.path.isfile(path):
            os.remove(path)
            removed_disk = True
    except Exception as e:
        logger.error("Admin file disk delete error %s: %s", file_id, e)

    # Remove associated run history and the hosted-file record.
    with db_lock:
        conn.execute("DELETE FROM runs WHERE file_id=?", (file_id,))
        conn.execute("DELETE FROM files WHERE id=?", (file_id,))
        conn.commit()

    log_admin("delete_file", f"file={file_id},user={rec['user_id']},disk_removed={removed_disk}")
    try:
        bot.send_message(
            rec["user_id"],
            f"🗑️ <b>File Deleted by Admin</b>\n\n"
            f"📄 File: <b>{html_lib.escape(rec['orig_name'] or str(file_id))}</b>\n"
            "Your hosted file has been permanently removed by the Admin."
        )
    except Exception:
        pass

    bot.send_message(
        chat_id,
        f"✅ <b>File deleted successfully.</b>\n\n"
        f"📄 {html_lib.escape(rec['orig_name'] or str(file_id))}\n"
        f"👤 User ID: <code>{rec['user_id']}</code>\n"
        f"💾 Disk removed: <b>{'YES' if removed_disk else 'NO / already missing'}</b>",
        reply_markup=admin_panel_kb()
    )


def admin_download_file(chat_id, file_id, callback_id=None):
    rec = get_file_record(file_id)
    if not rec:
        if callback_id: bot.answer_callback_query(callback_id, "File not found.")
        return
    if callback_id: bot.answer_callback_query(callback_id, "Sending...")
    fp = rec["path"]
    if os.path.isdir(fp):
        zp = os.path.join(TEMP_DIR, f"adl_{file_id}.zip")
        shutil.make_archive(zp.replace('.zip',''), 'zip', fp)
        with open(zp,'rb') as f: bot.send_document(chat_id, f, caption=f"📦 {rec['orig_name']}")
        os.remove(zp)
    elif os.path.exists(fp):
        with open(fp,'rb') as f: bot.send_document(chat_id, f, caption=f"📄 {rec['orig_name']}")
    else:
        bot.send_message(chat_id, "❌ File not found on disk.")

def _resolve_legacy_db_for_record(rec):
    """Find the DB that actually belongs to this hosted project.

    DBs created by a hosted script are often not uploaded through the bot's
    "Upload .db" button; the script creates them directly while running.
    Plain .py/.js projects share the user's upload directory, so we must use
    the project's source code to identify a referenced *.db when several DBs
    exist. For isolated ZIP projects, a DB inside that project directory is
    also safe to use.
    """
    saved = rec["db_path"] if "db_path" in rec.keys() else None
    if saved and os.path.isfile(str(saved)) and str(saved).lower().endswith(".db"):
        return str(saved)

    fp = str(rec["path"] or "")
    target_dir = fp if os.path.isdir(fp) else os.path.dirname(fp)
    if not target_dir or not os.path.isdir(target_dir):
        return None

    candidates = []
    try:
        for root, _, files in os.walk(target_dir):
            for name in files:
                if name.lower().endswith(".db"):
                    candidates.append(os.path.join(root, name))
    except OSError:
        return None
    if not candidates:
        return None

    # 1) Exact project/source filename match.
    project_names = set()
    for key in ("orig_name", "filename"):
        value = str(rec[key] or "").strip() if key in rec.keys() else ""
        if value:
            project_names.add(os.path.splitext(os.path.basename(value))[0].lower())
    if "orig_name" in rec.keys() and rec["orig_name"]:
        project_names.add(str(rec["orig_name"]).strip().lower())
    exact = [p for p in candidates if os.path.splitext(os.path.basename(p))[0].lower() in project_names]
    if len(exact) == 1:
        return exact[0]

    # 2) Read the project's own Python/JS source and look for literal DB names.
    # This handles common cases such as sqlite3.connect("bot.db"),
    # sqlite.connect('data.db'), new Database('app.db'), etc.
    import re
    source_files = []
    if os.path.isfile(fp) and fp.lower().endswith((".py", ".js")):
        source_files.append(fp)
    elif os.path.isdir(fp):
        try:
            for root, _, files in os.walk(fp):
                for name in files:
                    if name.lower().endswith((".py", ".js")):
                        source_files.append(os.path.join(root, name))
        except OSError:
            pass
    db_refs = set()
    for src in source_files:
        try:
            with open(src, "r", encoding="utf-8", errors="ignore") as f:
                text_src = f.read()
            for m in re.finditer(r"[\"']([^\"']+?\.db)[\"']", text_src, re.I):
                ref = os.path.basename(m.group(1).strip()).lower()
                if ref:
                    db_refs.add(ref)
        except Exception:
            pass
    if db_refs:
        referenced = [p for p in candidates if os.path.basename(p).lower() in db_refs]
        if len(referenced) == 1:
            return referenced[0]
        # Also allow a DB referenced by an absolute/relative path where the
        # basename is unique among the actual files.
        for ref in db_refs:
            matches = [p for p in candidates if os.path.basename(p).lower() == ref]
            if len(matches) == 1:
                return matches[0]

    # 3) An isolated project folder containing exactly one DB is deterministic.
    user_root = os.path.abspath(os.path.join(UPLOADS_DIR, str(rec["user_id"])))
    target_abs = os.path.abspath(target_dir)
    if target_abs != user_root and len(candidates) == 1:
        return candidates[0]

    # 4) A plain upload directory with exactly one DB is also unambiguous.
    if len(candidates) == 1:
        return candidates[0]

    return None

def _attach_resolved_db(rec, db_path):
    """Persist a recovered legacy DB so future downloads are exact."""
    if not db_path or not os.path.isfile(db_path):
        return False
    try:
        with db_lock:
            conn.execute("UPDATE files SET db_path=? WHERE id=?", (db_path, rec["id"]))
            conn.commit()
        return True
    except Exception:
        logger.exception("Could not save recovered db_path for file %s", rec["id"])
        return False


def _find_db_files_for_record(rec):
    db_path = _resolve_legacy_db_for_record(rec)
    if db_path:
        _attach_resolved_db(rec, db_path)
        return [db_path]
    return []


def admin_download_db(chat_id, file_id, callback_id=None):
    rec = get_file_record(file_id)
    if not rec:
        if callback_id: bot.answer_callback_query(callback_id, "❌ File not found.")
        return
    db_files = _find_db_files_for_record(rec)
    if not db_files:
        if callback_id: bot.answer_callback_query(callback_id, "No .db found.")
        bot.send_message(chat_id, f"❌ No <b>.db</b> file found for <b>{html_lib.escape(rec['orig_name'])}</b>.")
        return
    if callback_id: bot.answer_callback_query(callback_id, "🗄️ Sending .db...")
    sent = 0
    for db_path in db_files:
        try:
            with open(db_path, "rb") as df:
                bot.send_document(
                    chat_id, df,
                    caption=(
                        f"🗄️ <b>Database</b>\n"
                        f"📄 Project: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
                        f"👤 User ID: <code>{rec['user_id']}</code>\n"
                        f"📁 File: <code>{html_lib.escape(os.path.basename(db_path))}</code>"
                    )
                )
            sent += 1
        except Exception as e:
            logger.error(f"Admin DB download error: {e}")
    log_admin("admin_download_db", f"user={rec['user_id']},file={file_id},count={sent}")


def admin_upload_db_received(message, file_id):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Not authorized.")
        return
    rec = get_file_record(file_id)
    if not rec:
        bot.reply_to(message, "❌ File not found.")
        return
    if message.content_type == "text" and (message.text or "").strip() == "/cancel":
        bot.send_message(message.chat.id, "❌ DB upload cancelled.", reply_markup=admin_panel_kb())
        return
    if not message.document or not (message.document.file_name or "").lower().endswith(".db"):
        bot.reply_to(message, "❌ Sirf <b>.db</b> file upload karo.\n\n/cancel to abort.")
        bot.register_next_step_handler(message, admin_upload_db_received, file_id)
        return
    try:
        info = bot.get_file(message.document.file_id)
        data = bot.download_file(info.file_path)
        fp = rec["path"]
        target_dir = fp if os.path.isdir(fp) else os.path.dirname(fp)
        os.makedirs(target_dir, exist_ok=True)
        db_name = os.path.basename(message.document.file_name)
        old_db = rec["db_path"] if "db_path" in rec.keys() else None
        db_path = os.path.join(target_dir, db_name)
        if os.path.exists(db_path) and os.path.abspath(db_path) != os.path.abspath(old_db or ""):
            stem, ext = os.path.splitext(db_name)
            db_path = os.path.join(target_dir, f"db_{file_id}_{stem}{ext}")
        with open(db_path, "wb") as f:
            f.write(data)
        with db_lock:
            conn.execute("UPDATE files SET db_path=? WHERE id=?", (db_path, file_id))
            conn.commit()

        was_running = is_file_running(file_id)
        if was_running:
            stop_file_process(file_id)
            time.sleep(1)
            start_file_process(file_id, rec["user_id"])

        log_admin("admin_upload_db", f"user={rec['user_id']},file={file_id},db={db_name}")
        bot.send_message(
            message.chat.id,
            f"✅ <b>.db uploaded successfully!</b>\n\n"
            f"👤 User ID: <code>{rec['user_id']}</code>\n"
            f"📄 Project: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
            f"🗄️ Database: <b>{html_lib.escape(db_name)}</b>\n"
            f"{'🔄 Project restarted automatically.' if was_running else '▶️ Start/Restart the project to use it.'}",
            reply_markup=admin_panel_kb()
        )
        try:
            bot.send_message(
                rec["user_id"],
                f"🗄️ <b>Admin uploaded a .db file</b>\n\n"
                f"📄 Project: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
                f"🗄️ Database: <b>{html_lib.escape(db_name)}</b>"
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Admin DB upload error for file {file_id}: {e}")
        bot.reply_to(message, f"❌ .db upload failed: {html_lib.escape(str(e))}")


def admin_upload_db_prompt(chat_id, file_id):
    rec = get_file_record(file_id)
    if not rec:
        bot.send_message(chat_id, "❌ File not found.")
        return
    msg = bot.send_message(
        chat_id,
        "📤 <b>Admin — Upload .db</b>\n\n"
        f"👤 User ID: <code>{rec['user_id']}</code>\n"
        f"📄 Project: <b>{html_lib.escape(rec['orig_name'])}</b>\n\n"
        "Ab is project ke liye <b>.db</b> file bhejo.\n"
        "Existing same-name .db replace ho jayegi.\n\n"
        "/cancel to abort."
    )
    bot.register_next_step_handler(msg, admin_upload_db_received, file_id)


def admin_manage_files_list(chat_id, page=0, message_id=None):
    cur = conn.cursor()
    cur.execute("SELECT id,orig_name,user_id,status,approval_status FROM files ORDER BY id DESC")
    files = cur.fetchall()
    per_page = 50
    total_pages = max(1, (len(files) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_files = files[page*per_page:(page+1)*per_page]

    text = f"📁 <b>Manage Files (Page {page+1}/{total_pages})</b>\n\n"
    kb = InlineKeyboardMarkup(row_width=1)

    if not page_files:
        text += "No files uploaded yet."
    else:
        for f in page_files:
            # IMPORTANT: status is based on the actual live process, not the DB flag.
            running = is_file_running(f['id'])
            # Short status display; the action button below shows START/STOP.
            status = "🟢 ON" if running else "🔴 OFF"
            if f['approval_status'] == 'pending':
                status += " | ⏳ Pending Approval"
            elif f['approval_status'] == 'rejected':
                status += " | ❌ Rejected"
            text += (f"📄 <b>{html_lib.escape(f['orig_name'])}</b>\n"
                     f"👤 User ID: <code>{f['user_id']}</code>\n"
                     f"📊 Status: {status}\n\n")
            if running:
                kb.add(InlineKeyboardButton(
                    f"🔴 STOP • {f['orig_name'][:25]}",
                    callback_data=f"admin_stop_file:{f['id']}"))
            elif f['approval_status'] == 'approved':
                kb.add(InlineKeyboardButton(
                    f"🟢 START • {f['orig_name'][:25]}",
                    callback_data=f"admin_start_file:{f['id']}"))
            # Admin can permanently remove any user's hosted file.
            kb.add(InlineKeyboardButton(
                f"🗑️ DELETE • {f['orig_name'][:25]}",
                callback_data=f"admin_delete_file:{f['id']}"))

    if page > 0:
        kb.add(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_files_page:{page-1}"))
    if page < total_pages - 1:
        kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"admin_files_page:{page+1}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    _edit_or_send(chat_id, message_id, text, kb)


def admin_stop_process_list(chat_id, message_id=None):
    cur = conn.cursor()
    cur.execute("SELECT id,orig_name,user_id FROM files WHERE status='Running'")
    running = cur.fetchall()
    if not running:
        _edit_or_send(chat_id, message_id, "✅ No running processes.", None)
        return
    text = "🛑 <b>Running Processes</b>\n\nSelect to stop:\n"
    kb   = InlineKeyboardMarkup()
    for f in running:
        kb.add(InlineKeyboardButton(f"🛑 {html_lib.escape(f['orig_name'])} (User {f['user_id']})",
                                    callback_data=f"admin_stop_file:{f['id']}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    _edit_or_send(chat_id, message_id, text, kb)

def broadcast_send(message):
    # Broadcast accepts any single Telegram message type (text, voice, sticker, photo, video, audio, document, etc.).
    if message.content_type == "text" and (message.text or "").strip() == "/cancel":
        bot.send_message(message.chat.id, "❌ Cancelled."); return

    cur = conn.cursor(); cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    bot.send_message(message.chat.id, f"📢 Broadcasting to {len(users)} users...")
    ok = fail = 0
    for row in users:
        try:
            # Copy the original message so Telegram preserves its media/type and caption.
            bot.copy_message(row[0], message.chat.id, message.message_id)
            ok += 1
        except Exception as e:
            fail += 1
        time.sleep(0.05)
    bot.send_message(message.chat.id, f"✅ Broadcast complete. Success: {ok} | Failed: {fail}")

def _edit_or_send(chat_id, message_id, text, kb):
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb); return
        except: pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ── File Approval Callbacks ─────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve_py:", "reject_py:")))
def python_approval_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Not authorized.")
        return

    try:
        action, fid_text = call.data.split(":", 1)
        file_id = int(fid_text)
        rec = get_file_record(file_id)
        if not rec:
            bot.answer_callback_query(call.id, "File not found.")
            return

        if rec["approval_status"] != "pending":
            bot.answer_callback_query(call.id, f"Already {rec['approval_status']}.")
            return

        if action == "approve_py":
            with db_lock:
                conn.execute("UPDATE files SET approval_status='approved' WHERE id=?", (file_id,))
                conn.commit()
            bot.answer_callback_query(call.id, "✅ Applied")
            try:
                bot.edit_message_caption(
                    "📥 <b>File APPROVED</b>\n\n"
                    f"📄 File: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
                    f"👤 User ID: <code>{rec['user_id']}</code>\n"
                    f"🔖 File ID: <code>{file_id}</code>\n\n"
                    "✅ Status: Applied / Starting",
                    call.message.chat.id, call.message.message_id
                )
            except Exception:
                pass
            bot.send_message(rec["user_id"], f"✅ Admin approved your .py file: <b>{html_lib.escape(rec['orig_name'])}</b>\n\n⏳ Starting now...")
            start_file_process(file_id, rec["user_id"])
        else:
            with db_lock:
                conn.execute("UPDATE files SET approval_status='rejected', status='Stopped' WHERE id=?", (file_id,))
                conn.commit()
            bot.answer_callback_query(call.id, "❌ Rejected")
            try:
                bot.edit_message_caption(
                    "📥 <b>File REJECTED</b>\n\n"
                    f"📄 File: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
                    f"👤 User ID: <code>{rec['user_id']}</code>\n"
                    f"🔖 File ID: <code>{file_id}</code>\n\n"
                    "❌ Status: Rejected",
                    call.message.chat.id, call.message.message_id
                )
            except Exception:
                pass
            bot.send_message(rec["user_id"], f"❌ Admin rejected your .py file: <b>{html_lib.escape(rec['orig_name'])}</b>")
    except Exception as e:
        logger.error(f"Python approval callback error: {e}")
        bot.answer_callback_query(call.id, "Error processing approval")

# ── User Callbacks ────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: True)
def user_callback_handler(call):
    data, chat_id, user_id = call.data, call.message.chat.id, call.from_user.id
    if user_id != ADMIN_ID:
        cur = conn.cursor(); cur.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            bot.answer_callback_query(call.id, "🚫 You are blocked by Admin.")
            return

    if data == "back_to_files":
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        send_files_list(chat_id, user_id); return

    if data == "back_to_main":
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        bot.send_message(chat_id, "🏠 <b>Main Menu</b>", reply_markup=main_menu_kb())
        return

    try:
        if data.startswith("manage:"):
            show_file_management(chat_id, int(data.split(":")[1]), user_id, call.message.message_id)

        elif data.startswith("start:"):
            bot.answer_callback_query(call.id, "Starting...")
            start_file_process(int(data.split(":")[1]), chat_id, notify=True)
            show_file_management(chat_id, int(data.split(":")[1]), user_id, call.message.message_id)

        elif data.startswith("stop:"):
            bot.answer_callback_query(call.id, "Stopping...")
            stop_file_process(int(data.split(":")[1]))
            bot.send_message(chat_id, "⏹ Process stopped")
            time.sleep(1)
            show_file_management(chat_id, int(data.split(":")[1]), user_id, call.message.message_id)

        elif data.startswith("restart:"):
            bot.answer_callback_query(call.id, "Restarting...")
            fid = int(data.split(":")[1])
            stop_file_process(fid)
            threading.Thread(
                target=start_file_process,
                args=(fid, chat_id),
                kwargs={"notify": True},
                daemon=True
            ).start()
            show_file_management(chat_id, fid, user_id, call.message.message_id)

        elif data.startswith("delete:"):
            bot.answer_callback_query(call.id, "Deleting...")
            fid = int(data.split(":")[1])
            rec = get_file_record(fid)
            if rec:
                stop_file_process(fid)
                try:
                    fp = rec["path"]
                    shutil.rmtree(fp, ignore_errors=True) if os.path.isdir(fp) else os.remove(fp)
                except: pass
                remove_file_record(fid)
            bot.send_message(chat_id, "🗑 File deleted")
            send_files_list(chat_id, user_id)

        elif data.startswith("logs:"):
            bot.answer_callback_query(call.id, "Fetching logs...")
            fid  = int(data.split(":")[1])
            logs = get_file_logs(fid)
            rec  = get_file_record(fid)
            name = rec["orig_name"] if rec else "Unknown"
            if len(logs) > 4000: logs = "... (truncated)\n" + logs[-4000:]
            bot.send_message(chat_id, f"📄 <b>Logs: {html_lib.escape(name)}</b>\n\n<pre>{html_lib.escape(logs)}</pre>")

        elif data.startswith("change_main_file:"):
            fid = int(data.split(":")[1])
            rec = get_file_record(fid)
            if not rec:
                bot.answer_callback_query(call.id, "❌ File not found.")
                return
            if rec["user_id"] != user_id:
                bot.answer_callback_query(call.id, "❌ Access denied.")
                return

            bot.answer_callback_query(call.id, "✏️ Change File Name")
            msg = bot.send_message(
                chat_id,
                "✏️ <b>Change Main File Name</b>\n\n"
                f"📄 Current name: <b>{html_lib.escape(rec['orig_name'] or 'Unnamed')}</b>\n\n"
                "Send the new name you want to show in 📁 My Files.\n"
                "Example: <code>MyBot</code>\n\n"
                "⚠️ This only changes the name shown in the bot; your actual uploaded file remains unchanged.\n"
                "/cancel to abort."
            )
            bot.register_next_step_handler(msg, change_main_file_name_receive, fid)

        elif data.startswith("upload_db:"):
            fid = int(data.split(":")[1])
            rec = get_file_record(fid)
            if not rec:
                bot.answer_callback_query(call.id, "❌ File not found.")
                return
            if rec["user_id"] != user_id:
                bot.answer_callback_query(call.id, "❌ Access denied.")
                return
            bot.answer_callback_query(call.id, "📤 Send your .db file")
            msg = bot.send_message(
                chat_id,
                "🗄️ <b>Upload .db file</b>\n\n"
                f"📁 For: <b>{html_lib.escape(rec['orig_name'])}</b>\n\n"
                "Ab <b>.db</b> file bhejo.\n"
                "Database selected file ke folder me attach ho jayega aur bot usi .db ko use karega."
            )
            bot.register_next_step_handler(msg, upload_db_received, fid)

        elif data.startswith("download_db:"):
            bot.answer_callback_query(call.id, "Preparing .db...")
            fid = int(data.split(":")[1])
            rec = get_file_record(fid)
            if not rec:
                bot.send_message(chat_id, "❌ File not found."); return
            if rec["user_id"] != user_id:
                bot.send_message(chat_id, "❌ Access denied."); return

            # Use the exact attached DB. For older projects, safely recover
            # the DB only when its association is deterministic.
            db_file = _resolve_legacy_db_for_record(rec)
            if db_file:
                _attach_resolved_db(rec, db_file)

            if not db_file:
                bot.send_message(
                    chat_id,
                    "❌ Is project ke saath .db file attach nahi mili.\n\n"
                    "Agar is project ke folder me .db hai, ek baar 🗄️ Upload .db "
                    "se wahi DB re-attach kar do."
                )
                return

            try:
                with open(db_file, "rb") as df:
                    bot.send_document(
                        chat_id, df,
                        caption=f"🗄️ Database: {os.path.basename(db_file)}"
                    )
            except Exception as e:
                logger.error(f"DB download error: {e}")
                bot.send_message(chat_id, f"❌ .db download failed: {html_lib.escape(str(e))}")

        elif data.startswith("download:"):
            bot.answer_callback_query(call.id, "Preparing...")
            fid = int(data.split(":")[1])
            rec = get_file_record(fid)
            if not rec: bot.send_message(chat_id, "❌ File not found."); return
            if user_id not in (rec["user_id"], ADMIN_ID):
                bot.send_message(chat_id, "❌ Access denied."); return
            fp = rec["path"]
            if os.path.isdir(fp):
                zp = os.path.join(TEMP_DIR, f"dl_{fid}_{user_id}.zip")
                shutil.make_archive(zp.replace('.zip',''), 'zip', fp)
                with open(zp,'rb') as f: bot.send_document(chat_id, f)
                os.remove(zp)
            elif os.path.exists(fp):
                with open(fp,'rb') as f: bot.send_document(chat_id, f)
            else:
                bot.send_message(chat_id, "❌ File not found on disk.")

    except Exception as e:
        bot.answer_callback_query(call.id, "Error processing request")
        logger.error(f"Callback error: {e}")

def change_main_file_name_receive(message, file_id):
    """Allow the file owner to change the display name shown in My Files."""
    user_id = message.from_user.id
    rec = get_file_record(file_id)

    if not rec:
        bot.reply_to(message, "❌ File not found.")
        return
    if rec["user_id"] != user_id:
        bot.reply_to(message, "❌ Access denied.")
        return

    name = (message.text or "").strip()
    if name.lower() == "/cancel":
        bot.send_message(message.chat.id, "❌ Name change cancelled.")
        show_file_management(message.chat.id, file_id, user_id)
        return
    if not name:
        msg = bot.send_message(message.chat.id, "❌ Name cannot be empty. Send a new name or /cancel.")
        bot.register_next_step_handler(msg, change_main_file_name_receive, file_id)
        return
    if len(name) > 80:
        msg = bot.send_message(message.chat.id, "❌ Name is too long. Maximum 80 characters. Send again or /cancel.")
        bot.register_next_step_handler(msg, change_main_file_name_receive, file_id)
        return
    if any(ord(c) < 32 for c in name):
        msg = bot.send_message(message.chat.id, "❌ Invalid name. Please use a normal file/project name.")
        bot.register_next_step_handler(msg, change_main_file_name_receive, file_id)
        return

    try:
        with db_lock:
            conn.execute("UPDATE files SET orig_name=? WHERE id=? AND user_id=?", (name, file_id, user_id))
            conn.commit()
        log_activity(user_id, "change_main_file_name", f"file={file_id},name={name}")
        bot.send_message(
            message.chat.id,
            f"✅ <b>Main File Name Changed!</b>\n\n"
            f"📄 New name: <b>{html_lib.escape(name)}</b>\n"
            "This new name will now appear in 📁 My Files."
        )
        show_file_management(message.chat.id, file_id, user_id)
    except Exception as e:
        logger.error(f"Change file name error for file {file_id}: {e}")
        bot.reply_to(message, f"❌ Name change failed: {html_lib.escape(str(e))}")


def send_files_list(chat_id, user_id):
    files = list_user_files(user_id)
    kb = InlineKeyboardMarkup()
    if not files:
        kb.add(InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_main"))
        bot.send_message(chat_id, "📁 <b>Your Files</b>\n\nNo files uploaded yet.", reply_markup=kb)
        return
    for fid, fname, orig, uploaded, ftype, status, pid in files:
        emoji = "🟢" if status == "Running" else "🔴"
        kb.add(InlineKeyboardButton(f"{emoji} {orig} ({ftype})", callback_data=f"manage:{fid}"))
    kb.add(InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_main"))
    bot.send_message(chat_id, "📁 <b>Your Files</b>\n\nClick a file to manage it:", reply_markup=kb)

def show_file_management(chat_id, file_id, user_id, message_id=None):
    rec = get_file_record(file_id)
    if not rec: bot.send_message(chat_id, "❌ File not found"); return
    if rec["user_id"] != user_id: bot.send_message(chat_id, "❌ Access denied"); return
    running = is_file_running(file_id)
    text = f"""
⚙️ <b>File Management</b>

📁 File: {html_lib.escape(rec['orig_name'])}
📊 Type: {rec['file_type']}
📈 Status: {"🟢 Running" if running else "🔴 Stopped"}{"" if not rec['pid'] else chr(10)+"PID: " + str(rec['pid'])}
⏰ Uploaded: {rec['uploaded_at'][:16]}
    """
    _edit_or_send(chat_id, message_id, text, file_actions_kb(file_id, running))

# ── Menu Handlers ─────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "📖 How To Use Bot")
def how_to_use_handler(message):
    link = how_to_use_link()
    kb = InlineKeyboardMarkup()
    if link:
        kb.add(InlineKeyboardButton("📖 How To Use Bot", url=link))
    kb.add(InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_main"))
    bot.send_message(
        message.chat.id,
        "📖 <b>How To Use Bot</b>\n\n"
        "1️⃣ Upload your Python/JS file.\n"
        "2️⃣ Open 📁 My Files.\n"
        "3️⃣ Select your file and use Start, Stop, Restart or Logs.\n"
        "4️⃣ For a detailed guide, tap the button below.",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text == "📢 Updates Channel")
def updates_handler(message):
    bot.send_message(message.chat.id, f"📢 Join our channel: {CHANNEL_URL}")

@bot.message_handler(func=lambda m: m.text == "📞 Contact Owner")
def contact_handler(message):
    bot.send_message(message.chat.id, "📞 Contact: @SHARMAJIIX9")

@bot.message_handler(func=lambda m: m.text == "⚡ Bot Speed")
def speed_handler(message):
    started = time.perf_counter()
    try:
        sent = bot.send_message(message.chat.id, "⚡ <b>Checking original bot speed...</b>")
        elapsed_ms = (time.perf_counter() - started) * 1000
        cpu, mem, cnt = get_system_load()
        bot.edit_message_text(
            "⚡ <b>BOT SPEED</b>\n\n"
            f"🚀 Response: <b>{elapsed_ms:.2f} ms</b>\n"
            "🟢 Status: <b>ONLINE</b>\n"
            "⚙️ System: <b>ORIGINAL</b>\n"
            f"💻 CPU: <b>{cpu:.1f}%</b>\n"
            f"💾 RAM: <b>{mem:.1f}%</b>\n"
            f"🖥️ Processes: <b>{cnt}/{MAX_RUNNING_PROCESSES}</b>",
            chat_id=message.chat.id, message_id=sent.message_id
        )
    except Exception:
        logger.exception("Bot Speed handler error")
        try:
            bot.send_message(message.chat.id, "⚠️ <b>Speed check failed.</b>\n\nPlease try again.")
        except Exception:
            pass

@bot.message_handler(func=lambda m: m.text == "🧩 Feature Center")
def feature_center_handler(message):
    uid=message.from_user.id
    bot.send_message(message.chat.id,user_feature_center_text(uid),reply_markup=user_feature_center_kb(uid))

@bot.message_handler(func=lambda m: m.text == "👤 My Profile")
def my_profile_handler(message):
    uid = message.from_user.id
    cur = conn.cursor()
    row = cur.execute("SELECT username, joined_at, max_files, blocked FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        bot.send_message(message.chat.id, "❌ Profile not found. Please send /start again.")
        return
    total = cur.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (uid,)).fetchone()[0] or 0
    running = cur.execute("SELECT COUNT(*) FROM files WHERE user_id=? AND status='Running'", (uid,)).fetchone()[0] or 0
    limit = row["max_files"] if row["max_files"] is not None else effective_max_files()
    username = html_lib.escape(row["username"] or "Not Set")
    joined = html_lib.escape(str(row["joined_at"] or "Unknown")[:19])
    status = premium_status_text(uid)
    bot.send_message(
        message.chat.id,
        "👤 <b>MY PROFILE</b>\n\n"
        f"🆔 User ID: <code>{uid}</code>\n"
        f"🟢 Username: <b>@{username}</b>\n"
        f"💎 Premium: <b>{html_lib.escape(status)}</b>\n"
        f"📁 Projects: <b>{total}/{limit}</b>\n"
        f"🚀 Running: <b>{running}</b>\n"
        f"📅 Joined: <b>{joined} UTC</b>\n"
        f"🛡 Account: <b>{'Blocked' if row['blocked'] else 'Active'}</b>",
        reply_markup=main_menu_kb()
    )

@bot.message_handler(func=lambda m: m.text == "🧾 My Activity")
def my_activity_handler(message):
    uid = message.from_user.id
    rows = conn.execute(
        "SELECT action, details, created_at FROM activity_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
        (uid,)
    ).fetchall()
    if not rows:
        text = "🧾 <b>MY ACTIVITY</b>\n\nNo recent activity found."
    else:
        lines = ["🧾 <b>MY ACTIVITY</b>", ""]
        for r in rows:
            action = html_lib.escape(str(r["action"] or "Action"))
            details = html_lib.escape(str(r["details"] or ""))
            when = html_lib.escape(str(r["created_at"] or "")[:19])
            lines.append(f"• <b>{action}</b> — {details[:90]}\n  <code>{when} UTC</code>")
        text = "\n".join(lines)
    bot.send_message(message.chat.id, text, reply_markup=main_menu_kb())

@bot.message_handler(func=lambda m: m.text == "📊 Statistics")
def stats_handler(message):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users"); uc = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM files");                fc = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM files WHERE status='Running'"); rc = cur.fetchone()[0] or 0
    cpu, mem, _ = get_system_load()
    bot.send_message(message.chat.id, f"""
📊 <b>Bot Statistics</b>

👥 Total Users: {uc}
📁 Total Files: {fc}
🚀 Running Files: {rc}
⚡ CPU Usage: {cpu:.1f}%
💾 Memory Usage: {mem:.1f}%
    """)

@bot.message_handler(func=lambda m: m.text == "📁 My Files")
def my_files_handler(message):
    send_files_list(message.chat.id, message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "📤 Upload File")
def upload_handler(message):
    prompt = bot.send_message(message.chat.id,
        "📁 <b>New Upload — Project Name</b>\n\n"
        "Give this upload a project name:\n"
        "• It will appear in your control panel\n"
        "• Example: MyBot or NotificationBot\n\n"
        "/cancel to abort."
    )
    bot.register_next_step_handler(prompt, receive_project_name)

def receive_project_name(message):
    """Ask for a project name, then wait for the actual file upload."""
    name = (message.text or "").strip()
    if name == "/cancel":
        bot.send_message(message.chat.id, "❌ Upload cancelled.", reply_markup=main_menu_kb())
        return
    if not name:
        bot.send_message(message.chat.id, "❌ Project name cannot be empty. Please enter a name or /cancel.")
        bot.register_next_step_handler(message, receive_project_name)
        return
    if len(name) > 80:
        bot.send_message(message.chat.id, "❌ Project name is too long (maximum 80 characters). Please try again.")
        bot.register_next_step_handler(message, receive_project_name)
        return
    if any(ord(c) < 32 for c in name):
        bot.send_message(message.chat.id, "❌ Invalid project name. Please enter a normal name or /cancel.")
        bot.register_next_step_handler(message, receive_project_name)
        return

    # Store the custom display name only for the next upload from this user.
    pending_upload_names[message.from_user.id] = name
    prompt = bot.send_message(message.chat.id,
        f"📁 <b>Project: {html_lib.escape(name)}</b>\n\n"
        "Apna Sahi File Upload Karo 👇👇"
        "🐍 <b>.py</b> — Python\n"
            "🟨 <b>.js</b> — JavaScript\n"
            "📦 <b>.zip</b> — Project ZIP\n\n"
    )
    bot.register_next_step_handler(prompt, document_handler)

def upload_db_received(message, file_id):
    """Receive one .db file and attach exactly that database to the selected hosted file."""
    user = message.from_user
    user_id = user.id
    rec = get_file_record(file_id)

    if not rec:
        bot.reply_to(message, "❌ File not found.")
        return
    if rec["user_id"] != user_id:
        bot.reply_to(message, "❌ Access denied.")
        return
    if not message.document or not (message.document.file_name or "").lower().endswith(".db"):
        bot.reply_to(message, "❌ Sirf <b>.db</b> file upload karo.")
        return

    try:
        info = bot.get_file(message.document.file_id)
        data = bot.download_file(info.file_path)

        fp = rec["path"]
        target_dir = fp if os.path.isdir(fp) else os.path.dirname(fp)
        os.makedirs(target_dir, exist_ok=True)

        # IMPORTANT: each hosted project owns only the DB recorded in db_path.
        # Never scan/delete every .db in the user's shared upload directory,
        # because those databases can belong to other projects.
        old_db = rec["db_path"] if "db_path" in rec.keys() else None
        if old_db and os.path.isfile(old_db):
            try:
                os.remove(old_db)
            except OSError:
                pass

        db_name = os.path.basename(message.document.file_name)
        db_path = os.path.join(target_dir, db_name)
        # Avoid overwriting another project's database when both use the same name.
        if os.path.exists(db_path) and os.path.abspath(db_path) != os.path.abspath(old_db or ""):
            stem, ext = os.path.splitext(db_name)
            db_path = os.path.join(target_dir, f"db_{file_id}_{stem}{ext}")
        with open(db_path, "wb") as f:
            f.write(data)

        with db_lock:
            conn.execute("UPDATE files SET db_path=? WHERE id=?", (db_path, file_id))
            conn.commit()

        # Restart in the background so the user gets an immediate response
        # instead of waiting for dependency checks / startup confirmation.
        was_running = is_file_running(file_id)
        if was_running:
            threading.Thread(
                target=_restart_file_after_db_upload,
                args=(file_id, user_id),
                daemon=True
            ).start()
            status_msg = "\n\n🔄 DB attached. Bot restart is happening in background."
        else:
            status_msg = "\n\n▶️ DB attached. Start the bot when ready."

        bot.reply_to(
            message,
            f"✅ <b>.db uploaded successfully!</b>\n\n"
            f"📄 Project: <b>{html_lib.escape(rec['orig_name'])}</b>\n"
            f"🗄️ Database: <b>{html_lib.escape(db_name)}</b>"
            f"{status_msg}"
        )
    except Exception as e:
        logger.error(f"DB upload error for file {file_id}: {e}")
        bot.reply_to(message, f"❌ .db upload failed: {html_lib.escape(str(e))}")


def _restart_file_after_db_upload(file_id, chat_id):
    """Restart a hosted process without blocking the Telegram update handler."""
    try:
        stop_file_process(file_id)
        start_file_process(file_id, chat_id, notify=True)
    except Exception:
        logger.exception("Background DB restart failed for file %s", file_id)


@bot.message_handler(content_types=['photo'])
def premium_payment_photo_handler(message):
    """Receive payment proof and send a review card to Admin."""
    user_id = message.from_user.id
    days = pending_premium_plan.get(user_id)

    if not days:
        bot.reply_to(
            message,
            "ℹ️ First select a Premium plan from 💎 Premium, then send the payment screenshot."
        )
        return

    amount = PREMIUM_PLANS.get(days)
    if amount is None:
        pending_premium_plan.pop(user_id, None)
        bot.reply_to(message, "❌ Invalid Premium plan. Please select the plan again.")
        return

    try:
        screenshot_id = message.photo[-1].file_id
        pid = create_premium_payment(user_id, days, screenshot_id)

        username = message.from_user.username or message.from_user.first_name or str(user_id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"premium_pay_approve:{pid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"premium_pay_reject:{pid}")
        )

        caption = (
            f"💳 <b>NEW PREMIUM PAYMENT</b>\n\n"
            f"🆔 Payment ID: <code>{pid}</code>\n"
            f"👤 User: <b>{html_lib.escape(username)}</b>\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💎 Plan: <b>{days} Days</b>\n"
            f"💰 Amount: <b>₹{amount}</b>\n"
            f"📲 UPI: <code>{html_lib.escape(UPI_ID)}</code>\n\n"
            f"Choose <b>Approve</b> or <b>Reject</b>."
        )

        # Do not clear the user's selected plan until the admin notification
        # has been successfully sent.
        bot.send_photo(
            ADMIN_ID,
            screenshot_id,
            caption=caption,
            reply_markup=kb
        )

        pending_premium_plan.pop(user_id, None)

        bot.reply_to(
            message,
            "📤 <b>Screenshot received!</b>\n\n"
            "⏳ Your payment is pending Admin approval. "
            "Premium will activate after approval."
        )

    except Exception as e:
        logger.exception("Could not process premium payment screenshot")
        bot.reply_to(
            message,
            "❌ Screenshot receive/send failed. Please try sending the screenshot again."
        )


@bot.message_handler(content_types=['document'])
def document_handler(message):
    user    = message.from_user
    user_id = user.id
    if user_id != ADMIN_ID and maintenance_enabled():
        bot.reply_to(message, "🛠️ <b>Maintenance Mode</b>\n\nBot is temporarily under maintenance. Please try again later.")
        return
    if user_id != ADMIN_ID:
        cur = conn.cursor(); cur.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            bot.reply_to(message, "🚫 <b>You are blocked by Admin.</b>")
            return
    user_max = effective_user_max_files(user_id)
    if len(list_user_files(user_id)) >= user_max:
        bot.reply_to(message, f"❌ File limit reached ({user_max}). Delete some to upload new ones.")
        return
    orig_name = message.document.file_name or "unknown"
    file_type = get_file_type(orig_name)

    # IMPORTANT: During a normal project upload, ONLY .py, .js and .zip are
    # accepted. Reject everything else BEFORE saving it or creating a DB
    # record, so a wrong file can never appear in My Files.
    allowed_upload_types = {"python", "javascript", "zip"}
    if file_type not in allowed_upload_types:
        bot.reply_to(
            message,
            "❌ <b>Wrong file type!</b>\n\n"
            "Is upload ke liye sirf ye files allowed hain:\n"
            "🐍 <b>.py</b> — Python\n"
            "🟨 <b>.js</b> — JavaScript\n"
            "📦 <b>.zip</b> — Project ZIP\n\n"
            "⚠️ Ye file <b>save nahi hui</b> aur <b>📁 My Files</b> me nahi dikhegi.\n\n"
            "👉 Ab sahi <b>.py</b>, <b>.js</b> ya <b>.zip</b> file bhejo.\n"
            "❌ <i>/cancel</i> se upload cancel kar sakte ho."
        )
        # Keep the same project-name upload flow alive; do NOT consume the
        # pending project name until a valid file is received.
        bot.register_next_step_handler(message, document_handler)
        return

    try:
        info  = bot.get_file(message.document.file_id)
        data  = bot.download_file(info.file_path)
    except Exception as e:
        bot.reply_to(message, f"❌ Download failed: {e}"); return

    # Use the custom project name in My Files/control panel when supplied.
    project_name = pending_upload_names.pop(user_id, None)
    display_name = project_name or orig_name
    user_dir  = os.path.join(UPLOADS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    safe_name = f"{int(time.time())}_{orig_name}"
    file_path = os.path.join(user_dir, safe_name)
    try:
        with open(file_path, 'wb') as f: f.write(data)
    except Exception as e:
        bot.reply_to(message, f"❌ Save failed: {e}"); return

    final_path, extracted_dir = file_path, None

    if file_type in ["zip", "archive"]:
        bot.reply_to(message, "📦 Extracting archive...")
        extracted_dir = os.path.join(TEMP_DIR, f"ext_{user_id}_{int(time.time())}")
        os.makedirs(extracted_dir, exist_ok=True)
        ok, err = extract_archive(file_path, extracted_dir)
        if not ok:
            bot.reply_to(message, f"❌ Extract failed: {err}")
            try: os.remove(file_path)
            except: pass
            return
        main_file = find_main_file(extracted_dir)
        if not main_file:
            bot.reply_to(message, "❌ No main Python/JS file found in archive.")
            try: shutil.rmtree(extracted_dir, ignore_errors=True); os.remove(file_path)
            except: pass
            return
        final_path = extracted_dir
        file_type  = get_file_type(main_file)
        bot.reply_to(message, f"✅ Found main file: {os.path.basename(main_file)}")

    file_id = add_file_record(user_id, user.username, safe_name, display_name, final_path, file_type)
    log_activity(user_id, "upload", display_name)

    # ALL users require ADMIN approval for every uploaded file.
    # This includes FREE and PREMIUM users.
    premium_record = premium_row(user_id)
    premium_user = bool(premium_record and premium_record["status"] == "active")

    if True:
        with db_lock:
            conn.execute("UPDATE files SET approval_status='pending' WHERE id=?", (file_id,))
            conn.commit()
        try:
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("✅ APPLY", callback_data=f"approve_py:{file_id}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject_py:{file_id}")
            )
            caption = (
                "📥 <b>New File Approval</b>\n\n"
                f"📄 File: <b>{html_lib.escape(orig_name)}</b>\n"
                f"📦 Type: <b>{html_lib.escape(file_type)}</b>\n"
                f"👤 User: <b>{html_lib.escape(user.first_name or 'User')}</b>\n"
                f"🆔 User ID: <code>{user_id}</code>\n"
                f"🔖 File ID: <code>{file_id}</code>\n\n"
                "Choose <b>APPLY</b> to approve/start it or <b>REJECT</b> to deny it."
            )
            # Always send the original uploaded file to Admin. This also works
            # for ZIP/archive uploads whose hosted path is an extracted folder.
            with open(file_path, 'rb') as df:
                bot.send_document(ADMIN_ID, df, caption=caption, reply_markup=kb)
            bot.reply_to(
                message,
                "⏳ <b>Your file has been sent to Admin for approval.</b>\n\n"
                "✅ APPLY = Start\n❌ REJECT = Deny"
            )
        except Exception as e:
            logger.error(f"Admin approval send error: {e}")
            bot.reply_to(message, f"❌ Could not send file to Admin: {html_lib.escape(str(e))}")
    elif file_type in ["python", "javascript"]:
        # Safety fallback: this branch should not be reached because
        # all uploads are sent to Admin for approval above.
        bot.reply_to(
            message,
            "⏳ <b>Your file is waiting for Admin approval.</b>\n\n"
            "You will be notified after it is approved."
        )
    else:
        bot.reply_to(message, "✅ Uploaded! Use 📁 My Files to manage it.")

# ── Process Management ────────────────────────────────────
def _cleanup_stale_statuses():
    """Keep DB status consistent with the real in-memory process state."""
    if not STALE_STATUS_CHECK:
        return
    try:
        rows = conn.execute("SELECT id, status FROM files WHERE status='Running'").fetchall()
        active = set()
        with proc_lock:
            for fid, entry in processes.items():
                try:
                    if entry.get('process') and entry['process'].poll() is None:
                        active.add(fid)
                except Exception:
                    pass
        stale = [row[0] for row in rows if row[0] not in active]
        if stale:
            with db_lock:
                conn.executemany("UPDATE files SET pid=NULL,status='Stopped' WHERE id=?", [(fid,) for fid in stale])
                conn.commit()
    except Exception:
        logger.exception("Stale status cleanup error")

def _stale_status_worker():
    while True:
        try:
            _cleanup_stale_statuses()
        except Exception:
            pass
        time.sleep(30)

def start_file_process(file_id, chat_id, notify=True, _auto_restart=False):
    """Start a hosted file with no artificial startup delay.

    Dependency installation is performed before Popen because the hosted script
    may need those packages. Once Popen succeeds, the process is immediately
    registered as Running; there is no extra sleep/2-second confirmation.
    """
    try:
        rr = get_file_record(file_id)
        if rr:
            log_activity(rr["user_id"], "start", rr["orig_name"])
    except Exception:
        pass

    # A manual start gives the project a fresh recovery budget.
    if not _auto_restart:
        with auto_restart_lock:
            auto_restart_counts.pop(file_id, None)

    # Avoid duplicate starts.
    if is_file_running(file_id):
        if notify:
            bot.send_message(chat_id, "🟢 <b>Bot is already running.</b>")
        return True

    ok, reason = should_stop_due_to_load()
    if ok:
        if notify:
            bot.send_message(chat_id, f"⚠️ Cannot start: {reason}")
        return False

    rec = get_file_record(file_id)
    if not rec:
        if notify:
            bot.send_message(chat_id, "❌ File not found")
        return False

    fp, orig, ftype = rec["path"], rec["orig_name"], rec["file_type"]

    if rec["approval_status"] == "pending":
        if notify:
            bot.send_message(chat_id, "⏳ This .py file is waiting for Admin approval.")
        return False
    if rec["approval_status"] == "rejected":
        if notify:
            bot.send_message(chat_id, "❌ This .py file was rejected by Admin.")
        return False

    if os.path.isdir(fp):
        main_file = find_main_file(fp)
        if not main_file:
            if notify: bot.send_message(chat_id, "❌ No main file found")
            return False
        target, working_dir = main_file, os.path.dirname(main_file)
    else:
        if not os.path.exists(fp):
            if notify: bot.send_message(chat_id, f"❌ File missing: {fp}")
            return False
        target, working_dir = fp, os.path.dirname(fp)

    ext = os.path.splitext(target)[1].lower()
    if ext == ".py":
        req = os.path.join(working_dir, "requirements.txt")
        if os.path.exists(req):
            if notify: bot.send_message(chat_id, "📦 Installing requirements.txt in background...")
            ok2, msg = install_requirements_from_file(req, chat_id, orig)
            if notify: bot.send_message(chat_id, f"{'✅' if ok2 else '⚠️'} {msg}")

        imps = extract_imports(target)
        if imps:
            ok2, msg = install_missing_imports(imps, chat_id, orig)
            if notify and not ok2:
                bot.send_message(chat_id, f"⚠️ Imports: {msg}")

    if ext == ".py":
        cmd = [sys.executable, target]
    elif ext == ".js":
        cmd = ["node", target]
    else:
        if notify: bot.send_message(chat_id, f"❌ Unsupported: {ext}")
        return False

    log_path = os.path.join(LOGS_DIR, f"file_{file_id}_{int(time.time())}.log")
    try:
        proc = None
        last_start_error = None
        for attempt in range(max(1, START_RETRY_COUNT + 1)):
            try:
                with open(log_path, "w" if attempt == 0 else "a") as lf:
                    proc = subprocess.Popen(
                        cmd, stdout=lf, stderr=subprocess.STDOUT,
                        cwd=working_dir, text=True
                    )
                break
            except Exception as start_error:
                last_start_error = start_error
                if attempt < START_RETRY_COUNT:
                    time.sleep(2)
        if proc is None:
            raise RuntimeError(f"Process start failed after retries: {last_start_error}")

        run_id = record_run_start(file_id, proc.pid, log_path)
        update_file_status(file_id, proc.pid, "Running")
        with proc_lock:
            processes[file_id] = {
                "process": proc,
                "run_id": run_id,
                "log_path": log_path,
                "started_at": datetime.utcnow().isoformat()
            }

        # IMPORTANT: no sleep here. The status changes to Running immediately
        # after Popen succeeds. A separate monitor detects an instant crash.
        if notify:
            # Friendly startup message shown immediately before the final
            # "Your Bot Is Live!" notification.
            bot.send_message(
                chat_id,
                f"✨ <b>Great News!</b>\n\n"
                f"🤖 <b>{html_lib.escape(orig)}</b> is getting ready...\n"
                f"⚡ Your bot has started successfully.\n"
                f"🔧 Setting everything up for smooth 24x7 hosting...\n\n"
                f"💚 <i>Almost ready — your live status is coming next!</i>"
            )
            bot.send_message(
                chat_id,
                f"🚀 <b>Your Bot Is Live!</b>\n\n"
                f"📄 File: <b>{html_lib.escape(orig)}</b>\n"
                f"🆔 PID: <code>{proc.pid}</code>\n"
                f"✅ Status: Running 24/7\n\n"
                f"📁 My Files → Logs to see output."
            )

        def monitor():
            try:
                exit_code = proc.wait()
            except Exception:
                exit_code = -1
            finally:
                update_file_status(file_id, None, "Stopped")
                record_run_finish(run_id, exit_code)
                with proc_lock:
                    processes.pop(file_id, None)

                if exit_code not in (0, -15):
                    try:
                        crash_log = ""
                        try:
                            with open(log_path, encoding="utf-8", errors="replace") as lf:
                                crash_log = "".join(lf.readlines()[-20:])[-1000:]
                        except Exception:
                            pass
                        bot.send_message(
                            chat_id,
                            f"⚠️ <b>{html_lib.escape(orig)}</b> crashed!\n"
                            f"🔴 Exit: <code>{exit_code}</code>\n\n"
                            f"<pre>{html_lib.escape(crash_log or 'No log')}</pre>"
                        )
                    except Exception:
                        pass

                    # Automatic crash recovery: retry only a limited number of
                    # times so a permanently broken project cannot create a loop.
                    if AUTO_RESTART_ON_CRASH:
                        with auto_restart_lock:
                            count = auto_restart_counts.get(file_id, 0) + 1
                            auto_restart_counts[file_id] = count
                        if count <= MAX_AUTO_RESTARTS:
                            try:
                                time.sleep(max(1, AUTO_RESTART_DELAY))
                                if not is_file_running(file_id):
                                    start_file_process(file_id, chat_id, notify=False, _auto_restart=True)
                                    bot.send_message(
                                        chat_id,
                                        f"🔄 <b>{html_lib.escape(orig)}</b> auto-restarted. "
                                        f"Recovery attempt {count}/{MAX_AUTO_RESTARTS}."
                                    )
                            except Exception:
                                logger.exception("Auto-restart failed for file %s", file_id)
                        else:
                            try:
                                bot.send_message(
                                    chat_id,
                                    f"🛑 <b>{html_lib.escape(orig)}</b> stopped after "
                                    f"{MAX_AUTO_RESTARTS} automatic recovery attempts. "
                                    f"Please check Logs."
                                )
                            except Exception:
                                pass
                    else:
                        with auto_restart_lock:
                            auto_restart_counts.pop(file_id, None)
                else:
                    with auto_restart_lock:
                        auto_restart_counts.pop(file_id, None)

        threading.Thread(target=monitor, daemon=True).start()
        return True

    except Exception as e:
        logger.exception("Failed to start file %s", file_id)
        if notify:
            bot.send_message(chat_id, f"❌ Failed to start: {html_lib.escape(str(e))}")
        return False

def stop_file_process(file_id):
    with proc_lock:
        if file_id in processes:
            proc = processes[file_id]['process']
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            except Exception as e: logger.error(f"Stop error {file_id}: {e}")
            processes.pop(file_id, None)
    update_file_status(file_id, None, "Stopped")

def get_file_logs(file_id, lines=50):
    try:
        with proc_lock:
            if file_id in processes:
                lp = processes[file_id]['log_path']
                if os.path.exists(lp):
                    with open(lp) as f: c = f.readlines()
                    return ''.join(c[-lines:]) or "No logs yet"
        cur = conn.cursor()
        cur.execute("SELECT log_path FROM runs WHERE file_id=? ORDER BY started_at DESC LIMIT 1", (file_id,))
        row = cur.fetchone()
        if row and row[0] and os.path.exists(row[0]):
            with open(row[0]) as f: c = f.readlines()
            return ''.join(c[-lines:]) or "No logs"
        return "No log file found"
    except Exception as e:
        return f"Log error: {e}"

# ── Start Bot ─────────────────────────────────────────────
def start_bot():
    logger.info(f"Starting bot — Credit: {_WM_CREDIT}")
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=50)
        except Exception as e: logger.error(f"Polling error: {e}"); time.sleep(5)

if __name__ == "__main__":
    logger.info("24x7 Danger Hosting Bot starting...")
    threading.Thread(target=auto_stop_worker, daemon=True, name="auto-stop-worker").start()
    threading.Thread(target=_stale_status_worker, daemon=True, name="stale-status-worker").start()
    start_bot()
