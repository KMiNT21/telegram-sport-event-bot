# -*- coding: utf-8 -*-
"""This module works with sqlite3 database wtih 3 tables: Users, Chats, Events
"""

import sys
import sqlite3
import datetime
from typing import List, Set, Tuple
from loguru import logger

#pylint: disable=C0116

DB_FILENAME = 'bot_db.sqlite3'

logger.remove()
logger.add("logs/logs.log", level="DEBUG")
logger.add(sys.stderr, level="DEBUG")


@logger.catch
def reconnect():
    # return sqlite3.connect(DB_FILENAME, check_same_thread = False)
    return sqlite3.connect(DB_FILENAME)


def create_table_users():
    conn = reconnect()
    conn.execute('''CREATE TABLE Users
         (user_id  INTEGER PRIMARY KEY     NOT NULL,
         first_name TEXT DEFAULT "",
         last_name  TEXT DEFAULT "",
         username   TEXT DEFAULT "",
         birth_date TEXT DEFAULT "",
         phone TEXT DEFAULT "",
         facebook TEXT DEFAULT "",
         extra TEXT DEFAULT ""
         );''')
    conn.commit()
    conn.close()


def create_table_events():
    conn = reconnect()
    conn.execute("PRAGMA foreign_keys = 1;")
    conn.commit()
    cur=conn.cursor()
    cur.execute('''CREATE TABLE Events
         (event_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
         chat_id INTEGER,
         status TEXT DEFAULT "Open",
         description TEXT DEFAULT "",
         datetime TEXT DEFAULT "",
         players_limit INT DEFAULT 0,
         extra1 TEXT DEFAULT "",
         extra2 TEXT DEFAULT "",
         extra3 TEXT DEFAULT "",
         FOREIGN KEY(chat_id) REFERENCES Chats(chat_id)
         );''')
    conn.commit()
    conn.close()


def create_table_chats():
    conn = reconnect()
    conn.execute('''CREATE TABLE Chats
         (chat_id INTEGER PRIMARY KEY NOT NULL,
         lang TEXT,
         priority_members TEXT DEFAULT "",
         latest_event_id INT DEFAULT 0,
         latest_bot_message_id INT DEFAULT 0,
         latest_bot_message_text TEXT DEFAULT "",
         extra1 TEXT DEFAULT "",
         extra2 TEXT DEFAULT "",
         extra3 TEXT DEFAULT ""
         );''')
    conn.commit()
    conn.close()


def create_table_participants():
    conn = reconnect()
    conn.execute('''CREATE TABLE Participants
         (event_id INT  NOT NULL,
         user_id INT,
         operation_datetime DATETIME NOT NULL,
         FOREIGN KEY(event_id) REFERENCES Events(event_id),
         UNIQUE(event_id, user_id)
         );''')
    conn.commit()
    conn.close()


def create_table_revoked():
    conn = reconnect()
    conn.execute('''CREATE TABLE Revoked
         (event_id INT  NOT NULL,
         user_id INT,
         operation_datetime DATETIME NOT NULL,
         FOREIGN KEY(event_id) REFERENCES Events(event_id),
         UNIQUE(event_id, user_id)
         );''')
    conn.commit()
    conn.close()


def create_table_chat_penalties():
    conn = reconnect()
    conn.execute('''CREATE TABLE Penalties
        (chat_id INT,
        user_id INT,
        operation_datetime DATETIME NOT NULL,
        operator_id INT,
        FOREIGN KEY(chat_id) REFERENCES Chats(chat_id),
        FOREIGN KEY(user_id) REFERENCES Users(user_id),
        FOREIGN KEY(operator_id) REFERENCES Users(user_id)
        );''')
    conn.commit()
    conn.close()


@logger.catch
def close_all_open_events_for_chat(chat_id: int):
    conn = reconnect()
    conn.execute('''UPDATE Events SET status = "Closed" WHERE chat_id = ? AND status = "Open";''', (chat_id, ))
    conn.commit()
    conn.close()


def event_add(chat_id: int, text: str, dtm: datetime.datetime, players_limit: int, latest_bot_message_id:int, latest_bot_message_text:str):
    event_datetime = str(dtm) if dtm else ''
    conn = reconnect()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = 1;")
    cur.execute('''INSERT into Events (chat_id, description, datetime, players_limit)
    values (?, ?, ?, ?);''',  (chat_id, text, event_datetime, players_limit))
    conn.execute('''UPDATE Chats SET
    latest_event_id = ?, latest_bot_message_id = ?, latest_bot_message_text = ?  WHERE chat_id = ?;''',
    (cur.lastrowid, latest_bot_message_id, latest_bot_message_text, chat_id,))
    conn.commit()
    conn.close()



@logger.catch
def update_event_text(chat_id, new_text):
    conn = reconnect()
    conn.execute('''UPDATE Events SET description = ?  WHERE status = "Open" AND chat_id = ? ;''', (new_text, chat_id, ))
    conn.commit()
    conn.close()


@logger.catch
def get_event_text(chat_id) -> str:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT description FROM Events WHERE STATUS="Open" AND chat_id = ? ;''', (chat_id, ))
    row = cur.fetchone()
    conn.close()
    if not row:
        logger.info("get_event_text -> No events!")
        return ''
    return row[0]


@logger.catch
def set_players_limit(chat_id, players_limit: int):
    conn = reconnect()
    conn.execute('''UPDATE Events SET players_limit = ?  WHERE status = "Open" AND chat_id = ? ;''', (players_limit, chat_id, ))
    conn.commit()
    conn.close()



@logger.catch
def get_event_limit(chat_id) -> int:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT players_limit FROM Events WHERE status="Open" AND chat_id = ? ;''', (chat_id, ))
    row = cur.fetchone()
    conn.close()
    if not row:
        logger.warning("get_event_limit -> No events!")
        return 0
    elif not row[0]:
        return 0
    else:
        return int(row[0])


@logger.catch
def set_event_datetime(chat_id: int, dtm: datetime.datetime):
    conn = reconnect()
    conn.execute('''UPDATE Events SET datetime = ?  WHERE status = "Open" AND chat_id = ? ;''', (dtm, chat_id, ))
    conn.commit()
    conn.close()


@logger.catch
def get_event_datetime(chat_id: int) -> str:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT datetime FROM Events WHERE status="Open" AND chat_id = ? ;''', (chat_id, ))
    row = cur.fetchone()
    conn.close()
    if not row:
        logger.warning("get_event_datetime -> No events!")
        return ''
    return row[0]


@logger.catch
def fix_event(chat_id):
    conn = reconnect()
    conn.execute('''UPDATE Events SET status = "Fixed"  WHERE status = "Open" AND chat_id = ? ;''', (chat_id, ))
    conn.commit()
    conn.close()


@logger.catch
def get_latest_bot_message_id(chat_id) -> int:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT latest_bot_message_id FROM Chats WHERE chat_id = ? ;''', (chat_id, ))
    row = cur.fetchone()
    conn.close()
    if not row:
        logger.debug("get_latest_bot_message_id -> No previous messages to edit")
        return 0
    else:
        return int(row[0])


@logger.catch
def get_latest_bot_message_text(chat_id) -> str:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT latest_bot_message_text FROM Chats WHERE chat_id = ? ;''', (chat_id, ))
    row = cur.fetchone()
    conn.close()
    if not row:
        logger.warning("get_latest_bot_message_text: No events!")
        return ""
    else:
        return row[0]


@logger.catch
def save_latest_bot_message(chat_id, message_id, message_text):
    conn = reconnect()
    conn.execute('''UPDATE Chats SET latest_bot_message_id = ? , latest_bot_message_text = ?  WHERE chat_id = ? ;''', (message_id, message_text, chat_id, ))
    conn.commit()
    conn.close()


@logger.catch
def add_or_update_user(user_id, first_name="", last_name="", username=""):
    # logger.debug(f'add_or_update_user()...{user_record}')
    if first_name is None:
        first_name = ""
    if last_name is None:
        last_name = ""
    if username is None:
        username = ""
    user_record = (user_id, first_name, last_name, username)
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('SELECT FIRST_NAME, LAST_NAME, USERNAME FROM Users WHERE user_id = ?;', (user_id,))
    row = cur.fetchone()
    if not row:
        logger.debug('Adding NEW user record')
        conn.execute('INSERT into Users(user_id, first_name, last_name, username) values (?, ?, ?, ?)', user_record)
        conn.commit()
    elif row != (first_name, last_name, username):
        logger.debug('Updating user record')
        conn.execute('UPDATE Users SET first_name = ?, last_name = ?, username = ? WHERE user_id = ?;', user_record)
        conn.commit()
    else:
        logger.debug('    no new data')
    conn.close()


@logger.catch
def compose_full_name(user_id: int) -> str:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute(f'''SELECT first_name, last_name, username FROM users WHERE user_id = {user_id};''')
    row = cur.fetchone()
    conn.close()
    if not row:
        return 'USER_ID NOT FOUND!'
    fnm = row[0] if row[0] else ''
    lnm = row[1] if row[1] else ''
    unm = row[2] if row[2] else ''
    res = " ".join([fnm, lnm])
    res = " ".join(res.split())
    if res and unm:
        res = f"{res} ({unm})"
    if not res and unm:
        res = unm
    if not res:
        return str(user_id)
    return res


def penalty_for_user_in_chat(chat_id, user_id, operator_id: int):
    conn = reconnect()
    dtm = datetime.datetime.now()
    conn.execute('''INSERT INTO Penalties(chat_id, user_id, operation_datetime, operator_id) VALUES (?, ?, ?, ?);''',
    (chat_id, user_id, dtm, operator_id))
    conn.commit()
    conn.close()


@logger.catch
def get_all_userids() -> List[int]:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT user_id FROM Users;''')
    all_rows = cur.fetchall()
    conn.close()
    all_ids = []
    for row in all_rows:
        all_ids.append(int(row[0]))
    return all_ids


@logger.catch
def get_all_chat_ids() -> Set[int]:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''SELECT chat_id FROM Chats;''')
    all_rows = cur.fetchall()
    conn.close()
    all_chat_ids = set()
    for row in all_rows:
        all_chat_ids.add(int(row[0]))
    return all_chat_ids


@logger.catch
def register_new_chat_id(chat_id: int, lang: str):
    language_code = lang if lang else  ''  # Telegram API language_code. Example: 'en'
    conn = reconnect()
    conn.execute('INSERT into Chats(chat_id, lang) values (?, ?)', (chat_id, language_code))
    conn.commit()
    conn.close()


@logger.catch
def get_only_chat_participants(chat_id: int) -> List[int]:
    conn = reconnect()
    cur = conn.cursor()

    cur.execute('''
        SELECT DISTINCT user_id
        FROM Participants
        WHERE event_id =
        (SELECT event_id FROM Events WHERE chat_id = ?)
        ;''', (chat_id, ))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return []
    user_ids = [int(user_id[0]) for user_id in rows]
    return user_ids


@logger.catch
def get_chat_lang(chat_id: int) -> str:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('SELECT lang FROM Chats WHERE chat_id = ?;', (chat_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        logger.info(f'Can not get LANG for this chat_id: {chat_id}')
        return 'en'
    return row[0]


@logger.catch
def set_chat_lang(chat_id: int, lang: str):
    conn = reconnect()
    conn.execute("Update Chats SET lang = ? WHERE chat_id = ?;", (lang, chat_id,))
    conn.commit()
    conn.close()


def get_event_users(chat_id: int) -> List[int]:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM Participants WHERE event_id IN (SELECT event_id FROM Events WHERE status = "Open" AND  chat_id=?);', (chat_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return []
    users = [row[0] for row in rows if row[0] is not None]
    return users

def get_event_revoked_users(chat_id: int) -> List[int]:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM Revoked WHERE event_id IN (SELECT event_id FROM Events WHERE status = "Open" AND  chat_id=?);', (chat_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return []
    users = [row[0] for row in rows if row[0] is not None]
    return users


def apply_for_participation_in_the_event(chat_id: int, user_id: int):
    logger.info(f"Event - New player request: {user_id}")
    conn = reconnect()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = 1;")
    dtm = datetime.datetime.now()
    cur.execute('''
        INSERT or REPLACE into
        Participants (event_id, user_id, operation_datetime)
        values ((SELECT event_id FROM Events WHERE status = "Open" AND chat_id=?), ?, ?);
        ''', (chat_id, user_id, dtm))
    cur.execute('''
        DELETE FROM Revoked
        WHERE event_id = (SELECT event_id FROM Events WHERE status = "Open" AND chat_id=?) and user_id = ?;
        ''', (chat_id, user_id,))
    conn.commit()
    conn.close()


def revoke_application_for_the_event(chat_id: int, user_id: int):
    logger.info(f"Event - Player canceled request: {user_id}")
    conn = reconnect()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = 1;")
    dtm = datetime.datetime.now()
    cur.execute('''
        INSERT or REPLACE into
        Revoked (event_id, user_id, operation_datetime)
        values ((SELECT event_id FROM Events WHERE status = "Open" AND chat_id=?), ?, ?);
        ''', (chat_id, user_id, dtm))
    cur.execute('''
        DELETE FROM Participants
        WHERE event_id = (SELECT event_id FROM Events WHERE status = "Open" AND chat_id=?) and user_id = ?;
        ''', (chat_id, user_id,))
    conn.commit()
    conn.close()



def get_chat_user_rp(chat_id, user_id: int) -> Tuple[int, int]:
    """Get numbers of registrations and penalties for user in chat"""
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''
        SELECT COUNT(*)
        FROM Participants
        WHERE event_id in
        (SELECT event_id FROM Events WHERE status = "Fixed" and chat_id = ?)
        AND
        user_id = ?
        ;''', (chat_id, user_id))
    rows = cur.fetchall()
    chat_games = rows[0][0]
    cur.execute('SELECT COUNT(*) FROM Penalties  WHERE chat_id =? AND user_id = ?;', (chat_id, user_id))
    rows = cur.fetchall()
    chat_penalties = rows[0][0]
    return (chat_games, chat_penalties)


def get_user_cancellation_datetime(chat_id, canceled_user_id: int) -> str:
    conn = reconnect()
    cur = conn.cursor()
    cur.execute('''
        SELECT operation_datetime
        FROM Revoked
        WHERE event_id =
        (SELECT event_id FROM Events WHERE status = "Open"  AND chat_id = ?)
        AND user_id = ?;''', (chat_id, canceled_user_id))
    row = cur.fetchone()
    if not row:
        logger.error(f'Strange situation for chat_id = {chat_id} and canceled_user_id = {canceled_user_id}')
        return 'DATETIME NOT FOUND'
    return row[0]


if __name__ == '__main__':
    try:
        print(f'Creating database {DB_FILENAME}...')
        with open(DB_FILENAME, 'wb') as f:
            f.close()
    except Exception as e:
        print(f'Error: {e}')
        sys.exit()
    print(f'Creating tables in database {DB_FILENAME}...')
    create_table_users()
    create_table_chats()
    create_table_events()
    create_table_participants()
    create_table_revoked()
    create_table_chat_penalties()
    print('Done.')
