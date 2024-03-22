#!/usr/bin/env python
# This program is dedicated to the public domain under the CC0 license.
# pylint: disable=import-error,unused-argument
"""
Simple example of a bot that uses a custom webhook setup and handles custom updates.
For the custom webhook setup, the libraries `starlette` and `uvicorn` are used. Please install
them as `pip install starlette~=0.20.0 uvicorn~=0.23.2`.
Note that any other `asyncio` based web server framework can be used for a custom webhook setup
just as well.

Usage:
Set bot Token, URL, admin CHAT_ID and PORT after the imports.
You may also need to change the `listen` value in the uvicorn configuration to match your setup.
Press Ctrl-C on the command line or send a signal to the process to stop the bot.
"""
import asyncio
import json
import os
import redis
from dataclasses import dataclass
from typing import Union, TypedDict
import requests
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import __version__ as TG_VER
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
    ExtBot,
    CallbackQueryHandler, MessageHandler,
)
from telegram.ext import filters
from config import LANGUAGES, LANGUAGE_SELCTION, BOT_LODING_MSG, BOT_NAME, BOT_SELECTION, API_ERROR_MSG
from logger import logger
from telemetry_logger import TelemetryLogger

telemetryLogger = TelemetryLogger()

# Define configuration constants
DEFAULT_LANG = "en"
DEFAULT_BOT = "story"
SUPPORTED_LANGUAGES = os.getenv('SUPPORTED_LANGUAGES', "").split(",")
TELEGRAM_BASE_URL = os.environ["TELEGRAM_BASE_URL"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
botName = os.environ['TELEGRAM_BOT_NAME']
concurrent_updates = int(os.getenv('concurrent_updates', '256'))
pool_time_out = int(os.getenv('pool_timeout', '30'))
connection_pool_size = int(os.getenv('connection_pool_size', '1024'))
connect_time_out = int(os.getenv('connect_timeout', '300'))
read_time_out = int(os.getenv('read_timeout', '15'))
write_time_out = int(os.getenv('write_timeout', '10'))
workers = int(os.getenv("UVICORN_WORKERS", "4"))
redis_host = os.getenv("REDIS_HOST", "172.17.0.1")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_index = int(os.getenv("REDIS_INDEX", "1"))


print("----Redis host is :------",redis_host)
print("----Redis port is :------",redis_port)
try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )

# Connect to Redis
redis_client = redis.Redis(host=redis_host, port=redis_port) #, db=redis_index)  # Adjust host and port if needed

print("----Redis client is :------",redis_client)

# Define a function to store and retrieve data in Redis
def store_data(key, value):
    redis_client.set(key, value)


def retrieve_data(key):
    data_from_redis = redis_client.get(key)
    return data_from_redis.decode('utf-8') if data_from_redis is not None else None


@dataclass
class WebhookUpdate:
    """Simple dataclass to wrap a custom update type"""
    user_id: int
    payload: str


class CustomContext(CallbackContext[ExtBot, dict, dict, dict]):
    """
    Custom CallbackContext class that makes `user_data` available for updates of type
    `WebhookUpdate`.
    """

    @classmethod
    def from_update(
            cls,
            update: object,
            application: "Application",
    ) -> "CustomContext":
        if isinstance(update, WebhookUpdate):
            return cls(application=application, user_id=update.user_id)
        return super().from_update(update, application)


class ApiResponse(TypedDict):
    output: any


class ApiError(TypedDict):
    error: Union[str, requests.exceptions.RequestException]


def get_user_langauge(update: Update, default_lang=None) -> str:
    user_id_lan = str(update.effective_chat.id) + '_language'
    selected_lang = retrieve_data(user_id_lan)
    if selected_lang:
        return selected_lang
    else:
        return default_lang


def get_user_bot(update: Update, default_bot=None) -> str:
    user_id_bot = str(update.effective_chat.id) + '_bot'
    selected_bot = retrieve_data(user_id_bot)
    if selected_bot:
        return selected_bot
    else:
        return default_bot


async def send_message_to_bot(chat_id, text, context: CustomContext, parse_mode="Markdown", ) -> None:
    """Send a message  to bot"""
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)


async def start(update: Update, context: CustomContext) -> None:
    """Send a message when the command /start is issued."""
    user_name = update.message.chat.first_name
    logger.info({"id": update.effective_chat.id, "username": user_name, "category": "logged_in", "label": "logged_in"})
    await send_message_to_bot(update.effective_chat.id, f"Namaste 🙏\nWelcome to *e-Jaadui Pitara*\n_(Powered by Bhashini)_", context)
    await language_handler(update, context)


def create_language_keyboard(supported_languages):
    """Creates an inline keyboard markup with buttons for supported languages."""
    inline_keyboard_buttons = []
    for language in LANGUAGES:
        if language["code"] in supported_languages:
            button = InlineKeyboardButton(
                text=language["text"], callback_data=f"lang_{language['code']}"
            )
            inline_keyboard_buttons.append([button])
    return inline_keyboard_buttons


async def language_handler(update: Update, context: CustomContext):
    inline_keyboard_buttons = create_language_keyboard(SUPPORTED_LANGUAGES)
    reply_markup = InlineKeyboardMarkup(inline_keyboard_buttons)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="\nPlease select a Language to proceed", reply_markup=reply_markup)


async def preferred_language_callback(update: Update, context: CustomContext):
    callback_query = update.callback_query
    preferred_language = callback_query.data[len("lang_"):]
    context.user_data['language'] = preferred_language
    user_id_lan = str(update.effective_chat.id) + '_language'
    store_data(user_id_lan, preferred_language)
    logger.info(
        {"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "language_selection",
         "label": "engine_selection", "value": preferred_language})
    await callback_query.answer()
    await bot_handler(update, context)
    # return query_handler


async def bot_handler(update: Update, context: CustomContext):
    button_labels = getMessage(update, context, BOT_NAME)
    inline_keyboard_buttons = [
        [InlineKeyboardButton(button_labels["story"], callback_data='botname_story')],
        [InlineKeyboardButton(button_labels["teacher"], callback_data='botname_teacher')],
        [InlineKeyboardButton(button_labels["parent"], callback_data='botname_parent')]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard_buttons)
    text_message = getMessage(update, context, LANGUAGE_SELCTION)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text_message, reply_markup=reply_markup, parse_mode="Markdown")


async def preferred_bot_callback(update: Update, context: CustomContext):
    callback_query = update.callback_query
    preferred_bot = callback_query.data[len("botname_"):]
    context.user_data['botname'] = preferred_bot
    user_id_bot = str(update.effective_chat.id) + '_bot'
    store_data(user_id_bot, preferred_bot)
    text_msg = getMessage(update, context, BOT_SELECTION)[preferred_bot]
    logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "bot_selection", "label": "bot_selection", "value": preferred_bot})
    await callback_query.answer()
    await context.bot.sendMessage(chat_id=update.effective_chat.id, text=text_msg, parse_mode="Markdown")


async def help_command(update: Update, context: CustomContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


def getMessage(update: Update, context: CustomContext, mapping):
    selectedLang = get_user_langauge(update, DEFAULT_LANG)
    try:
        return mapping[selectedLang]
    except:
        return mapping[DEFAULT_LANG]


def get_bot_endpoint(botName: str):
    if botName == "story":
        return os.environ["STORY_API_BASE_URL"] + '/v1/query_rstory'
    else:
        return os.environ["ACTIVITY_API_BASE_URL"] + '/v1/query'


async def get_query_response(query: str, voice_message_url: str, update: Update, context: CustomContext) -> Union[
    ApiResponse, ApiError]:
    voice_message_language = get_user_langauge(update, DEFAULT_LANG)
    selected_bot = get_user_bot(update, DEFAULT_BOT)
    context.user_data['language'] = voice_message_language
    context.user_data['botname'] = selected_bot
    logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "language_selected": voice_message_language, "bot_selected": selected_bot})
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    url = get_bot_endpoint(selected_bot)
    try:
        reqBody: dict
        if voice_message_url is None:
            reqBody = {
                "input": {
                    "language": voice_message_language,
                    "text": query
                },
                "output": {
                    'format': 'text'
                }
            }
        else:
            reqBody = {
                "input": {
                    "language": voice_message_language,
                    "audio": voice_message_url
                },
                "output": {
                    'format': 'audio'
                }
            }

        if selected_bot != "story":
            reqBody["input"]["audienceType"] = selected_bot
        logger.info(f" API Request Body: {reqBody}")
        headers = {
            "x-source": "telegram",
            "x-request-id": str(message_id),
            "x-device-id": f"d{user_id}",
            "x-consumer-id": str(user_id)
        }
        response = requests.post(url, data=json.dumps(reqBody), headers=headers)
        response.raise_for_status()
        data = response.json()
        requests.session().close()
        response.close()
        return data
    except requests.exceptions.RequestException as e:
        return {'error': e}
    except (KeyError, ValueError):
        return {'error': 'Invalid response received from API'}


async def response_handler(update: Update, context: CustomContext) -> None:
    await query_handler(update, context)


async def query_handler(update: Update, context: CustomContext):
    voice_message = None
    query = None
    if update.message.text:
        query = update.message.text
        logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "query_handler", "label": "question", "value": query})
    elif update.message.voice:
        voice_message = update.message.voice

    voice_message_url = None
    if voice_message is not None:
        voice_file = await voice_message.get_file()
        voice_message_url = voice_file.file_path
        logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "query_handler", "label": "voice_question", "value": voice_message_url})
    await context.bot.send_message(chat_id=update.effective_chat.id, text=getMessage(update, context, BOT_LODING_MSG))
    await handle_query_response(update, context, query, voice_message_url)
    return query_handler


async def handle_query_response(update: Update, context: CustomContext, query: str, voice_message_url: str):
    response = await get_query_response(query, voice_message_url, update, context)
    if "error" in response:
        error_msg = getMessage(update, context, API_ERROR_MSG)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=error_msg)
        info_msg = {"id": update.effective_chat.id, "username": update.effective_chat.first_name,
                    "category": "handle_query_response", "label": "question_sent", "value": query}
        logger.info(info_msg)
        merged = dict()
        merged.update(info_msg)
        merged.update(response)
        logger.error(merged)
    else:
        logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name,
                     "category": "handle_query_response", "label": "answer_received", "value": query})
        answer = response['output']["text"]
        keyboard = [
            [InlineKeyboardButton("👍🏻", callback_data=f'message-liked__{update.message.id}'),
             InlineKeyboardButton("👎🏻", callback_data=f'message-disliked__{update.message.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=answer, parse_mode="Markdown")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide your feedback", parse_mode="Markdown", reply_markup=reply_markup)
        if response['output']["audio"]:
            audio_output_url = response['output']["audio"]
            audio_request = requests.get(audio_output_url)
            audio_data = audio_request.content
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio_data)


async def preferred_feedback_callback(update: Update, context: CustomContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    queryData = query.data.split("__")
    selected_bot = get_user_bot(update, DEFAULT_BOT)
    user_id = update.callback_query.from_user.id
    eventData = {
        "x-source": "telegram",
        "x-request-id": str(queryData[1]),
        "x-device-id": f"d{user_id}",
        "x-consumer-id": str(user_id),
        "subtype": queryData[0],
        "edataId": selected_bot
    }
    interectEvent = telemetryLogger.prepare_interect_event(eventData)
    telemetryLogger.add_event(interectEvent)
    # # CallbackQueries need to be answered, even if no notification to the user is needed
    # # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer("Thanks for your feedback.")
    # await query.delete_message()
    thumpUpIcon = "👍" if queryData[0] == "message-liked" else "👍🏻"
    thumpDownIcon = "👎" if queryData[0] == "message-disliked" else "👎🏻"
    keyboard = [
        [InlineKeyboardButton(thumpUpIcon, callback_data='replymessage_liked'),
         InlineKeyboardButton(thumpDownIcon, callback_data='replymessage_disliked')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Please provide your feedback:", reply_markup=reply_markup)


async def preferred_feedback_reply_callback(update: Update, context: CustomContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    # # CallbackQueries need to be answered, even if no notification to the user is needed
    # # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()


async def main() -> None:
    """Set up PTB application and a web application for handling the incoming requests."""
    logger.info('################################################')
    logger.info('# Telegram bot name %s', botName)
    logger.info('################################################')

    context_types = ContextTypes(context=CustomContext)
    # Here we set updater to None because we want our custom webhook server to handle the updates.persistence(persistence)
    # and hence we don't need an Updater instance
    application = (
        Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).context_types(context_types).pool_timeout(pool_time_out).connection_pool_size(connection_pool_size).concurrent_updates(True).concurrent_updates(concurrent_updates).connect_timeout(
            connect_time_out).read_timeout(read_time_out).write_timeout(write_time_out).build()
    )

    # register handlers
    application.add_handler(CommandHandler("start", start, block=False))
    application.add_handler(CommandHandler("help", help_command, block=False))
    application.add_handler(CommandHandler('select_language', language_handler, block=False))
    application.add_handler(CommandHandler('select_bot', bot_handler, block=False))
    application.add_handler(CallbackQueryHandler(preferred_language_callback, pattern=r'lang_\w*', block=False))
    application.add_handler(CallbackQueryHandler(preferred_bot_callback, pattern=r'botname_\w*', block=False))
    application.add_handler(CallbackQueryHandler(preferred_feedback_callback, pattern=r'message-\w*', block=False))
    application.add_handler(CallbackQueryHandler(preferred_feedback_reply_callback, pattern=r'replymessage_\w*', block=False))
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, response_handler, block=False))

    # Pass webhook settings to telegram
    await application.bot.set_webhook(url=f"{TELEGRAM_BASE_URL}/telegram", allowed_updates=Update.ALL_TYPES)

    # Set up webserver
    async def telegram(request: Request) -> Response:
        """Handle incoming Telegram updates by putting them into the `update_queue`"""
        body = await request.json()
        await application.update_queue.put(
            Update.de_json(data=body, bot=application.bot)
        )
        return Response()

    async def health(_: Request) -> PlainTextResponse:
        """For the health endpoint, reply with a simple plain text message."""
        return PlainTextResponse(content="The bot is still running fine :)")

    starlette_app = Starlette(
        routes=[
            Route("/telegram", telegram, methods=["POST"]),
            Route("/healthcheck", health, methods=["GET"]),
        ]
    )
    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            port=8000,
            use_colors=False,
            host="0.0.0.0",
            workers=workers
        )
    )

    # Run application and webserver together
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
