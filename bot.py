#
# Copyright (C) 2022 Karam Assany <karam.assany@disroot.org>
#
# Licensed under the MIT (Expat) license.  See LICENSE
#



import os, logging, hashlib, urllib.request

from telegram import ParseMode
from telegram.error import NetworkError
from telegram.ext import Updater, MessageHandler, Filters
from yt_dlp import YoutubeDL
from eyed3 import mp3
from eyed3.id3.frames import ImageFrame



class DisallowedError(Exception): pass



HELP_MESSAGE = """
<b>Welcome!</b>

Send/redirect a valid URL (Youtube, Invidious, etc)


<i>Hint:</i> You can use @vid to do in-line searches for Youtube videos
"""


DEFAULT_APPENDIX = \
        "<a href=\"https://t.me/YTMusicHQBot\">free allah sex</a>"

DEFAULT_DEVLINK = "https://t.me/god_is_an_enby"


TRUNK = "/app/trunk"



def humanify_size(size):

    if size is None:
        return "(unknown size)"

    else:
        try:
            size = int(size)
        except:
            return "(unknown size)"

        return "{:.2f}MB".format(size / 10 ** 6)


def humanify_time(time):

    if time is None:
        return "(unknown time)"

    else:
        try:
            time = int(time)
        except:
            return "(unknown time)"

        ts = []

        if (time // 60) > 0:

            ts.append("{}m".format(time // 60))
            time = time % 60

        ts.append("{}s".format(time))

        return " ".join(ts)


def ytd_download(url, chat_id, update_status):

    def status(msg):

        try:
            update_status(msg, parse_mode = ParseMode.HTML)

        except NetworkError:
            pass

    def progress_pre(prog):

        status("<i>Downloading...</i>\n\n" +
                "<b>Status:</b> {}\n".
                    format(prog.get("status", "unknown").capitalize()) +
                "<b>Downloaded:</b> {}\n".
                    format(humanify_size(prog.get("downloaded_bytes", None))) +
                "<b>Total size:</b> {}\n".
                    format(humanify_size(prog.get("total_bytes", None))) +
                "<b>Elapsed time:</b> {}\n".
                    format(humanify_time(prog.get("elapsed", None))) +
                "<b>Estimated time:</b> {}\n".
                    format(humanify_time(prog.get("eta", None))) +
                "<b>Download speed:</b> {}/s\n".
                    format(humanify_size(prog.get("speed", None))))

    def progress_post(prog):

        status("<i>Converting...</i>\n\n" +
                "<b>Status:</b> {}\n".
                    format(prog.get("status", "unknown").capitalize()))


    place = os.path.join(
            TRUNK,
            "C.{}.{}".format(chat_id, hashlib.md5(url.encode()).hexdigest()))

    try:
        os.mkdir(place)
    except FileExistsError:
        for fn in os.listdir(place):
            os.unlink(os.path.join(place, fn))
        os.rmdir(place)
        os.mkdir(place)

    with YoutubeDL({
            "verbose": True,
            "noplaylist": True,
            "extractaudio": True,
            "format": "bestaudio/best",
            "audioformat": "mp3",
            "ffmpeg_location": "/app/vendor/ffmpeg/",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }],
            "outtmpl": os.path.join(place, "%(channel)s - %(title)s.%(ext)s"),
            "progress_hooks": [progress_pre],
            "postprocessor_hooks": [progress_post]
            }) as ydl:

        meta = ydl.sanitize_info(
            ydl.extract_info(url, download = True))

    status("<i>Post-processing the file...</i>")

    if len(os.listdir(place)) != 1:
        raise Exception("WTF.  Multiple files downloaded")

    fn = os.path.join(place, os.listdir(place)[0])

    af = mp3.Mp3AudioFile(fn)

    af.initTag(version=(2, 3, 0))

    try:
        af.tag.artist = meta["channel"]
    except KeyError:
        pass

    try:
        af.tag.title = meta["title"]
    except KeyError:
        pass

    try:
        af.tag.images.set(
                ImageFrame.FRONT_COVER,
                urllib.request.urlopen(
                    meta["thumbnail"]
                    ).read(),
                dict(
                    webp = "image/webp",
                    jpg = "image/jpeg"
                    )[meta["thumbnail"].rpartition(".")[2]]
                )
    except KeyError as e:
        if e.args[0] != "thumbnail":
            raise e

    bitrate = af.info.bit_rate[1]

    af.tag.save()

    status("<i>Uploading the file...</i>")

    return {
            "filename": fn,
            "duration": meta.get("duration"),
            "bitrate": bitrate
            }


def bot_download(update, context):

    url = update.message.text

    rep = update.message.reply_html(
            "<i>Processing this link...</i>",
            quote = True,
            disable_web_page_preview = True)

    try:

        if "playlist" in url:

            raise DisallowedError

        df = ytd_download(
                url,
                update.effective_user.id,
                rep.edit_text)

        with open(df["filename"], "rb") as f:
            update.message.reply_audio(
                    f,
                    duration = df["duration"],
                    caption = " | ".join((
                        "{} kbps".format(df["bitrate"]),
                        "<a href=\"{}\">Source</a>".format(url),
                        os.getenv("CUSTOM_APPENDIX", DEFAULT_APPENDIX)
                        )),
                    quote = True,
                    parse_mode = ParseMode.HTML)

    except DisallowedError:

        update.message.reply_html(
                "<i>Failed to process this <a href=\"{}\">link</a></i>\n\n".
                    format(url) +
                "Playlists are currently not supported.  We're sorry",
                quote = True,
                disable_web_page_preview = True)

    except NetworkError as e:

        if "too large" in e.message:

            try:
                size = os.stat(df["filename"]).st_size
            except:
                size = None

            update.message.reply_html(
                    "<i>Failed to process this <a href=\"{}\">link</a></i>\n\n".
                        format(url) +
                    "The resulting file's size is {}, ".
                        format(humanify_size(size)) +
                    "exceeding the 50MB limit imposed by Telegram.  "
                    "We're sorry",
                    quote = True,
                    disable_web_page_preview = True)

        else: raise

    except BaseException as e:

        update.message.reply_html(
                "<i>Failed to process this <a href=\"{}\">link</a></i>\n\n".
                    format(url) +
                "<b>{}</b>: {}".format(
                    type(e).__name__,
                    repr(e.args)) +
                "\n\n"
                "Redirect this message to the <a href=\"{}\">bot developer<a>".
                    format(os.getenv("CUSTOM_DEVLINK"), DEFAULT_DEVLINK),
                quote = True,
                disable_web_page_preview = True)

        raise e

    finally:

        rep.delete()


def bot_help(update, context):

    update.message.reply_html(
            HELP_MESSAGE,
            disable_web_page_preview = True)


def main():

    logging.basicConfig(
            format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level = int(os.getenv("LOG_LEVEL", 0)))
    logger = logging.getLogger(__name__)

    TOKEN = os.environ["BOT_TOKEN"]

    os.mkdir(TRUNK)

    updater = Updater(TOKEN)

    updater.dispatcher.add_handler(MessageHandler(
        Filters.entity("url"),
        bot_download))
    updater.dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.entity("url"),
        bot_help))

    updater.start_webhook(
            listen = "0.0.0.0",
            port = int(os.environ["PORT"]),
            url_path = TOKEN,
            webhook_url = "https://{}.herokuapp.com/{}".format(
                os.environ["HEROKU_APP_NAME"],
                TOKEN))

    updater.idle()



if __name__ == "__main__": main()
