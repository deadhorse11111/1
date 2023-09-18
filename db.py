import sqlite3

connection = sqlite3.connect('db.db')
c = connection.cursor()
print("База данных подключена")

def get_sources(mod_id):
    return c.execute("SELECT id, active FROM sources WHERE mod_id = ?", (mod_id,)).fetchall()

def get_sources_ids(mod_id):
    res = c.execute("SELECT id FROM sources WHERE mod_id = ?", (mod_id,)).fetchall()
    res = [i[0] for i in res]
    return res
    
def add_source(mod_id, id):
    try:
        res = c.execute("SELECT id FROM sources WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchall()
        if not bool(len(res)):
            c.execute("INSERT INTO sources (mod_id, id, active, allow_links, remove_links, media_mode, moderation) VALUES (?,?,?,?,?,?,?)", (mod_id, id, 1, 1, 2, 2, 1))
            print("Добавлен источник: ", id)
            connection.commit()
            return True
    except Exception as e:
        return False
        
def remove_source(mod_id, id):
    try:
        res = c.execute("SELECT id FROM sources WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchall()
        if bool(len(res)):
            c.execute("DELETE FROM sources WHERE mod_id = ? AND id = ?", (mod_id, id))
            print("Удалён источник: ", id)
            connection.commit()
            return True
    except Exception as e:
        return False
        
def add_source_tag(mod_id, id, tag):
    try:
        res = c.execute("SELECT id FROM source_tags WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchall()
        if not bool(len(res)):
            c.execute("INSERT INTO source_tags (mod_id, id, tag) VALUES (?,?,?)", (mod_id, id, tag))
            connection.commit()
            return True
    except Exception as e:
        return False
        
def remove_source_tag(mod_id, id):
    try:
        res = c.execute("SELECT id FROM source_tags WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchall()
        if bool(len(res)):
            c.execute("DELETE FROM source_tags WHERE mod_id = ? AND id = ?", (mod_id, id))
            connection.commit()
            return True
    except Exception as e:
        return False
        
def get_source_tag(mod_id, id):
    return c.execute("SELECT tag FROM source_tags WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchone()[0]
    
def set_source_name(mod_id, id, name):
    c.execute("UPDATE source_tags SET name = ? WHERE mod_id = ? AND id = ?", (name, mod_id, id))
    connection.commit()
    
def get_source_name(mod_id=None, id=None, tag=None):
    if tag == None:
        return c.execute("SELECT name FROM source_tags WHERE id = ? AND mod_id = ?", (id, mod_id)).fetchone()[0]
    elif id == None:
        return c.execute("SELECT name FROM source_tags WHERE tag = ? AND mod_id = ?", (tag, mod_id)).fetchone()[0]
        
def get_source_config(mod_id, id):
    res = c.execute("SELECT active, allow_links, remove_links, media_mode, moderation FROM sources WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchone()
    return {'active': res[0], 'allow_links': res[1], 'remove_links': res[2], 'media_mode': res[3], 'moderation': res[4]}
    
def set_source_active(mod_id, id, v):
    c.execute("UPDATE sources SET active = ? WHERE mod_id = ? AND id = ?", (v, mod_id, id))
    connection.commit()

def set_source_moderation(mod_id, id, v):
    c.execute("UPDATE sources SET moderation = ? WHERE mod_id = ? AND id = ?", (v, mod_id, id))
    connection.commit()
        
def set_source_allow_links(mod_id, id, v):
    c.execute("UPDATE sources SET allow_links = ? WHERE mod_id = ? AND id = ?", (v, mod_id, id))
    connection.commit()
        
def set_source_remove_links(mod_id, id, v):
    c.execute("UPDATE sources SET remove_links = ? WHERE mod_id = ? AND id = ?", (v, mod_id, id))
    connection.commit()
        
def add_source_remove_link(mod_id, id, links):
    try:
        for link in links.split('\n'):
            c.execute("INSERT INTO remove_links (mod_id, source_id, link) VALUES (?,?,?)", (mod_id, id, link))
        connection.commit()
        return True
    except Exception as e:
        return False
        
def remove_source_remove_link(mod_id, id, link):
    try:
        c.execute("DELETE FROM remove_links WHERE mod_id = ? AND source_id = ? AND link = ?", (mod_id, id, link))
        connection.commit()
        return True
    except Exception as e:
        return False
        
def get_source_remove_links(mod_id, id):
    res = c.execute("SELECT link FROM remove_links WHERE mod_id = ? AND source_id = ?", (mod_id, id)).fetchall()
    res = [i[0] for i in res]
    return res
        
def set_source_media_mode(mod_id, id, v):
    try:
        c.execute("UPDATE sources SET media_mode = ? WHERE mod_id = ? AND id = ?", (v, mod_id, id))
        connection.commit()
        return True
    except Exception as e:
        return False

def mod_count():
    return c.execute("SELECT COUNT(*) FROM moderators").fetchone()[0]

def user_exists(user_id):
    try:
        return len(c.execute("SELECT * FROM moderators WHERE user_id = ?", (user_id,)).fetchall())
    except Exception as e:
        return False
        
def set_mod_channel(mod_id, channel):
    c.execute("UPDATE moderators SET channel = ? WHERE user_id = ?", (channel, mod_id))
    connection.commit()
    
def get_mod_channels():
    res = c.execute("SELECT user_id, channel FROM moderators").fetchall()
    return res

def add_mod_channel_tag(mod_id, id, tag):
    try:
        res = c.execute("SELECT id FROM channel_tags WHERE mod_id = ?", (mod_id,)).fetchall()
        if not bool(len(res)):
            c.execute("INSERT INTO channel_tags (mod_id, id, tag) VALUES (?,?,?)", (mod_id, id, tag))
            connection.commit()
            return True
    except Exception as e:
        return False
        
def remove_mod_channel_tag(mod_id):
    try:
        res = c.execute("SELECT id FROM channel_tags WHERE mod_id = ?", (mod_id,)).fetchall()
        if bool(len(res)):
            c.execute("DELETE FROM channel_tags WHERE mod_id = ?", (mod_id,))
            connection.commit()
            return True
    except Exception as e:
        return False
        
def get_mod_channel_tag(mod_id):
    return c.execute("SELECT tag FROM channel_tags WHERE mod_id = ?", (mod_id,)).fetchone()[0]
    
def set_mod_channel_name(mod_id, name):
    c.execute("UPDATE channel_tags SET name = ? WHERE mod_id = ?", (name, mod_id))
    connection.commit()
    
def get_mod_channel_name(mod_id):
    return c.execute("SELECT name FROM channel_tags WHERE mod_id = ?", (mod_id,)).fetchone()[0]
        
def add_mod(user_id):
    try:
        res = c.execute("SELECT user_id FROM moderators WHERE user_id=?", (user_id,)).fetchall()
        if not bool(len(res)):
            c.execute("INSERT INTO moderators (user_id, state) VALUES (?, ?)", (user_id, 'start'))
            c.execute("INSERT INTO config (mod_id) VALUES (?)", (user_id,))
            print("Добавлен модератор: ", user_id)
            connection.commit()
            return True
    except Exception as e:
        print(e)
        return False
        
def remove_mod(user_id):
    try:
        res = c.execute("SELECT user_id FROM moderators WHERE user_id=?", (user_id,)).fetchall()
        if bool(len(res)):
            c.execute("DELETE FROM moderators WHERE user_id=?", (user_id,))
            print("Удалён модератор: ", user_id)
            connection.commit()
            return True
    except Exception as e:
        return False
        
def get_mods():
    res = c.execute("SELECT user_id FROM moderators").fetchall()
    res = [i[0] for i in res]
    return res
    
def set_mod_tag(user_id, tag):
    c.execute("UPDATE moderators SET tag = ? WHERE user_id = ?", (tag, user_id))
    connection.commit()
    
def get_mod_tag(user_id):
    return c.execute("SELECT tag FROM moderators WHERE user_id = ?", (user_id,)).fetchone()[0]
    
def get_user_state(user_id):
    return c.execute("SELECT state FROM moderators WHERE user_id=?", (user_id,)).fetchone()[0]

def set_user_prev_state(user_id, state):
    c.execute("UPDATE moderators SET prev_state=? WHERE user_id=?", (state, user_id))
    connection.commit()

def get_user_prev_state(user_id):
    return c.execute("SELECT prev_state FROM moderators WHERE user_id=?", (user_id,)).fetchone()[0]
    
def set_user_state(user_id, state):
    c.execute("UPDATE moderators SET state=? WHERE user_id=?", (state, user_id))
    connection.commit()
    
def set_user_prev_action(user_id, action):
    c.execute("UPDATE moderators SET prev_action=? WHERE user_id=?", (action, user_id))
    connection.commit()
    
def get_user_prev_action(user_id):
    return c.execute("SELECT prev_action FROM moderators WHERE user_id=?", (user_id,)).fetchone()[0]

def add_stop(mod_id, word):
    c.execute("INSERT INTO stops (mod_id, word) VALUES (?,?)", (mod_id, word))
    connection.commit()

def remove_stop(mod_id, id):
    try:
        res = c.execute("SELECT word FROM stops WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchall()
        if bool(len(res)):
            c.execute("DELETE FROM stops WHERE mod_id = ? AND id = ?", (mod_id, id))
            connection.commit()
            return True
    except:
        return False

def get_stops(mod_id):
    return c.execute("SELECT id, word FROM stops WHERE mod_id = ?", (mod_id,)).fetchall()

def add_filter_word(mod_id, text, replacement):
    try:
        c.execute("INSERT INTO filter_words (mod_id, word, replacement) VALUES (?,?,?)", (mod_id, text, replacement))
        connection.commit()
        return True
    except Exception as e:
        return False
        
def remove_filter_word(mod_id, id):
    try:
        res = c.execute("SELECT word FROM filter_words WHERE mod_id = ? AND id = ?", (mod_id, id)).fetchall()
        if bool(len(res)):
            c.execute("DELETE FROM filter_words WHERE mod_id = ? AND id = ?", (mod_id, id))
            print("Удалён фильтр: ", id)
            connection.commit()
            return True
    except Exception as e:
        return False
        
def get_filter_words(mod_id):
    return c.execute("SELECT id, word, replacement FROM filter_words WHERE mod_id = ?", (mod_id,)).fetchall()
    
def set_prefix(mod_id, prefix):
    c.execute("UPDATE config SET prefix = ? WHERE mod_id = ?", (prefix, mod_id))
    connection.commit()
    
def get_prefix(mod_id):
    return c.execute("SELECT prefix FROM config WHERE mod_id = ?", (mod_id,)).fetchone()[0]
    
def set_postfix(mod_id, postfix):
    c.execute("UPDATE config SET postfix = ? WHERE mod_id = ?", (postfix, mod_id))
    connection.commit()
    
def get_postfix(mod_id):
    return c.execute("SELECT postfix FROM config WHERE mod_id = ?", (mod_id,)).fetchone()[0]
    
def set_watermark(mod_id, watermark, type):
    c.execute("UPDATE config SET watermark = ?, watermark_type = ? WHERE mod_id = ?", (watermark, type, mod_id))
    connection.commit()
    
def get_watermark(mod_id):
    res = c.execute("SELECT watermark, watermark_type FROM config WHERE mod_id = ?", (mod_id,)).fetchone()
    return {'watermark': res[0], 'type': res[1]}
    
def set_watermark_opacity(mod_id, opacity):
    c.execute("UPDATE config SET watermark_opacity = ? WHERE mod_id = ?", (opacity, mod_id))
    connection.commit()
    
def get_watermark_opacity(mod_id):
    return c.execute("SELECT watermark_opacity FROM config WHERE mod_id = ?", (mod_id,)).fetchone()[0]
    
def set_watermark_font_size(mod_id, size):
    c.execute("UPDATE config SET watermark_font_size = ? WHERE mod_id = ?", (size, mod_id))
    connection.commit()
   
def get_watermark_font_size(mod_id):
    return c.execute("SELECT watermark_font_size FROM config WHERE mod_id = ?", (mod_id,)).fetchone()[0]
    
def set_watermark_font_color(mod_id, color):
    c.execute("UPDATE config SET watermark_font_color = ? WHERE mod_id = ?", (color, mod_id))
    connection.commit()
    
def get_watermark_font_color(mod_id):
    return c.execute("SELECT watermark_font_color FROM config WHERE mod_id = ?", (mod_id,)).fetchone()[0]

def add_no_download_message(mod_id, path, client_id, bot_id):
    c.execute("INSERT INTO no_download_messages (mod_id, path, client_id, bot_id) VALUES (?,?,?,?)", (mod_id, path, client_id, bot_id))
    connection.commit()

def remove_no_download_message(mod_id, path):
    c.execute("DELETE FROM no_download_messages WHERE mod_id = ? and path = ?", (mod_id, path))
    connection.commit()

def get_no_download_messages(mod_id):
    res = c.execute("SELECT path, client_id, bot_id FROM no_download_messages WHERE mod_id = ?", (mod_id,))
    res = [{'path': x[0], 'client_id': x[1], 'bot_id': x[2]} for x in res]
    return res

def set_no_download_message_bot_id(path, bot_id):
    try:
        res = c.execute("SELECT client_id FROM no_download_messages WHERE path = ?", (path,))
        res = [x[0] for x in res]
        for i, client_id in enumerate(res):
            c.execute("UPDATE no_download_messages SET bot_id = ? WHERE path = ? AND client_id = ?", (bot_id[i], path, client_id))
    except Exception as e:
        print(e)
    connection.commit()