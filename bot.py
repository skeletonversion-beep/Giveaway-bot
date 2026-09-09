import os
import sqlite3
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNELS = [
    ("bypassVault", "https://t.me/bypassVault"),
    ("primeloote", "https://t.me/primeloote"),
    ("sheinstockprime", "https://t.me/sheinstockprime"),
]

RESULT_TIME = datetime(2026, 9, 12, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
DB = "giveaway.db"

def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        entered INTEGER DEFAULT 0, referred_by INTEGER, referrals INTEGER DEFAULT 0,
        created_at TEXT)""")
    c.commit()
    return c

def upsert_user(u):
    c=db()
    c.execute("""INSERT INTO users(user_id,username,first_name,created_at)
                 VALUES(?,?,?,?)
                 ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
                 first_name=excluded.first_name""",
              (u.id,u.username,u.first_name,datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()

def set_referrer(uid, ref):
    if not ref or uid == ref: return
    c=db()
    row=c.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,)).fetchone()
    if row and row[0] is None:
        exists=c.execute("SELECT user_id FROM users WHERE user_id=?", (ref,)).fetchone()
        if exists:
            c.execute("UPDATE users SET referred_by=? WHERE user_id=?", (ref,uid))
            c.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=?", (ref,))
            c.commit()
    c.close()

async def joined_all(bot, user_id):
    for channel, _ in CHANNELS:
        try:
            m = await bot.get_chat_member("@" + channel, user_id)
            if m.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True

def join_keyboard():
    rows=[[InlineKeyboardButton(f"📢 Join @{ch}", url=url)] for ch,url in CHANNELS]
    rows.append([InlineKeyboardButton("✅ Verify Join", callback_data="verify")])
    return InlineKeyboardMarkup(rows)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Enter Giveaway", callback_data="enter")],
        [InlineKeyboardButton("👥 My Referrals", callback_data="refs"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="leader")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; upsert_user(u)
    ref=None
    if context.args:
        try: ref=int(context.args[0])
        except: pass
    set_referrer(u.id, ref)
    await update.message.reply_text(
        "🎉 *₹150 GIVEAWAY* 🎉\n\n"
        "🥇 1st Prize — ₹100\n🥈 2nd Prize — ₹50\n\n"
        "📢 Pehle teeno channels join karein aur Verify Join dabayein.",
        parse_mode="Markdown", reply_markup=join_keyboard())

async def verify(update, context):
    q=update.callback_query; await q.answer()
    if await joined_all(context.bot, q.from_user.id):
        await q.edit_message_text("✅ *Join verified!*\n\nAb Giveaway me entry karein 👇",
                                  parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await q.answer("❌ Aapne abhi teeno channels join nahi kiye.", show_alert=True)

async def enter(update, context):
    q=update.callback_query; await q.answer()
    if not await joined_all(context.bot,q.from_user.id):
        await q.edit_message_text("❌ Pehle teeno compulsory channels join karein.",
                                  reply_markup=join_keyboard()); return
    c=db()
    c.execute("UPDATE users SET entered=1 WHERE user_id=?", (q.from_user.id,))
    c.commit(); c.close()
    await q.edit_message_text(
        "🎉 *Entry Successful!*\n\n"
        "Ab apna referral link share karke valid referrals badhayein:\n"
        f"`https://t.me/{(await context.bot.get_me()).username}?start={q.from_user.id}`\n\n"
        "🏆 Sabse zyada valid referrals wale 2 members winners honge.",
        parse_mode="Markdown", reply_markup=main_keyboard())

async def refs(update, context):
    q=update.callback_query; await q.answer()
    c=db(); r=c.execute("SELECT referrals,entered FROM users WHERE user_id=?", (q.from_user.id,)).fetchone(); c.close()
    count=r[0] if r else 0
    await q.edit_message_text(f"👥 *Your valid referrals:* {count}\n\nKeep sharing your referral link!",
                              parse_mode="Markdown", reply_markup=main_keyboard())

async def leader(update, context):
    q=update.callback_query; await q.answer()
    c=db(); rows=c.execute("""SELECT first_name,username,referrals FROM users
                              WHERE entered=1 ORDER BY referrals DESC LIMIT 10""").fetchall(); c.close()
    if not rows: text="🏆 Leaderboard abhi empty hai."
    else:
        text="🏆 *Top Giveaway Members*\n\n"
        for i,(name,username,r) in enumerate(rows,1):
            display=("@" + username) if username else name
            text += f"{i}. {display} — {r} referrals\n"
    await q.edit_message_text(text,parse_mode="Markdown",reply_markup=main_keyboard())

async def admin(update, context):
    if update.effective_user.id != ADMIN_ID: return
    c=db()
    rows=c.execute("""SELECT user_id,first_name,username,referrals FROM users
                      WHERE entered=1 ORDER BY referrals DESC""").fetchall()
    c.close()
    text="🏆 *Final Ranking*\n\n"
    for i,(uid,name,username,r) in enumerate(rows[:20],1):
        text += f"{i}. {name} (@{username or '-'}) — {r}\n"
    await update.message.reply_text(text,parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin))
    app.add_handler(CallbackQueryHandler(verify,pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(enter,pattern="^enter$"))
    app.add_handler(CallbackQueryHandler(refs,pattern="^refs$"))
    app.add_handler(CallbackQueryHandler(leader,pattern="^leader$"))
    print("Giveaway bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
