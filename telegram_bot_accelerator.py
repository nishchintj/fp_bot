import json
import os
from typing import Union, TypedDict
from config import LANGUAGES, LANGUAGE_SELCTION,BOT_LODING_MSG, BOT_NAME, BOT_SELECTION, API_ERROR_MSG
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import __version__ as TG_VER
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext, \
    CallbackQueryHandler, Application
from telemetry_logger import TelemetryLogger
from logger import logger

"""
start - Start the bot
set_engine - To choose the engine 
set_language - To choose language of your choice
"""

load_dotenv()

botName = os.environ['TELEGRAM_BOT_NAME']
DEFAULT_LANG = "en"
DEFAULT_BOT = "story"
SUPPORTED_LANGUAGES = os.getenv('SUPPORTED_LANGUAGES', "").split(",")
concurrent_updates = int(os.getenv('concurrent_updates', '1'))
pool_time_out = int(os.getenv('pool_timeout', '10'))
connection_pool_size = int(os.getenv('connection_pool_size', '100'))
telemetryLogger = TelemetryLogger()
class ApiResponse(TypedDict):
    output: any
class ApiError(TypedDict):
    error: Union[str, requests.exceptions.RequestException]

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

def getUserLangauge(context: CallbackContext, default_lang = None):
    selectedLang =  context.user_data.get('language')
    if selectedLang:
        return selectedLang
    else:
        return default_lang


async def send_message_to_bot(chat_id, text, context: CallbackContext, parse_mode="Markdown", ) -> None:
    """Send a message  to bot"""
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_name = update.message.chat.first_name
    logger.info({"id": update.effective_chat.id, "username": user_name, "category": "logged_in", "label": "logged_in"})
    await send_message_to_bot(update.effective_chat.id, f"Namaste 🙏\nWelcome to *FarmPulse* \n I am an AI powered chatbot, designed specifically for agriculutral sector", context)
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

async def language_handler(update: Update, context: CallbackContext):
    inline_keyboard_buttons = create_language_keyboard(SUPPORTED_LANGUAGES)
    reply_markup = InlineKeyboardMarkup(inline_keyboard_buttons)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="\nPlease select a Language to proceed", reply_markup=reply_markup)

async def preferred_language_callback(update: Update, context: CallbackContext):
    callback_query = update.callback_query
    preferred_language = callback_query.data[len("lang_"):]
    context.user_data['language'] = preferred_language
    logger.info(
        {"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "language_selection",
         "label": "engine_selection", "value": preferred_language})
    await callback_query.answer()
    await bot_handler(update, context)
    # return query_handler

async def bot_handler(update: Update, context: CallbackContext):
    button_labels = getMessage(context, BOT_NAME)
    inline_keyboard_buttons = [
        # [InlineKeyboardButton(button_labels["story"], callback_data='botname_story')],
        # [InlineKeyboardButton(button_labels["teacher"], callback_data='botname_teacher')],
        [InlineKeyboardButton(button_labels["parent"], callback_data='botname_parent')]]    
    reply_markup = InlineKeyboardMarkup(inline_keyboard_buttons)  
    text_message = getMessage(context, LANGUAGE_SELCTION)
    #text_message = 'Please type in your query for me' 
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text_message, reply_markup=reply_markup, parse_mode="Markdown")  #reply_markup=reply_markup

async def preferred_bot_callback(update: Update, context: CallbackContext):
    callback_query = update.callback_query
    preferred_bot = callback_query.data[len("botname_"):]
    context.user_data['botname'] = preferred_bot
    text_msg = getMessage(context, BOT_SELECTION)[preferred_bot]
    logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "bot_selection","label": "bot_selection", "value": preferred_bot})
    await callback_query.answer()
    await context.bot.sendMessage(chat_id=update.effective_chat.id, text= text_msg, parse_mode="Markdown")
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

def getMessage(context: CallbackContext, mapping):
    selectedLang =  context.user_data.get('language', None) 
    try:
        return mapping[selectedLang]
    except:
        return mapping[DEFAULT_LANG]

def get_bot_endpoint(botName: str):
    if botName == "story":
        return os.environ["STORY_API_BASE_URL"] + '/v1/query_rstory'
    else:
        return os.environ["ACTIVITY_API_BASE_URL"] + '/v1/query'

async def get_query_response(query: str, voice_message_url: str, update: Update, context: CallbackContext) -> Union[
    ApiResponse, ApiError]:
    voice_message_language = context.user_data.get('language') or DEFAULT_LANG
    selected_bot = context.user_data.get('botname') or DEFAULT_BOT
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    url = get_bot_endpoint(selected_bot)
    try:
        reqBody: dict
        if voice_message_url is None:
            reqBody = {
                        "input": {
                            "language": voice_message_language,
                            "text": query,
                            "audienceType": "parent"
                        },
                        "output": {
                            "format": "text"
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
            print("---------request body is :-----------",reqBody)
            print("selected bot is :", selected_bot)
            reqBody["input"]["audienceType"] = str(selected_bot)
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

async def response_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query_handler(update, context)

async def query_handler(update: Update, context: CallbackContext):
    voice_message = None
    query = None
    if update.message.text:
        query = update.message.text
        logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "query_handler","label": "question", "value": query})
    elif update.message.voice:
        voice_message = update.message.voice

    voice_message_url = None
    if voice_message is not None:
        voice_file = await voice_message.get_file()
        voice_message_url = voice_file.file_path
        logger.info({"id": update.effective_chat.id, "username": update.effective_chat.first_name, "category": "query_handler","label": "voice_question", "value": voice_message_url})
    await context.bot.send_message(chat_id=update.effective_chat.id, text=getMessage(context, BOT_LODING_MSG))
    await handle_query_response(update, context, query, voice_message_url)
    return query_handler

async def handle_query_response(update: Update, context: CallbackContext, query: str, voice_message_url: str):
    response = await get_query_response(query, voice_message_url, update, context)
    if "error" in response:
        errorMsg = getMessage(context, API_ERROR_MSG)
        await context.bot.send_message(chat_id=update.effective_chat.id,text=errorMsg)
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
        await context.bot.send_message(chat_id=update.effective_chat.id, text=answer)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide your feedback", parse_mode="Markdown", reply_markup=reply_markup)
        if response['output']["audio"]:
            audio_output_url = response['output']["audio"]
            audio_request = requests.get(audio_output_url)
            audio_data = audio_request.content
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio_data)

async def preferred_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    queryData = query.data.split("__")
    selected_bot = context.user_data.get('botname') or DEFAULT_BOT
    user_id = update.callback_query.from_user.id
    message_id = queryData[1]
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

async def preferred_feedback_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    # # CallbackQueries need to be answered, even if no notification to the user is needed
    # # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

def main() -> None:
    logger.info('################################################')
    logger.info('# Telegram bot name %s', botName)
    logger.info('################################################')

    logger.info({"concurrent_updates": concurrent_updates})
    logger.info({"pool_time_out": pool_time_out})
    logger.info({"connection_pool_size": connection_pool_size})

    application = Application.builder().token(os.environ['TELEGRAM_BOT_TOKEN']).pool_timeout(pool_time_out).connection_pool_size(connection_pool_size).concurrent_updates(concurrent_updates).connect_timeout(pool_time_out).read_timeout(pool_time_out).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler('select_language', language_handler))
    application.add_handler(CommandHandler('select_bot', bot_handler))

    application.add_handler(CallbackQueryHandler(preferred_language_callback, pattern=r'lang_\w*'))
    application.add_handler(CallbackQueryHandler(preferred_bot_callback, pattern=r'botname_\w*')) 
    application.add_handler(CallbackQueryHandler(preferred_feedback_callback, pattern=r'message-\w*'))
    application.add_handler(CallbackQueryHandler(preferred_feedback_reply_callback, pattern=r'replymessage_\w*')) 
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, response_handler))

    application.run_polling()


if __name__ == "__main__":
    main()