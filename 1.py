import os
import sys
import subprocess
import asyncio
import logging
import time
import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from deep_translator import GoogleTranslator

# ========== PENGECEKAN DEPENDENSI ==========
def check_dependencies():
    missing = []
    try:
        import telegram
        import requests
        import aiohttp
        from deep_translator import GoogleTranslator
    except ImportError:
        missing.append("python-telegram-bot requests aiohttp deep-translator")
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except:
        missing.append("yt-dlp")
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except:
        missing.append("ffmpeg")
    if missing:
        print("\n❌ DEPENDENSI BELUM TERINSTAL!")
        print("Silakan jalankan perintah berikut:\n")
        print("pip install python-telegram-bot requests aiohttp deep-translator yt-dlp")
        if "ffmpeg" in missing:
            print("sudo apt install ffmpeg -y")
        print("\nSetelah itu, jalankan ulang bot.\n")
        sys.exit(1)

check_dependencies()

# ========== IMPOR ==========
import requests
import time
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from deep_translator import GoogleTranslator

# === CONFIG ===
TOKEN = "8328979483:AAGVICrdqOy-vf_az7zg3tZRPBwHcCwfwTw"
OPENROUTER_API_KEY = "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"
WORK_DIR = os.path.join(os.getcwd(), "oxyx_engine")
if not os.path.exists(WORK_DIR):
    os.makedirs(WORK_DIR)

ADMIN_USERNAME = "Fivipi"

logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

USER_STATES = {}
ACTIVE_PROCESS = {}

# ================= TERMINAL PROGRESS BAR =================
class ProgressBar:
    def __init__(self, total_steps=100):
        self.total = total_steps
        self.current = 0
        self._stop = False
        self._task = None
        self._lock = asyncio.Lock()
        self._message = ""
        self._spinner = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        self._spinner_idx = 0

    async def start(self, message="Processing..."):
        async with self._lock:
            self._stop = False
            self.current = 0
            self._message = message
            self._task = asyncio.create_task(self._animate())

    async def update(self, percent, message=None):
        async with self._lock:
            self.current = percent
            if message:
                self._message = message

    async def _animate(self):
        while not self._stop:
            filled = int(self.current / 100 * 10)
            bar = "▓" * filled + "░" * (10 - filled)
            spinner = self._spinner[self._spinner_idx % len(self._spinner)]
            sys.stdout.write(f"\r{spinner} {self._message} [{bar}] {self.current}%")
            sys.stdout.flush()
            self._spinner_idx += 1
            await asyncio.sleep(0.1)
        sys.stdout.write("\r" + " " * 50 + "\r")
        sys.stdout.flush()

    async def stop(self):
        async with self._lock:
            self._stop = True
            if self._task:
                await self._task
                self._task = None

progress = ProgressBar()

# ================= FUNGSI TERJEMAHAN =================
async def translate_to_english(text: str) -> str:
    try:
        translator = GoogleTranslator(source='id', target='en')
        translated = translator.translate(text)
        if translated:
            return translated
        return text
    except Exception as e:
        logging.error(f"Gagal terjemah: {e}")
        return text

# ================= DOWNLOADER =================
def run_safe_download(url, output_path):
    cmd_hq = [
        "yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best",
        url, "-o", output_path, "--no-playlist", "--max-filesize", "50M",
        "--merge-output-format", "mp4", "--no-check-certificate"
    ]
    cmd_fallback = ["yt-dlp", "-f", "best", url, "-o", output_path, "--no-playlist", "--max-filesize", "50M"]

    try:
        subprocess.run(cmd_hq, capture_output=True, text=True, timeout=120)
        if os.path.exists(output_path):
            return True, "HQ Success"
        subprocess.run(cmd_fallback, capture_output=True, timeout=120)
        if os.path.exists(output_path):
            return True, "Fallback Success"
        return False, "File tidak ditemukan"
    except subprocess.TimeoutExpired:
        return False, "Waktu download habis"
    except Exception as e:
        return False, str(e)

async def run_safe_download_async(url, output_path, progress_bar):
    async def update_progress():
        for p in range(0, 101, 10):
            await progress_bar.update(p, f"Mengunduh {p}%...")
            await asyncio.sleep(0.5)

    loop = asyncio.get_running_loop()
    download_future = loop.run_in_executor(None, run_safe_download, url, output_path)
    progress_task = asyncio.create_task(update_progress())
    try:
        result = await download_future
        progress_task.cancel()
        return result
    except Exception as e:
        progress_task.cancel()
        return False, str(e)

# ================= AI GAMBAR =================
async def generate_image(chat_id, prompt):
    img_path = os.path.join(WORK_DIR, f"ai_{chat_id}.jpg")
    encoded_prompt = prompt.replace(' ', '%20')
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true&width=1024&height=1024"

    await progress.update(10, "Mengirim permintaan...")
    await asyncio.sleep(0.5)
    await progress.update(30, "Menunggu respon server...")

    for attempt in range(3):
        try:
            response = requests.get(url, timeout=90)
            if response.status_code == 200 and 'image' in response.headers.get('content-type', ''):
                if len(response.content) > 1000:
                    await progress.update(70, "Menyimpan gambar...")
                    with open(img_path, "wb") as f:
                        f.write(response.content)
                    await progress.update(100, "Selesai!")
                    return img_path
        except requests.exceptions.Timeout:
            logging.warning(f"Image attempt {attempt+1} timeout")
        except Exception as e:
            logging.error(f"Image attempt {attempt+1} error: {e}")
        if attempt == 0:
            await progress.update(50, "Coba ulang...")
        elif attempt == 1:
            await progress.update(70, "Percobaan terakhir...")
        await asyncio.sleep(2)
    return None

# ================= BYPASS LINK =================
def bypass_link(url: str, timeout=15) -> str:
    try:
        response = requests.get(url, allow_redirects=True, timeout=timeout)
        return response.url
    except requests.exceptions.Timeout:
        return "Error: Waktu habis, link tidak bisa diakses"
    except requests.exceptions.ConnectionError:
        return "Error: Gagal terhubung ke server"
    except Exception as e:
        logging.error(f"Bypass error: {e}")
        return f"Error: {str(e)}"

# ================= AI CHAT (OPENROUTER - 50+ MODEL) =================
async def chat_ai(message: str, model: str = "anthropic/claude-3.5-sonnet") -> str:
    """Menggunakan OpenRouter API untuk mengakses berbagai model AI."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": message}],
                "max_tokens": 1000
            }
            
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    error_text = await response.text()
                    logging.error(f"OpenRouter error: {response.status} - {error_text}")
                    return f"Maaf, terjadi kesalahan. Status: {response.status}"
    except asyncio.TimeoutError:
        return "Waktu habis. AI terlalu lama merespons. Coba lagi."
    except Exception as e:
        logging.error(f"Chat AI error: {e}")
        return "Terjadi kesalahan saat menghubungi AI. Coba beberapa saat lagi."

# ================= MENU UTAMA =================
async def ls_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    chat_id = update.effective_chat.id
    USER_STATES[chat_id] = None
    keyboard = [
        [InlineKeyboardButton("🎬 Video AI", callback_data='m_video'), InlineKeyboardButton("🎨 Gambar AI", callback_data='m_image')],
        [InlineKeyboardButton("📥 Video Downloader", callback_data='m_dl')],
        [InlineKeyboardButton("💬 AI Chat", callback_data='m_chat'), InlineKeyboardButton("🔗 Bypass Link", callback_data='m_bypass')],
        [InlineKeyboardButton("📊 Info & Penawaran", callback_data='m_info')],
        [InlineKeyboardButton("🛰️ Status", callback_data='m_check'), InlineKeyboardButton("👨‍💻 Admin", callback_data='m_admin')]
    ]
    text = "🚀 **OXYX V109.1 - CLEAN CONSOLE**\nSistem berjalan dalam mode senyap, Tuan."

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    elapsed = time.time() - start_time
    logging.info(f"ls_menu finished in {elapsed:.2f}s")

# ================= PILIHAN GAYA GAMBAR =================
STYLES_IMAGE = {
    "realistis": "realistic, photorealistic, high detail",
    "kartun": "cartoon style, animated, colorful",
    "anime": "anime style, manga art, vibrant",
    "fantasi": "fantasy art, magical, ethereal",
    "hd": "ultra HD, 8k, high resolution, sharp focus",
    "minimalis": "minimalist style, simple, clean lines"
}

STYLES_VIDEO = {
    "realistis": "realistic, high quality video",
    "kartun": "cartoon animation, 3d style",
    "anime": "anime style, japanese animation",
    "fantasi": "fantasy world, magical scene"
}

def apply_style(prompt: str, style_key: str, is_image=True) -> str:
    if is_image:
        style_desc = STYLES_IMAGE.get(style_key, "")
    else:
        style_desc = STYLES_VIDEO.get(style_key, "")
    if style_desc:
        return f"{style_desc}, {prompt}"
    return prompt

# ================= HANDLER TOMBOL =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user = update.effective_user
    await query.answer()

    if query.data == 'm_back':
        await ls_menu(update, context)
        return

    if query.data.startswith("style_img_"):
        style = query.data.split("_")[2]
        USER_STATES[chat_id] = {"mode": "image_style", "style": style}
        await query.edit_message_text(
            f"🎨 **Gaya dipilih:** `{style.upper()}`\nSekarang kirimkan deskripsi gambar Tuan!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Batal", callback_data='m_back')]])
        )
        return

    if query.data.startswith("style_vid_"):
        style = query.data.split("_")[2]
        USER_STATES[chat_id] = {"mode": "video_style", "style": style}
        await query.edit_message_text(
            f"🎬 **Gaya dipilih:** `{style.upper()}`\nSekarang kirimkan topik video Tuan!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Batal", callback_data='m_back')]])
        )
        return

    if query.data == 'm_image':
        keyboard = []
        for style in STYLES_IMAGE.keys():
            keyboard.append([InlineKeyboardButton(f"🎨 {style.capitalize()}", callback_data=f"style_img_{style}")])
        keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')])
        await query.edit_message_text(
            "🎨 **Pilih gaya gambar yang diinginkan:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if query.data == 'm_video':
        keyboard = []
        for style in STYLES_VIDEO.keys():
            keyboard.append([InlineKeyboardButton(f"🎬 {style.capitalize()}", callback_data=f"style_vid_{style}")])
        keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')])
        await query.edit_message_text(
            "🎬 **Pilih gaya video yang diinginkan:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if query.data == 'm_dl':
        USER_STATES[chat_id] = {"mode": "dl"}
        await query.edit_message_text(
            "📥 **MODE DOWNLOADER**\nKirim link video!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')]])
        )
        return

    if query.data == 'm_chat':
        USER_STATES[chat_id] = {"mode": "chat"}
        await query.edit_message_text(
            "💬 **MODE AI CHAT (OpenRouter - 50+ Model)**\nKirim pesan apa saja, AI akan menjawab.\n\nKetik /start untuk keluar.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')]])
        )
        return

    if query.data == 'm_bypass':
        USER_STATES[chat_id] = {"mode": "bypass"}
        await query.edit_message_text(
            "🔗 **MODE BYPASS LINK**\nKirim sebuah link, saya akan mengikuti redirect hingga mendapatkan URL akhir.\n\nKetik /start untuk keluar.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')]])
        )
        return

    if query.data == 'm_info':
        info_text = (
            "📄 *INFO BOT & PENAWARAN*\n\n"
            "🤖 *OXYX V109.1* adalah bot multi-fungsi dengan fitur:\n"
            "• 🎨 *Gambar AI* – buat gambar dengan pilihan gaya\n"
            "• 📥 *Downloader* – unduh video dari berbagai platform\n"
            "• 💬 *AI Chat* – ngobrol dengan 50+ model AI (OpenRouter)\n"
            "• 🔗 *Bypass Link* – dapatkan URL akhir dari link redirect\n"
            "• 🎬 *Video AI* – (dalam pengembangan)\n\n"
            "✨ *Paket Member VIP*\n"
            "💎 *Rp60.000 / bulan*\n"
            "Fitur eksklusif untuk member:\n"
            "• Prioritas pemrosesan\n"
            "• Download video tanpa batas ukuran\n\n"
            "📲 *Hubungi admin:* @Fivipi"
        )
        await query.edit_message_text(info_text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')]]))
        return

    if query.data == 'm_check':
        status_text = (
            "🛰️ *STATUS BOT*\n\n"
            f"• *User:* @{user.username if user.username else 'Tidak ada username'}\n"
            f"• *Status:* {ACTIVE_PROCESS.get(chat_id, 'Idle')}\n"
            f"• *Admin:* @{ADMIN_USERNAME}\n"
            "• *Fitur aktif:*\n"
            "  ✅ Gambar AI\n"
            "  ✅ Downloader\n"
            "  ✅ AI Chat (OpenRouter - 50+ model)\n"
            "  ✅ Bypass Link\n"
            "  ❌ Video AI (nonaktif)\n\n"
            "• *Bot berjalan sejak:* " + time.strftime("%d %b %Y %H:%M:%S")
        )
        await query.edit_message_text(status_text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')]]))
        return

    if query.data == 'm_admin':
        admin_text = (
            "👨‍💻 *ADMIN BOT*\n\n"
            f"• *Username:* @{ADMIN_USERNAME}\n"
            "• *Credit:* @Fivipi\n\n"
            "🔒 *Akses penuh*: Admin dapat menggunakan semua fitur.\n"
            "📢 Untuk laporan bug atau menjadi member VIP, hubungi langsung."
        )
        await query.edit_message_text(admin_text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='m_back')]]))
        return

# ================= HANDLE TEXT =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    chat_id = update.effective_chat.id
    state = USER_STATES.get(chat_id)

    # Mode gambar dengan gaya
    if isinstance(state, dict) and state.get("mode") == "image_style":
        style = state.get("style")
        if not style:
            await update.message.reply_text("❌ Terjadi kesalahan. Silakan pilih gaya lagi.")
            USER_STATES[chat_id] = None
            return

        ACTIVE_PROCESS[chat_id] = "Generating Image..."
        status_msg = await update.message.reply_text("🎨 **Sedang melukis...**")
        await progress.start("Mempersiapkan...")

        english_prompt = await translate_to_english(user_input)
        final_prompt = apply_style(english_prompt, style, is_image=True)

        try:
            img_path = await generate_image(chat_id, final_prompt)
            await progress.stop()
            if img_path:
                await update.message.reply_photo(
                    photo=open(img_path, 'rb'),
                    caption=f"✅ **Gambar berhasil!**\n🎨 Gaya: {style.capitalize()}\n📝 Prompt: `{user_input}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                os.remove(img_path)
            else:
                await update.message.reply_text("❌ Gagal membuat gambar.")
        except Exception as e:
            logging.error(f"Image error: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan.")
        finally:
            await progress.stop()
            await status_msg.delete()
            ACTIVE_PROCESS[chat_id] = "Idle"
            USER_STATES[chat_id] = None
        return

    # Mode video (nonaktif)
    if isinstance(state, dict) and state.get("mode") == "video_style":
        await update.message.reply_text("❌ Fitur Video AI sedang dalam pengembangan.")
        USER_STATES[chat_id] = None
        return

    # Mode downloader
    if isinstance(state, dict) and state.get("mode") == "dl":
        ACTIVE_PROCESS[chat_id] = "Downloading..."
        status_msg = await update.message.reply_text("📥 **Mengunduh...**")
        await progress.start("Memulai download...")
        video_file = os.path.join(WORK_DIR, f"out_{chat_id}.mp4")
        success, info = await run_safe_download_async(user_input, video_file, progress)
        await progress.stop()
        if success:
            try:
                size = os.path.getsize(video_file) / (1024 * 1024)
                if size > 50:
                    await update.message.reply_text(f"⚠️ Video terlalu besar ({size:.1f} MB)")
                else:
                    await update.message.reply_video(video=open(video_file, 'rb'), caption="✅ Berhasil diunduh!")
            except Exception as e:
                await update.message.reply_text(f"❌ Gagal mengirim: {e}")
            finally:
                if os.path.exists(video_file):
                    os.remove(video_file)
        else:
            await update.message.reply_text(f"❌ Gagal download: {info}")
        await status_msg.delete()
        ACTIVE_PROCESS[chat_id] = "Idle"
        USER_STATES[chat_id] = None
        return

    # Mode AI Chat (OpenRouter)
    if isinstance(state, dict) and state.get("mode") == "chat":
        ACTIVE_PROCESS[chat_id] = "Chatting..."
        status_msg = await update.message.reply_text("💬 **AI sedang berpikir...**")
        await progress.start("Menghubungi OpenRouter AI...")
        try:
            reply = await chat_ai(user_input)
            await progress.stop()
            await status_msg.delete()
            if len(reply) > 4096:
                reply = reply[:4093] + "..."
            await update.message.reply_text(f"🤖 *AI:* {reply}", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await progress.stop()
            await status_msg.delete()
            await update.message.reply_text("❌ Gagal mendapatkan respons AI.")
            logging.error(f"Chat error: {e}")
        finally:
            ACTIVE_PROCESS[chat_id] = "Idle"
        return

    # Mode Bypass Link
    if isinstance(state, dict) and state.get("mode") == "bypass":
        if not user_input.startswith(("http://", "https://")):
            await update.message.reply_text("❌ Kirim link yang valid (http:// atau https://).")
            return
        ACTIVE_PROCESS[chat_id] = "Bypassing..."
        status_msg = await update.message.reply_text("🔗 **Memproses link...**")
        await progress.start("Mengikuti redirect...")
        try:
            final_url = bypass_link(user_input)
            await progress.stop()
            await status_msg.delete()
            await update.message.reply_text(f"🔗 *Hasil Bypass:*\n`{final_url}`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await progress.stop()
            await status_msg.delete()
            await update.message.reply_text(f"❌ Gagal: {e}")
        finally:
            ACTIVE_PROCESS[chat_id] = "Idle"
        return

    # Jika tidak dalam mode, arahkan ke menu
    await ls_menu(update, context)

# ================= MAIN =================
def main():
    request = HTTPXRequest(read_timeout=30, write_timeout=30, connect_timeout=30)
    app = Application.builder().token(TOKEN).request(request).build()
    app.add_handler(CommandHandler(["start", "ls"], ls_menu))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    os.system('clear')
    print("=" * 50)
    print("OXYX V109.1 ONLINE - CLEAN CONSOLE ACTIVE")
    print("=" * 50)
    print("✅ Gambar AI (dengan gaya)")
    print("✅ Downloader Video")
    print("✅ AI Chat (OpenRouter - 50+ Model)")
    print("✅ Bypass Link")
    print("❌ Video AI (nonaktif)")
    print(f"🔧 Admin: @{ADMIN_USERNAME}")
    print("=" * 50)
    print("🔄 Terminal progress bar akan muncul saat proses berjalan.\n")
    app.run_polling()

if __name__ == "__main__":
    main()
