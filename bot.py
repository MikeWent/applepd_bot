#!/usr/bin/env python3

# https://github.com/MikeWent/applepd_bot
# https://t.me/applepd_bot

import os
import random
import re
import string
import threading
import time

import requests
import telebot
import mutagen

from hurry.filesize import alternative, size

from playlist_parser import get_urls_from_playlist

# SETTINGS
TEMP_FOLDER = "/tmp/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36",
    "Accept-Encoding": "identity"
}
MAXIMUM_FILESIZE_ALLOWED = 50*1024*1024 # ~50 MB

# MESSAGES
error_wrong_code = "❗️ Resource returned HTTP {} code. Maybe link in the playlist is broken or outdated?"
error_downloading = "⚠️ Unable to download this file"
error_parsing = "⚠️ Sorry, I am unable to parse this file correctly. If you sure that I should, then contact @Mike_Went"
error_huge_file = "🍉 File is bigger than 50 MB. Telegram <b>does not<b> allow me to upload huge files, sorry."
error_no_length = "⚠️ Server didn't send the Content-Length header, so I can't determine the filesize and download this file"
message_start = """Hello! I am Apple Playlist Decoder bot (not affiliated with Apple in any way)

📁 Send a <b>playlist file</b> to me and I will send you a list of links preserved in the file.

🌐 You can even send me a <b>link to MP3</b> and I will upload it to you via Telegram!"""
message_downloading = "⬇️ Downloading… {}"
message_uploading = "☁️ Uploading to Telegram…"

def update_status_message(message, text):
    try:
        bot.edit_message_text(chat_id=message.chat.id,
                              message_id=message.message_id,
                              text=text, parse_mode="HTML")
    except:
        pass


def rm(filename):
    """Delete file (like 'rm' command)"""
    try:
        os.remove(filename)
    except:
        pass


def random_string(length=12):
    """Random string of uppercase ASCII and digits"""
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))


def download_file(request, destination):
    """Pass remote file to the local pipe"""
    with open(destination, "wb") as f:
        for chunk in request:
            f.write(chunk)


def worker(message, url):
    """Generic process spawned every time user sends a link"""
    # Try to download URL
    try:
        r = requests.get(url, stream=True, headers=HEADERS)
    except:
        bot.send_message(message.chat.id, error_downloading, parse_mode="HTML")
        return

    # Something went wrong on the server side
    if r.status_code != 200:
        bot.send_message(message.chat.id, error_wrong_code.format(r.status_code), parse_mode="HTML")
        return
    
    # Check file size
    if not r.headers.get("Content-Length"):
        bot.send_message(message.chat.id, error_no_length, parse_mode="HTML")
        return

    if int(r.headers["Content-Length"]) >= MAXIMUM_FILESIZE_ALLOWED:
        bot.send_message(message.chat.id, error_huge_file, parse_mode="HTML")
        return

    # Tell user that we are working
    status_message = bot.reply_to(message, message_downloading.format(""), parse_mode="HTML")

    # Download file
    filename = TEMP_FOLDER + "track-" + random_string()
    try:
        downloading_thread = threading.Thread(
            target=download_file,
            kwargs={
                "request": r,
                "destination": filename
            }
        )
        downloading_thread.start()
    except:
        update_status_message(status_message, error_downloading)
        return
    time.sleep(1)

    old_progress = ""
    while downloading_thread.is_alive():
        try:
            output_file_size = os.stat(filename).st_size
        except FileNotFoundError:
            output_file_size = 0
        local_size = size(output_file_size, system=alternative)
        remote_size = size(int(r.headers["Content-Length"]), system=alternative)
        human_readable_progress = " ".join([local_size, "/", remote_size])
        if human_readable_progress != old_progress:
            update_status_message(status_message, message_downloading.format(human_readable_progress))
            old_prpgress = human_readable_progress
        time.sleep(3)

    # Extract metadata
    audiofile = mutagen.File(filename)
    title = audiofile.tags.get("TIT2", None)
    performer = audiofile.tags.get("TPE1", None)
    duration = int(audiofile.info.length)
    # Upload
    update_status_message(status_message, message_uploading)
    bot.send_audio(message.chat.id, open(filename, "rb"), title=title, performer=performer, duration=duration)

    bot.delete_message(message.chat.id, status_message.message_id)
    rm(filename)

### Telegram interaction below ###
try:
    with open("token.txt", "r") as f:
        telegram_token = f.read().strip()
except FileNotFoundError:
    print("Put your Telegram bot token to 'token.txt' file")
    exit(1)
bot = telebot.TeleBot(telegram_token)

@bot.message_handler(commands=["start", "help"])
def start_help(message):
    bot.send_message(message.chat.id, message_start, parse_mode="HTML")

# Handle URLs
URL_REGEXP = r"(http.?:\/\/.*)"
@bot.message_handler(regexp=URL_REGEXP)
def handle_urls(message):
    # Grab first found link
    url = re.findall(URL_REGEXP, message.text)[0]
    threading.Thread(
        target=worker,
        kwargs={
            "message": message,
            "url": url
        }
    ).start()

# Handle files
@bot.message_handler(content_types=["document"])
def handle_files(message):
    # Get playlist from telegram
    file_info = bot.get_file(message.document.file_id)
    url = "https://api.telegram.org/file/bot{0}/{1}".format(telegram_token, file_info.file_path)
    filename = TEMP_FOLDER + "playlist-" + random_string()
    download_file(
        requests.get(url),
        filename
    )

    # Send list of urls
    list_of_urls = "Found URLs:\n\n"
    count = 0
    for url in get_urls_from_playlist(filename):
        list_of_urls += "{}\n\n".format(url)
        count += 1
    if count == 0:
        bot.send_message(message.chat.id, error_parsing, parse_mode="HTML")
        return
    list_of_urls += "Total: {}\n".format(count)
    bot.send_message(message.chat.id, list_of_urls, parse_mode="HTML", disable_web_page_preview=True)
    rm(filename)

bot.polling(none_stop=True)
