import os, sqlite3
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN=os.getenv("BOT_TOKEN","")
ADMIN_ID=int(os.getenv("ADMIN_ID","0"))
CHANNELS=[("bypassVault","https://t.me/bypassVault"),("primeloote","https://t.me/primeloote"),("sheinstockprime","https://t.me/sheinstockprime")]
IST=timezone(timedelta(hours=5,minutes=30))
RESULT_TIME=datetime(2026,9,12,10,0,tzinfo=IST)
DB="giveaway.db"

def conn():
 c=sqlite3.connect(DB)
 c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,entered INTEGER DEFAULT 0,referred_by INTEGER,referrals INTEGER DEFAULT 0,created_at TEXT)")
 c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)")
 c.commit(); return c

def upsert(u):
 c=conn(); c.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name",(u.id,u.username,u.first_name or "User",0,None,0,datetime.now(IST).isoformat())); c.commit(); c.close()

async def joined(bot,uid):
 for ch,_ in CHANNELS:
  try:
   m=await bot.get_chat_member("@"+ch,uid)
   if m.status in ("left","kicked"): return False
  except Exception: return False
 return True

def joins():
 r=[[InlineKeyboardButton("📢 Join @"+c,url=u)] for c,u in CHANNELS]
 r.append([InlineKeyboardButton("✅ Verify Join",callback_data="verify")])
 return InlineKeyboardMarkup(r)

def menu():
 return InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Enter Giveaway",callback_data="enter")],[InlineKeyboardButton("👥 My Referrals",callback_data="refs"),InlineKeyboardButton("🏆 Leaderboard",callback_data="leader")]])

async def start(update,context):
 u=update.effective_user; upsert(u)
 if context.args:
  try:
   ref=int(context.args[0]); c=conn()
   row=c.execute("SELECT referred_by FROM users WHERE user_id=?",(u.id,)).fetchone()
   if ref!=u.id and row and row[0] is None and c.execute("SELECT 1 FROM users WHERE user_id=?",(ref,)).fetchone():
    c.execute("UPDATE users SET referred_by=? WHERE user_id=?",(ref,u.id)); c.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=?",(ref,))
   c.commit(); c.close()
  except: pass
 await update.message.reply_text("🎉 *₹150 GIVEAWAY* 🎉\n\n🥇 1st Prize — ₹100\n🥈 2nd Prize — ₹50\n\nPehle teeno channels join karke Verify Join karein.",parse_mode="Markdown",reply_markup=joins())

async def verify(update,context):
 q=update.callback_query; await q.answer()
 if await joined(context.bot,q.from_user.id):
  await q.edit_message_text("✅ *Join Verified!*\n\nAb Giveaway me entry karein 👇",parse_mode="Markdown",reply_markup=menu())
 else: await q.answer("❌ Pehle teeno channels join karein.",show_alert=True)

async def enter(update,context):
 q=update.callback_query; await q.answer()
 if datetime.now(IST)>=RESULT_TIME:
  await q.edit_message_text("⛔ Giveaway khatam ho chuka hai."); return
 if not await joined(context.bot,q.from_user.id):
  await q.edit_message_text("❌ Pehle teeno channels join karein.",reply_markup=joins()); return
 c=conn(); c.execute("UPDATE users SET entered=1 WHERE user_id=?",(q.from_user.id,)); c.commit(); c.close()
 me=await context.bot.get_me(); link=f"https://t.me/{me.username}?start={q.from_user.id}"
 await q.edit_message_text(f"🎉 *Entry Successful!*\n\n🔗 Referral Link:\n`{link}`\n\n🏆 Result: 12 September, 10:00 AM. Top 2 valid referral winners honge.",parse_mode="Markdown",reply_markup=menu())

async def refs(update,context):
 q=update.callback_query; await q.answer(); c=conn(); r=c.execute("SELECT referrals FROM users WHERE user_id=?",(q.from_user.id,)).fetchone(); c.close()
 await q.edit_message_text(f"👥 *Your Referrals:* {r[0] if r else 0}",parse_mode="Markdown",reply_markup=menu())

async def leader(update,context):
 q=update.callback_query; await q.answer(); c=conn(); rows=c.execute("SELECT first_name,username,referrals FROM users WHERE entered=1 ORDER BY referrals DESC,created_at ASC LIMIT 10").fetchall(); c.close()
 text="🏆 *Leaderboard*\n\n"+("\n".join(f"{i}. @{x[1] or x[0]} — {x[2]} referrals" for i,x in enumerate(rows,1)) if rows else "Abhi koi participant nahi hai.")
 await q.edit_message_text(text,parse_mode="Markdown",reply_markup=menu())

async def result_job(context):
 if datetime.now(IST)<RESULT_TIME: return
 c=conn()
 if c.execute("SELECT 1 FROM settings WHERE key='results_sent'").fetchone(): c.close(); return
 rows=c.execute("SELECT user_id,first_name,username,referrals FROM users WHERE entered=1 ORDER BY referrals DESC,created_at ASC").fetchall()
 winners=[]
 for x in rows:
  if await joined(context.bot,x[0]):
   winners.append(x)
   if len(winners)==2: break
 c.execute("INSERT OR REPLACE INTO settings VALUES('results_sent','1')"); c.commit(); c.close()
 if len(winners)<2:
  if ADMIN_ID: await context.bot.send_message(ADMIN_ID,"⚠️ 2 eligible winners nahi mile.")
  return
 a,b=winners
 msg=f"🎉 *GIVEAWAY RESULT DECLARED* 🎉\n\n🥇 *1st Winner — ₹100*\n{a[1]} — {a[3]} valid referrals\n\n🥈 *2nd Winner — ₹50*\n{b[1]} — {b[3]} valid referrals\n\nCongratulations! 🎊"
 if ADMIN_ID: await context.bot.send_message(ADMIN_ID,msg,parse_mode="Markdown")
 for x in winners:
  try: await context.bot.send_message(x[0],"🎉 Congratulations!\n\n"+msg,parse_mode="Markdown")
  except: pass

def main():
 if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN missing")
 app=Application.builder().token(BOT_TOKEN).build()
 app.add_handler(CommandHandler("start",start))
 app.add_handler(CallbackQueryHandler(verify,pattern="^verify$"))
 app.add_handler(CallbackQueryHandler(enter,pattern="^enter$"))
 app.add_handler(CallbackQueryHandler(refs,pattern="^refs$"))
 app.add_handler(CallbackQueryHandler(leader,pattern="^leader$"))
 app.job_queue.run_repeating(result_job,interval=60,first=5)
 print("Bot running...")
 app.run_polling()
if __name__=="__main__": main()
