# -*- coding: utf-8 -*-
"""This module works with sqlite3 database with 3 tables: Users, Chats, Events
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
    # return sqlite3.connect(DB_FILENAME, check_same_thread = False, isolation_level=None)
    conn = sqlite3.connect(DB_FILENAME)
    # Enable foreign key constraints
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


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
    """Close all open events for a chat with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''UPDATE Events SET status = 'Closed' WHERE chat_id = ? AND status = 'Open';''', (chat_id,))
    except sqlite3.Error as e:
        logger.error(f"Error in close_all_open_events_for_chat: {e}")
        raise
    finally:
        conn.close()


def event_add(chat_id: int, text: str, dtm: datetime.datetime, players_limit: int, latest_bot_message_id: int, latest_bot_message_text: str):
    """Add a new event with proper SQL parameterization"""
    if not isinstance(chat_id, int) or not isinstance(players_limit, int) or not isinstance(latest_bot_message_id, int):
        raise ValueError("Invalid parameter types")
        
    event_datetime = str(dtm) if dtm else ''
    conn = reconnect()
    try:
        with conn:
            cur = conn.cursor()
            # Insert new event
            cur.execute('''
                INSERT INTO Events (chat_id, description, datetime, players_limit)
                VALUES (?, ?, ?, ?);
            ''', (chat_id, text, event_datetime, players_limit))
            
            # Update chat info
            conn.execute('''
                UPDATE Chats 
                SET latest_event_id = ?, 
                    latest_bot_message_id = ?, 
                    latest_bot_message_text = ?
                WHERE chat_id = ?;
            ''', (cur.lastrowid, latest_bot_message_id, latest_bot_message_text, chat_id))
    except sqlite3.Error as e:
        logger.error(f"Error in event_add: {e}")
        raise
    finally:
        conn.close()



@logger.catch
def update_event_text(chat_id, new_text):
    """Update event text with proper SQL parameterization"""
    if not isinstance(chat_id, int) or not isinstance(new_text, str):
        raise ValueError("Invalid parameter types")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''
                UPDATE Events 
                SET description = ?
                WHERE status = 'Open' AND chat_id = ?;
            ''', (new_text, chat_id))
    except sqlite3.Error as e:
        logger.error(f"Error in update_event_text: {e}")
        raise
    finally:
        conn.close()


@logger.catch
def get_event_text(chat_id: int) -> str:
    """Get event text with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT description 
            FROM Events 
            WHERE STATUS = 'Open' AND chat_id = ?;
        ''', (chat_id,))
        row = cur.fetchone()
        return row[0] if row else ''
    except sqlite3.Error as e:
        logger.error(f"Error in get_event_text: {e}")
        return ''
    finally:
        conn.close()


@logger.catch
def set_players_limit(chat_id: int, players_limit: int):
    """Set players limit with proper SQL parameterization"""
    if not isinstance(chat_id, int) or not isinstance(players_limit, int):
        raise ValueError("chat_id and players_limit must be integers")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''
                UPDATE Events 
                SET players_limit = ?
                WHERE status = 'Open' AND chat_id = ?;
            ''', (players_limit, chat_id))
    except sqlite3.Error as e:
        logger.error(f"Error in set_players_limit: {e}")
        raise
    finally:
        conn.close()



@logger.catch
def get_event_limit(chat_id: int) -> int:
    """Get event player limit with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT players_limit 
            FROM Events 
            WHERE status = 'Open' AND chat_id = ?;
        ''', (chat_id,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_event_limit: {e}")
        return 0
    finally:
        conn.close()


@logger.catch
def set_event_datetime(chat_id: int, dtm: datetime.datetime):
    """Set event datetime with proper SQL parameterization"""
    if not isinstance(chat_id, int) or not isinstance(dtm, datetime.datetime):
        raise ValueError("Invalid parameter types")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''
                UPDATE Events 
                SET datetime = ?
                WHERE status = 'Open' AND chat_id = ?;
            ''', (dtm, chat_id))
    except sqlite3.Error as e:
        logger.error(f"Error in set_event_datetime: {e}")
        raise
    finally:
        conn.close()


@logger.catch
def get_event_datetime(chat_id: int) -> str:
    """Get event datetime with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT datetime FROM Events WHERE status="Open" AND chat_id = ? ;''', (chat_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else ''
    except sqlite3.Error as e:
        logger.error(f"Error in get_event_datetime: {e}")
        return ''
    finally:
        conn.close()


@logger.catch
def fix_event(chat_id: int):
    """Close all open events for a chat with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''UPDATE Events SET status = 'Fixed' WHERE status = 'Open' AND chat_id = ? ;''', (chat_id,))
    except sqlite3.Error as e:
        logger.error(f"Error in fix_event: {e}")
        raise
    finally:
        conn.close()


@logger.catch
def get_latest_bot_message_id(chat_id: int) -> int:
    """Get latest bot message ID with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT latest_bot_message_id FROM Chats WHERE chat_id = ? ;''', (chat_id,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_latest_bot_message_id: {e}")
        return 0
    finally:
        conn.close()


@logger.catch
def get_latest_bot_message_text(chat_id: int) -> str:
    """Get latest bot message text with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT latest_bot_message_text FROM Chats WHERE chat_id = ? ;''', (chat_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else ''
    except sqlite3.Error as e:
        logger.error(f"Error in get_latest_bot_message_text: {e}")
        return ''
    finally:
        conn.close()


@logger.catch
def save_latest_bot_message(chat_id: int, message_id: int, message_text: str):
    """Save latest bot message with proper SQL parameterization"""
    if not all(isinstance(x, int) for x in (chat_id, message_id)) or not isinstance(message_text, str):
        raise ValueError("Invalid parameter types")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''UPDATE Chats SET latest_bot_message_id = ?, latest_bot_message_text = ? WHERE chat_id = ?;''', (message_id, message_text, chat_id))
    except sqlite3.Error as e:
        logger.error(f"Error in save_latest_bot_message: {e}")
        raise
    finally:
        conn.close()


@logger.catch
def add_or_update_user(user_id: int, first_name: str = "", last_name: str = "", username: str = "") -> None:
    """Adds or updates user data in the database.
    
    Args:
        user_id: User's Telegram ID
        first_name: User's first name
        last_name: User's last name
        username: User's Telegram username (without @)
    """
    # Input validation
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive integer")
    if not all(isinstance(x, str) for x in (first_name, last_name, username)):
        raise TypeError("first_name, last_name and username must be strings")
    
    # Clean input data
    first_name = first_name or ""
    last_name = last_name or ""
    username = username or ""
    
    conn = None
    try:
        conn = reconnect()
        with conn:
            # Check if user exists
            cur = conn.cursor()
            cur.execute('''
                SELECT first_name, last_name, username 
                FROM Users 
                WHERE user_id = ?;
            ''', (user_id,))
            row = cur.fetchone()
            
            if row is None:
                # Add new user
                logger.debug(f'Adding new user: {user_id}')
                conn.execute('''
                    INSERT INTO Users(user_id, first_name, last_name, username) 
                    VALUES (?, ?, ?, ?);
                ''', (user_id, first_name, last_name, username))
            else:
                # Update existing user if data has changed
                current_first, current_last, current_username = row
                if (first_name, last_name, username) != (current_first, current_last, current_username):
                    logger.debug(f'Updating user data: {user_id}')
                    conn.execute('''
                        UPDATE Users 
                        SET first_name = ?, last_name = ?, username = ? 
                        WHERE user_id = ?;
                    ''', (first_name, last_name, username, user_id))
                else:
                    logger.debug(f'User {user_id} data has not changed')
                    
    except sqlite3.Error as e:
        logger.error(f"Database error while updating user {user_id}: {e}")
        raise
    finally:
        if conn:
            conn.close()


@logger.catch
def compose_full_name(user_id: int) -> str:
    """Compose user's full name with proper SQL parameterization"""
    if not isinstance(user_id, int):
        raise ValueError("user_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT first_name, last_name, username 
            FROM users 
            WHERE user_id = ?;
        ''', (user_id,))
        row = cur.fetchone()
        if not row:
            return 'USER_ID NOT FOUND!'
            
        fnm = row[0] if row[0] else ''
        lnm = row[1] if row[1] else ''
        unm = row[2] if row[2] else ''
        
        res = " ".join([fnm, lnm]).strip()
        if res and unm:
            res = f"{res} ({unm})"
        elif not res and unm:
            res = unm
            
        return res if res else str(user_id)
    except sqlite3.Error as e:
        logger.error(f"Error in compose_full_name: {e}")
        return str(user_id)
    finally:
        conn.close()


def penalty_for_user_in_chat(chat_id: int, user_id: int, operator_id: int):
    """Add penalty for user in chat with proper SQL parameterization"""
    if not all(isinstance(x, int) for x in (chat_id, user_id, operator_id)):
        raise ValueError("All IDs must be integers")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''
                INSERT INTO Penalties(chat_id, user_id, operation_datetime, operator_id) 
                VALUES (?, ?, ?, ?);
            ''', (chat_id, user_id, datetime.datetime.now(), operator_id))
    except sqlite3.Error as e:
        logger.error(f"Error in penalty_for_user_in_chat: {e}")
        raise
    finally:
        conn.close()


@logger.catch
def get_all_userids() -> List[int]:
    """Get all user IDs with proper error handling"""
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT user_id FROM Users;''')
        return [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_all_userids: {e}")
        return []
    finally:
        conn.close()


@logger.catch
def get_all_chat_ids() -> Set[int]:
    """Get all chat IDs with proper error handling"""
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT chat_id FROM Chats;''')
        return {int(row[0]) for row in cur.fetchall() if row and row[0] is not None}
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_all_chat_ids: {e}")
        return set()
    finally:
        conn.close()


@logger.catch
def register_new_chat_id(chat_id: int, lang: str):
    """Register new chat ID with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    language_code = lang if lang else ''  # Telegram API language_code. Example: 'en'
    conn = reconnect()
    try:
        with conn:
            conn.execute('''
                INSERT INTO Chats(chat_id, lang) 
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE 
                SET lang = excluded.lang;
            ''', (chat_id, language_code))
    except sqlite3.Error as e:
        logger.error(f"Error in register_new_chat_id: {e}")
        raise
    finally:
        conn.close()


@logger.catch
def get_only_chat_participants(chat_id: int) -> List[int]:
    """Get all participants for a chat with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT DISTINCT user_id
            FROM Participants
            WHERE event_id IN 
            (SELECT event_id FROM Events WHERE chat_id = ?);
        ''', (chat_id,))
        return [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_only_chat_participants: {e}")
        return []
    finally:
        conn.close()


@logger.catch
def get_chat_lang(chat_id: int) -> str:
    """Get chat language with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT lang 
            FROM Chats 
            WHERE chat_id = ?;
        ''', (chat_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            logger.info(f'Can not get LANG for this chat_id: {chat_id}')
            return 'en'
        return row[0]
    except sqlite3.Error as e:
        logger.error(f"Error in get_chat_lang: {e}")
        return 'en'
    finally:
        conn.close()


@logger.catch
def set_chat_lang(chat_id: int, lang: str):
    """Set chat language with proper SQL parameterization"""
    if not isinstance(chat_id, int) or not isinstance(lang, str):
        raise ValueError("Invalid parameter types")
        
    conn = reconnect()
    try:
        with conn:
            conn.execute('''
                UPDATE Chats 
                SET lang = ? 
                WHERE chat_id = ?;
            ''', (lang, chat_id))
    except sqlite3.Error as e:
        logger.error(f"Error in set_chat_lang: {e}")
        raise
    finally:
        conn.close()


def get_event_users(chat_id: int) -> List[int]:
    """Get users for an event with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT user_id 
            FROM Participants 
            WHERE event_id IN 
                (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?) 
            ORDER BY operation_datetime;
        ''', (chat_id,))
        return [row[0] for row in cur.fetchall() if row and row[0] is not None]
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_event_users: {e}")
        return []
    finally:
        conn.close()

def get_event_revoked_users(chat_id: int) -> List[int]:
    """Get revoked users for an event with proper SQL parameterization"""
    if not isinstance(chat_id, int):
        raise ValueError("chat_id must be an integer")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT user_id 
            FROM Revoked 
            WHERE event_id IN 
                (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?) 
            ORDER BY operation_datetime;
        ''', (chat_id,))
        return [row[0] for row in cur.fetchall() if row and row[0] is not None]
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_event_revoked_users: {e}")
        return []
    finally:
        conn.close()


def apply_for_participation_in_the_event(chat_id: int, user_id: int):
    """Apply for participation in an event with proper SQL parameterization"""
    if not all(isinstance(x, int) for x in (chat_id, user_id)):
        raise ValueError("chat_id and user_id must be integers")
        
    logger.info(f"Event - New player request: {user_id}")
    conn = reconnect()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys = 1;")
            dtm = datetime.datetime.now()
            
            # Insert or replace participation
            cur.execute('''
                INSERT OR REPLACE INTO Participants (event_id, user_id, operation_datetime)
                VALUES (
                    (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?), 
                    ?, 
                    ?
                );
            ''', (chat_id, user_id, dtm))
            
            # Remove from revoked if exists
            cur.execute('''
                DELETE FROM Revoked
                WHERE event_id = (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?) 
                AND user_id = ?;
            ''', (chat_id, user_id))
    except sqlite3.Error as e:
        logger.error(f"Error in apply_for_participation_in_the_event: {e}")
        raise
    finally:
        conn.close()


def revoke_application_for_the_event(chat_id: int, user_id: int):
    """Revoke application for an event with proper SQL parameterization"""
    if not all(isinstance(x, int) for x in (chat_id, user_id)):
        raise ValueError("chat_id and user_id must be integers")
        
    logger.info(f"Event - Player canceled request: {user_id}")
    conn = reconnect()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys = 1;")
            dtm = datetime.datetime.now()
            
            # Add to revoked
            cur.execute('''
                INSERT OR REPLACE INTO Revoked (event_id, user_id, operation_datetime)
                VALUES (
                    (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?), 
                    ?, 
                    ?
                );
            ''', (chat_id, user_id, dtm))
            
            # Remove from participants
            cur.execute('''
                DELETE FROM Participants
                WHERE event_id = (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?) 
                AND user_id = ?;
            ''', (chat_id, user_id))
    except sqlite3.Error as e:
        logger.error(f"Error in revoke_application_for_the_event: {e}")
        raise


def get_chat_user_rp(chat_id: int, user_id: int) -> Tuple[int, int]:
    """Get numbers of registrations and penalties for user in chat with proper SQL parameterization"""
    if not all(isinstance(x, int) for x in (chat_id, user_id)):
        raise ValueError("chat_id and user_id must be integers")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        
        # Get registration count
        cur.execute('''
            SELECT COUNT(*) 
            FROM Participants 
            WHERE event_id IN (SELECT event_id FROM Events WHERE chat_id = ?) 
            AND user_id = ?;
        ''', (chat_id, user_id))
        reg_count = cur.fetchone()[0] or 0
        
        # Get penalty count
        cur.execute('''
            SELECT COUNT(*) 
            FROM Penalties 
            WHERE chat_id = ? 
            AND user_id = ?;
        ''', (chat_id, user_id))
        pen_count = cur.fetchone()[0] or 0
        
        return (int(reg_count), int(pen_count))
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error in get_chat_user_rp: {e}")
        return (0, 0)
    finally:
        conn.close()


def get_user_cancellation_datetime(chat_id: int, canceled_user_id: int) -> Optional[datetime.datetime]:
    """Get user's last cancellation datetime with proper SQL parameterization"""
    if not all(isinstance(x, int) for x in (chat_id, canceled_user_id)):
        raise ValueError("chat_id and canceled_user_id must be integers")
        
    conn = reconnect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT operation_datetime 
            FROM Revoked
            WHERE event_id = (SELECT event_id FROM Events WHERE status = 'Open' AND chat_id = ?) 
            AND user_id = ?;
        ''', (chat_id, canceled_user_id))
        row = cur.fetchone()
        if not row or not row[0]:
            logger.info(f'No cancellation found for user {canceled_user_id} in chat {chat_id}')
            return None
        return row[0]
    except sqlite3.Error as e:
        logger.error(f"Error in get_user_cancellation_datetime: {e}")
        return None
    finally:
        conn.close()


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
