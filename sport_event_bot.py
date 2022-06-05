# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Created By  : KMiNT21
# Created Date: 2022. In Ukraine during war.
# version ='1.0'
# ---------------------------------------------------------------------------
"""Telegram BOT for organization any event what need participants to be registered.

To use it on your own you need your own API_TOKEN from BOT_FATHER. Follow his instructions.
Then create token.txt file in project folder and stat this main file.

Based on python-telegram-bot v13.xx (multithreaded).
May be it will be rewrited to python-telegram-bot v20.0 with asyncio in future.

TODO: priority list of participants?, bot name (any) removing from command
TODO: /add /remove with event without description
"""

import sys
from typing import Optional, Callable  #, Union, List, Set
import gettext
from functools import wraps
import datetime
from loguru import logger
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
import parsedatetime
from recurrent.event_parser import RecurringEvent
import db


def _(text) -> int:
    """Keep text in English"""
    return text


TRANSLATIONS = {
    'uk': gettext.translation('ua', localedir='locale', languages=['ua']).gettext,
    'pt-br': gettext.translation('pt', localedir='locale', languages=['pt']).gettext,
    'ru': gettext.translation('ru', localedir='locale', languages=['ru']).gettext
    # 'en': _
}


def make_translatable_user_id_context(func):
    """Switch language if possible"""
    @wraps(func)
    def wrapped(update, context):
        global _  #pylint: disable=W0603
        try:
            lang = update.message.from_user.language_code
            logger.info(f'lang={lang}')
        except Exception:
            lang = 'en'
        if lang in TRANSLATIONS.keys():
            _ = TRANSLATIONS[lang]
        else:
            def _(text):
                return text
        result = func(update, context)
        return result
    return wrapped


def new_chat_id_memoization(chat_id: int, lang: str, all_known_chat_ids=db.get_all_chat_ids()):  # pylint: disable=W0102
    """Save every new unique CHAT_ID in database. Create new record in 'Chats'. Also save LANG."""
    # if not all_known_chat_ids:
    #     all_known_chat_ids = fbotdb.get_all_chat_ids()
    if chat_id not in all_known_chat_ids:
        all_known_chat_ids.add(chat_id)
        db.register_new_chat_id(chat_id, lang)
        logger.info(f'New chat_id: {chat_id}. All chat_ids: ')
        logger.info(all_known_chat_ids)


@logger.catch
def build_message_markup(update, _context):
    """Build message markup for this chat LANG"""
    global _  #pylint: disable=W0603
    try:
        lang = db.get_chat_lang(update.effective_message.chat_id)
        if lang in TRANSLATIONS.keys():
            _ = TRANSLATIONS[lang]
        else:
            def _(text):
                return text
    except Exception as e:
        logger.error(e)
        def _(text):
            return text
    button_list = [
    InlineKeyboardButton(_('+ Apply for participation'), callback_data='ADD'),
    InlineKeyboardButton(_('- Revoke application'), callback_data='REMOVE'),
    ]
    markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))
    return markup


@logger.catch
@make_translatable_user_id_context
def button(update, context):
    """Process clicking buttons for EVENT (register/unregister player)"""
    this_chat_id = update.effective_message.chat_id
    query = update.callback_query
    user_id = query.from_user.id
    db.add_or_update_user(user_id, query.from_user.first_name, query.from_user.last_name, query.from_user.username)
    if query.data == "ADD":
        db.apply_for_participation_in_the_event(this_chat_id, user_id)
    elif query.data == "REMOVE":
        db.revoke_application_for_the_event(this_chat_id, user_id)
    else:  # for future --- in case of additional buttons
        pass
    message_text = create_event_full_text(this_chat_id)
    if message_text != db.get_latest_bot_message_text(this_chat_id):
        query.edit_message_text(text = message_text, reply_markup=build_message_markup(update, context), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        db.save_latest_bot_message(this_chat_id, update.effective_message.message_id, message_text)
    update.callback_query.answer() # https://core.telegram.org/bots/api#callbackquery.


@logger.catch
def parse_datetime(str_datetime_in_free_form: str) -> Optional[datetime.datetime]:
    """Parse text for DATETIME in free form with RECURRENT library. """
    try:
        consts = parsedatetime.Constants(localeID=_('en_US'), usePyICU=False)
        consts.use24 = True
        r_event = RecurringEvent(parse_constants=consts)
        found_date = r_event.parse(str_datetime_in_free_form)
        if not found_date:
            # logger.debug("Date in event name not found")
            return None
        # logger.debug(f"found date: {found_date}")
        # Drop any suspicious results
        delta = found_date - datetime.datetime.now()
        if delta.days < 0:
            logger.info(f"Time DELTA.days < 0 !!!  {delta.days}. ??? skipping...")
            return None
        if delta.days > 31:
            logger.info(f"Time DELTA.days = {delta.days}. Suspicious, skipping...")
            return None
        logger.info(f"Delta: {delta.days}, {delta.seconds}")
        return found_date
    except Exception as e:
        logger.exception(e)
    return None


@logger.catch
def parse_cmd_arg(update, _context) -> str:
    """Parse command with argument and return argument only"""
    user_input = update.message.text
    space_index = user_input.find(' ')
    cmd_arg = user_input[space_index+1:].strip()
    if space_index < 0 or not cmd_arg:
        # show_help(update, _context)  # to show help or not?
        return ''
    cmd_arg = cmd_arg.replace('@zp_futsal_bot', '')
    return cmd_arg


@logger.catch
def remove_all_chat_events(update, context):
    """Change event status from Open to Closed"""
    this_chat_id = update.message.chat_id
    new_chat_id_memoization(this_chat_id, update.message.from_user.language_code)
    try:
        latest_bot_message_id = db.get_latest_bot_message_id(this_chat_id)
        if latest_bot_message_id:
            context.bot.edit_message_reply_markup(this_chat_id, latest_bot_message_id)
    except Exception as e:
        logger.warning(e)
    db.close_all_open_events_for_chat(this_chat_id)


@logger.catch
@make_translatable_user_id_context
def create_new_event(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    # Create new event for chat, try to find DATETIME and LIMIT in text
    remove_all_chat_events(update, context)
    this_chat_id = update.message.chat_id
    lang = update.message.from_user.language_code
    if lang:
        db.set_chat_lang(this_chat_id, lang)
    event_text = parse_cmd_arg(update, context)
    # this is our personal use-case, can be deleted or updated for real regex parsing LIMIT value (for fun?):
    txt = event_text.lower()
    limit_markers = ['maximum', 'limit', 'максимум', 'максимальн', 'лимит', 'ограничени']
    event_limit = 0
    if any([marker in txt for marker in limit_markers]):
        event_limit = 12  # 12 players by default
        if "12" not in txt and "15" in txt:
            event_limit = 15
    event_datetime = parse_datetime(event_text)
    message_text = _("New event created") + ":\n\n⚽️<b> " + event_text + " </b>⚽️"
    new_message = context.bot.send_message(this_chat_id, message_text, reply_markup=build_message_markup(update, context),  parse_mode=ParseMode.HTML)
    db.event_add(this_chat_id, event_text, event_datetime, event_limit, new_message.message_id, message_text)


@logger.catch
def update_event(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    new_event_text = parse_cmd_arg(update, context)
    db.update_event_text(update.message.chat_id, new_event_text)
    show_info(update, context)


@logger.catch
def set_event_datetime(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    str_datetime_in_free_form = parse_cmd_arg(update, context)
    event_datetime = parse_datetime(str_datetime_in_free_form)
    if event_datetime:
        db.set_event_datetime(update.message.chat_id, event_datetime)
    show_info(update, context)


@logger.catch
def set_players_limit(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    try:
        new_limit = parse_cmd_arg(update, context)
        db.set_players_limit(update.message.chat_id, int(new_limit))
    except Exception as e:
        logger.exception(e)


@logger.catch
def create_event_full_text(this_chat_id: int):
    """Compose full text for telegram message for the event. Using LANG from chat_id (set by event creator)"""

    lang = db.get_chat_lang(this_chat_id)
    if lang in TRANSLATIONS.keys():
        _ = TRANSLATIONS[lang]
    else:
        def _(text):
            return text

    def player_name_with_cards(games_registered, penalties: int, full_name: str, translator: Callable) -> str:
        """Add warning card to players names if needed"""
        printable_name = full_name
        games_played = games_registered - penalties
        if games_registered < 5:
            return printable_name
        if not penalties:
            return printable_name
        printable_name_with_cards = printable_name
        _ = translator
        txt_played = _('Played')
        txt_from = _('from')
        if games_registered and penalties and games_played/games_registered < 0.9:
            printable_name_with_cards = f'{printable_name}🟨 ({txt_played} {games_played} {txt_from} {games_registered})'
        if games_registered and penalties and games_played/games_registered < 0.8:
            printable_name_with_cards = f'{printable_name}🟨🟨 ({txt_played} {games_played} {txt_from} {games_registered})'
        if games_registered and penalties and games_played/games_registered < 0.7:
            printable_name_with_cards = f'{printable_name}🟨🟨🟨({txt_played} {games_played} {txt_from} {games_registered})'  # 🟥
        return printable_name_with_cards


    text = '⚽️"<b>' + db.get_event_text(this_chat_id) + '</b>"⚽️\n'

    players_limit = db.get_event_limit(this_chat_id)

    if players_limit:
        text = text + _('Players limit') + f': {players_limit}\n'

    str_datetime_iso_8601 = db.get_event_datetime(this_chat_id)
    if str_datetime_iso_8601:
        event_datetime = datetime.datetime.fromisoformat(str_datetime_iso_8601)
        text = text + '📅  ' + _('Event date and time') + f": {event_datetime.strftime('%Y-%m-%d, %H:%M')}\n"
        if event_datetime < datetime.datetime.now():
            text = text + '⏳ ' + _('Event time out') + '.\n'
        else:
            delta = event_datetime - datetime.datetime.now()
            text = text + '⏳ ' + _('Time left') + f': {delta.days} ' + _('days') + ' ' + _('and') + f' {round(delta.seconds / 60 / 60)} ' + _('hours') + '\n'

    text = text + _('Players list') + ':\n'
    text_players = ''

    players = db.get_event_users(this_chat_id)


    for n, user_id in enumerate(players, start=1):
        if players_limit and n == players_limit + 1:
            text_players = text_players + '\t\t\n' + _('Reserve') + ':\n'
        in_squad = '👟'
        if players_limit and n >= players_limit + 1:
            in_squad = '      '
        printable_name = db.compose_full_name(user_id)
        games_registered, penalties = db.get_chat_user_rp(this_chat_id, user_id)
        text_players = text_players + in_squad + f'{n}. {player_name_with_cards(games_registered, penalties, printable_name, _)}\n'

    text = text + '\n' + text_players
    text_players = ''

    canceled_players = db.get_event_revoked_users(this_chat_id)
    if canceled_players:
        text = text + '\n' + _('Revoked applications') + ':'
        for canceled_user_id in canceled_players:
            cancel_datetime = db.get_user_cancellation_datetime(this_chat_id, canceled_user_id)
            # ~ 2022-06-04 02:11:54.377618 -> 2022-06-04 02:11
            cancel_datetime = cancel_datetime[:cancel_datetime.rfind(':', 2)]

            printable_name = db.compose_full_name(canceled_user_id)
            text_players = text_players + f'      <s>{printable_name} - {cancel_datetime}</s>\n'

    if not players and not canceled_players:
        text_players = _('No applications yet')

    text = text + '\n' + text_players
    return text


@logger.catch
@make_translatable_user_id_context
def show_info(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    this_chat_id = update.message.chat_id
    if not db.get_event_text(this_chat_id):
        update.message.reply_text(_('No events'))
        return
    event_text = create_event_full_text(this_chat_id)
    # removing buttons from latest bot message
    try:
        latest_bot_message_id = db.get_latest_bot_message_id(this_chat_id)
        if latest_bot_message_id:
            context.bot.edit_message_reply_markup(this_chat_id, latest_bot_message_id)
    except Exception as e:
        logger.exception(e)
    new_message = context.bot.send_message(this_chat_id, event_text, reply_markup=build_message_markup(update, context), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    db.save_latest_bot_message(this_chat_id, new_message.message_id, event_text)


@logger.catch
@make_translatable_user_id_context
def add_player(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    user = update.message.from_user
    if db.get_event_text(update.message.chat_id):  # if found OPEN event:
        db.add_or_update_user(user.id, user.first_name, user.last_name, user.username)
        db.apply_for_participation_in_the_event(update.message.chat_id, user.id)
        logger.info(f"Event - Player canceled request: {user.id}")
    show_info(update, context)


@logger.catch
@make_translatable_user_id_context
def remove_player(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    user = update.message.from_user
    if db.get_event_text(update.message.chat_id):  # if found OPEN event:
        db.add_or_update_user(user.id, user.first_name, user.last_name, user.username)
        db.revoke_application_for_the_event(update.message.chat_id, user.id)
    show_info(update, context)


@logger.catch
@make_translatable_user_id_context
def penalty_player(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    user_id = parse_cmd_arg(update, context)
    try:
        db.penalty_for_user_in_chat(chat_id=update.message.chat_id, user_id=user_id, operator_id=update.message.from_user.user_id)
    except Exception as e:
        logger.exception(e)


@logger.catch
@make_translatable_user_id_context
def fix_squad(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    this_chat_id = update.message.chat_id
    if not db.get_event_text(this_chat_id):
        update.message.reply_text(_('No events to fix stat for'))
        return
    text = _('Current statistics for this chat room members:') +'\n<code>'
    squad = []
    players_limit = db.get_event_limit(this_chat_id)
    for position, userid in enumerate(db.get_event_users(this_chat_id), start=1):
        if not players_limit or position <= players_limit:
            try:
                squad.append(userid)
                full_name = db.compose_full_name(userid)
                games, penalties = db.get_chat_user_rp(this_chat_id, userid)
                games = games + 1
                text = text + f"{full_name} {games}/{penalties}\n"

            except Exception as e:
                logger.exception(e)
    text = text + "</code>"
    # удаление кнопок из последнего сообщения
    try:
        latest_bot_message_id = db.get_latest_bot_message_id(this_chat_id)
        if latest_bot_message_id:
            context.bot.edit_message_reply_markup(this_chat_id, latest_bot_message_id)
    except Exception as e:
        logger.exception(e)
    context.bot.send_message(this_chat_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    db.fix_event(this_chat_id)  # fix only after get_event_users() for OPEN event


@logger.catch
@make_translatable_user_id_context
def show_stat(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    all_userids = db.get_only_chat_participants(update.message.chat_id)
    if not all_userids:
        return
    text = _('Current statistics for this chat room members:') + '\n'
    text = text + '<tg-spoiler>' + _('Registrations / Penalties') + '</tg-spoiler>\n'
    text = text + '<code>'
    # all_userids = fbotdb.get_all_userids()  # global stats, not used
    for userid in all_userids:
        printable_name = db.compose_full_name(userid)
        registered, penalties = db.get_chat_user_rp(update.message.chat_id, userid)
        text = text + "ID:{}, {:>2}/{}, Full Name: {}\n".format(userid, registered, penalties, printable_name)
    text = text + '</code>'
    context.bot.send_message(update.message.chat_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@logger.catch
@make_translatable_user_id_context
def show_help(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    new_chat_id_memoization(update.message.chat_id, update.message.from_user.language_code)
    event_text = _("""
Available BOT commands:

/event_add TEXT
Register new event

/event_remove
Remove open event

/event_update TEXT
Change event description

/limit XX
Set players limit

/event_datetime DATE TIME
Set event date and time in any format. It will parsed automatically.
Example 1: 2023-01-30, 18:00
Example2: tomorrow, 14:30

/info
Show event details

/add
Register yourself to the event

/remove
Revoke your application

/fix
Fix event statistics (increment participants counters)

/penalty USERID
Increase someone's PENALTY counter for  unreasonable skipping of the event without notification others.
You can find USERID by command /stat

/stat
This group members statistics (registrations and penalties)
""")
    context.bot.send_message(update.message.chat_id, event_text, parse_mode=ParseMode.HTML)

@logger.catch
@make_translatable_user_id_context
def unknown_command_handler(update, context):
    """CommandHandler_______________________________________________________________________________________________"""
    if not update.message:
        logger.warning("No message in update handler. Full info:")
        logger.warning(update)
        return
    this_chat_id = update.message.chat_id
    if update.message.new_chat_members:
        show_info(update, context)  # Wellcome new member by sending current event info
    text = update.message.text
    if not text:
        return

    new_chat_id_memoization(this_chat_id, update.message.from_user.language_code)
    logger.info(f'Unknown command typed: {text}')
    logger.info(f'Chat ID: {update.message.chat_id}')


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    """Build menu from buttons for telegram message"""
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu



# ____________________________________________________________________________________________________________________
# ____________________________________________________________________________________________________________________
# ____________________________________________________________________________________________________________________


if __name__ == '__main__':

    logger.remove()
    logger.add("logs/logs.log", level="INFO")
    logger.add(sys.stderr, level="WARNING")

    try:
        with open('token.txt', encoding='utf-8') as f:
            api_token = f.readline()
    except Exception as err:
        logger.exception(err)
        print("Can not read api_token from token.txt")
        sys.exit()

    updater = Updater(api_token, use_context=True, workers=1)  # default workers = 4 but пофиг
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('add', add_player))
    dispatcher.add_handler(CommandHandler('remove', remove_player))
    dispatcher.add_handler(CommandHandler('info', show_info))
    dispatcher.add_handler(CommandHandler('help', show_help))
    dispatcher.add_handler(CommandHandler('stat', show_stat))
    dispatcher.add_handler(CommandHandler('fix', fix_squad))

    dispatcher.add_handler(CommandHandler('event_add', create_new_event))
    dispatcher.add_handler(CommandHandler('event_remove', remove_all_chat_events))
    dispatcher.add_handler(CommandHandler('event_update', update_event))
    dispatcher.add_handler(CommandHandler('limit', set_players_limit))
    dispatcher.add_handler(CommandHandler('penalty', penalty_player))
    dispatcher.add_handler(CommandHandler('event_datetime', set_event_datetime))

    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text | Filters.status_update.new_chat_members, unknown_command_handler))

    updater.start_polling()
    logger.info("Telegram Futsal Bot is waiting for commands...")
    updater.idle()


# Library 'python-telegram-bot' v13.xx is multithreaded.
# This is not thread-safe wraps. There is a little possibility that some new user message
# will be arrived just in the middle of processing another message in a different thread
# and the LANG will be wrong for that user (if LANGs are different).
# So, this wrapper can be replaced by func-space commands like this:

# lang = update.message.from_user.language_code
# if lang == "ru":
#     _ = lang_ru.gettext
# else:
#     def _(text):
#         return text
# inside every function
# But I want to left this as is for now. :)
