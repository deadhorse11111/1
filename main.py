from telethon import TelegramClient, events, utils, errors
from telethon.tl import types
from telethon.tl.types import *
import telethon.tl.functions.channels as channelsFunc
import telethon.tl.functions.messages as messagesFunc
import asyncio, re, os, json, shutil, copy
from collections import deque
from datetime import datetime
from buttons import *
from db import *
from watermark import *
from config import *

mod_channels = {}
mod_waiting_messages = {}
mod_main_id = {}
channels = {}

moderating = {}
mb_modBuffer = {}
mb_clientBuffer = {}
mb_addTasks = {}

noDownloadBuffer = {}
noDownloadCond = asyncio.Condition()

filterConfigText = ''

for channel in get_mod_channels():
    if channel[1]:
        mod_channels[int(channel[0])] = int(channel[1])
    
for mod in get_mods():
    for i in get_sources_ids(mod):
        if int(i) in channels: channels[int(i)] += 1
        else: channels[int(i)] = 1
    mod_waiting_messages[mod] = len(os.listdir('./posts/waiting/'+get_mod_tag(mod)))
    mb_addTasks[mod] = deque()        
        
bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)
client = TelegramClient('myGrab', api_id, api_hash, sequential_updates=True)   
def parseSources(mod_id):
    active = []
    inactive = []
    for i in get_sources(mod_id):
        if bool(i[1]): active += [get_source_name(mod_id, id=i[0])]
        else: inactive += [get_source_name(mod_id, id=i[0])]
    msg = "🌕Активные:\n"
    for i in active:
        msg += f"{i}\n"
    msg += "\n🌑Неактивные:\n"
    for i in inactive:
        msg += f"{i}\n"
    return msg

def parseSourceRemoveLinks(mod_id, source_id):
    links = get_source_remove_links(mod_id, source_id)
    msg = ""
    if len(links) == 0:
        msg += "\n\nНет указанных ссылок\n"
    else:
        msg += "\n\nУказанные ссылки:\n"
        for link in links:
            msg += f"{link}\n"
    return msg
    
async def parseWatermark(mod_id):
    wm = get_watermark(mod_id)
    if len(wm['type']) == 0:
        return {'msg': "\n\n Водяной знак не установлен", 'image': None}
    elif wm['type'] == 'text':
        return {'msg': "\n\n Водяной знак:\n" + wm['watermark'], 'image': None}
    else:
        img = await bot.upload_file('./watermark/'+str(mod_id)+'/watermark.png')
        return {'msg': "", 'image': img}
           
def messageFromJson(string):
    dict = json.loads(string)
    dict.pop('_')
    dict['peer_id'] = types.PeerChannel(dict['peer_id']['channel_id'])
    dict['date'] = datetime.fromisoformat(dict['date'])
    if dict['entities']:
        for i, entity in enumerate(dict['entities']):
            entity = globals()[entity['_']](**{x: entity[x] for x in entity if x != '_'})
            if isinstance(entity, types.InputMessageEntityMentionName):
                entity.user_id = globals()[entity.user_id['_']](**{x: entity.user_id[x] for x in entity.user_id if x != '_'})
            dict['entities'][i] = entity
    if dict['reply_markup']:
        rows = []
        for row in dict['reply_markup']['rows']:
            buttons = []
            for button in row['buttons']:
                buttons += [globals()[button['_']](**{x: button[x] for x in button if x != '_'})]
            rows += [globals()[row['_']](buttons)]
        markup = globals()[dict['reply_markup']['_']](rows)
        dict['reply_markup'] = markup
    if dict['media'] and dict['media']['_'] == 'MessageMediaWebPage':
        dict['media'] = {}
    message = types.Message(**dict)
    return message  
    
async def modGetMessage(mod_id):
    if noDownloadCond.locked():
        await noDownloadCond.acquire()
        noDownloadCond.release()
    modDir = get_mod_tag(mod_id)
    dir = os.listdir('./posts/waiting/'+modDir)
    if not dir: 
        return None
    else:
        if not mod_id in mb_modBuffer or not mb_modBuffer[mod_id]: 
            dir.sort(reverse=True)
        else:
            dir.sort()
        index = mod_waiting_messages[mod_id]-1
        with open('./posts/waiting/'+modDir+'/'+dir[index]+'/message.json') as f:
            res = {'dir': dir[index], 'filepaths': []}
            msg = messageFromJson(f.read())
            if msg.message:
                msg.message = (await client.send_message(await client.get_entity('me'), msg.message, formatting_entities=msg.entities)).text
            clmsg = copy.deepcopy(msg)
            fileName = dir[index].split('_', 2)
            date = datetime.strptime(fileName[0], '%Y-%m-%d-%H-%M-%S')
            res['post_info'] = f"\n\n-----------------------\n{fileName[2]}\n{date.strftime('%Y-%m-%d %H:%M:%S')}"
            postDir = os.listdir('./posts/waiting/'+modDir+'/'+dir[index])
            postDir.remove('message.json')
            msg.media = []
            clmsg.media = []
            res['noDownloadKey'] = f"{modDir}/{dir[index]}"
            if postDir:
                postDir.sort()
                for file in postDir:
                    modFile = await bot.upload_file(f'./posts/waiting/{modDir}/{dir[index]}/{file}')
                    msg.media += [utils.get_input_media(modFile, is_photo=utils.is_image(modFile))]
                    res['filepaths'] += [f'./posts/waiting/{modDir}/{dir[index]}/{file}']
            else: 
                msg.entities = None
                clmsg.entities = None
                msg.media = None
                clmsg.media = None
            res['msg'] = msg
            res['clmsg'] = clmsg
            return res
    
async def mb_modAdd(mod_id):
    message = await modGetMessage(mod_id)
    if message:
        if mod_id in mb_modBuffer:
            mb_modBuffer[mod_id].append(message)
        else:
            mb_modBuffer[mod_id] = deque([message])
    return message

async def mb_modGet(mod_id, index=0):
    if mod_waiting_messages[mod_id]:
        if not mod_id in mb_modBuffer or not mb_modBuffer[mod_id]: 
            await mb_modAdd(mod_id)
        if mb_modBuffer[mod_id][index]['noDownloadKey'] in noDownloadBuffer:
            bot_media = []
            client_media = []
            for id in noDownloadBuffer[mb_modBuffer[mod_id][index]['noDownloadKey']]:
                client_msgs = (await client(messagesFunc.GetMessagesRequest([types.InputMessageID(id['client'])]))).messages
                if client_msgs: client_media += [client_msgs[0].media]
                bot_msgs = (await bot(messagesFunc.GetMessagesRequest([types.InputMessageID(id['bot'])]))).messages
                if bot_msgs: bot_media += [bot_msgs[0].media]
            if mb_modBuffer[mod_id][index]['clmsg'].media: mb_modBuffer[mod_id][index]['clmsg'].media += client_media
            elif client_media: mb_modBuffer[mod_id][index]['clmsg'].media = client_media
            if mb_modBuffer[mod_id][index]['msg'].media: mb_modBuffer[mod_id][index]['msg'].media += bot_media
            elif bot_media: mb_modBuffer[mod_id][index]['msg'].media = bot_media
        return mb_modBuffer[mod_id][index]
    else:
        return None

async def mb_clientAdd(mod_id, message):
    if message['filepaths']:
        for path in message['filepaths']:
            file = await client.upload_file(path)
            message['clmsg'].media += [utils.get_input_media(file, is_photo=utils.is_image(file))]
    if mod_id in mb_clientBuffer:
        mb_clientBuffer[mod_id].append(message['clmsg'])
    else:
        mb_clientBuffer[mod_id] = deque([message['clmsg']])

def mb_clientGet(mod_id):   
    return mb_clientBuffer[mod_id].popleft()

async def mb_add(mod_id, moderated):
    if len(mb_addTasks[mod_id]) > 1:
        await mb_addTasks[mod_id][-2]
    mod_waiting_messages[mod_id] += 1 
    message = await mb_modAdd(mod_id)
    if moderated: await mb_clientAdd(mod_id, message)
    if mb_addTasks[mod_id]: mb_addTasks[mod_id].popleft()
    if moderated and get_user_state(mod_id) == 'start' and mod_main_id[mod_id]:
        buttons = startButtons(mod_id)
        buttons[1][0].text = f'Модерация ({mod_waiting_messages[mod_id]})'
        await bot.edit_message(get_mod_tag(mod_id), mod_main_id[mod_id], buttons=buttons)
    return len(mb_modBuffer[mod_id])-1

async def modPassMessage(mod_id, message, filepaths, noDownloadKey, noMod=False):
    if mod_id in mb_clientBuffer and mb_clientBuffer[mod_id] and not noMod:
        msg = mb_clientGet(mod_id)
        if msg.media and len(msg.media) == 1: msg.media = msg.media[0] 
        await client.send_message(mod_channels[mod_id], msg.message, file=msg.media)
    else:
        files = []
        if filepaths:
            for path in filepaths:
                files += [await client.upload_file(path.replace('waiting', 'archived'))]
        if noDownloadKey in noDownloadBuffer:
            for id in noDownloadBuffer[noDownloadKey]:
                client_msgs = (await client(messagesFunc.GetMessagesRequest([types.InputMessageID(id['client'])]))).messages
                if client_msgs: files += [client_msgs[0].media]
            remove_no_download_message(mod_id, noDownloadKey)
        if len(files) == 1: files = files[0]
        elif not files: files = None
        await client.send_message(mod_channels[mod_id], message.message, file=files)
    
def removeRestrictedCharacters(text):
    regrex_pattern = re.compile('[\\/:"*?<>|]+')
    return regrex_pattern.sub(r'', text)
    
async def copyFile(src, dst):
    shutil.copyfile(src, dst)
    
async def mainMenu(mod_id):
    buttons = startButtons(mod_id)
    buttons[1][0].text = f'Модерация ({mod_waiting_messages[mod_id]})'
    msg = await bot.send_message(mod_id, f"🏠**Главная**\n\nВаш канал:\n{get_mod_channel_name(mod_id)}", buttons=buttons)
    mod_main_id[mod_id] = msg.id
    set_user_state(mod_id, 'start')
        
@bot.on(events.NewMessage(incoming=True))
async def bot_handler(event):
    if event.message.grouped_id: return
    mod_id = event.message.peer_id.user_id
    global filterConfigText
    if event.message.message == '/start':
        if not user_exists(mod_id):
            if not add_mod(mod_id):
               await bot.send_message(event.message.peer_id, "Не удалось добавить модератора") 
               return
            clientUsername = '@'+(await client.get_me()).username
            await bot.send_message(event.message.peer_id, f"Отправьте ссылку-приглашение или @юзернейм канала и назначьте {clientUsername} адимнистратором с правом на отправку сообщений")
            set_mod_tag(mod_id, '@'+(await event.get_sender()).username)
            set_user_state(mod_id, 'set_mod_channel')
            mod_waiting_messages[mod_id] = 0
            mb_addTasks[mod_id] = deque()
            os.mkdir('./watermark/'+str(mod_id))
            os.mkdir('./posts/waiting/'+get_mod_tag(mod_id))
            os.mkdir('./posts/archived/'+get_mod_tag(mod_id))
        else:
            await mainMenu(mod_id)
    elif user_exists(mod_id):
        userState = get_user_state(mod_id).split()
        if userState[0] == 'add_mod':
            newModId = await bot.get_peer_id(event.message.message)
            msg = "**Управление модераторами**\n**Добавить модератора**\n\n"
            if not add_mod(newModId):
                msg += "Не удалось добавить модератора\nМодераторы:\n"
                for mod in get_mods():
                    msg += f"{get_mod_tag(mod)}\n"
                await bot.send_message(event.message.peer_id, msg, buttons=modControl+[[back, cancel]])
            else:
                set_mod_tag(newModId, event.message.message)
                set_user_state(newModId, 'start')
                mod_waiting_messages[mod_id] = 0
                mb_addTasks[mod_id] = deque()
                os.mkdir('./watermark/'+str(newModId))
                os.mkdir('./posts/waiting/'+get_mod_tag(newModId))
                os.mkdir('./posts/archived/'+get_mod_tag(newModId))
                msg += "Модератор добавлен\nМодераторы:\n"
                for mod in get_mods():
                    msg += f"{get_mod_tag(mod)}\n"
                await bot.send_message(event.message.peer_id, msg, buttons=modControl+[[back, cancel]])
            set_user_state(mod_id, 'start')
        elif userState[0] == 'add_stop':
            add_stop(mod_id, event.message.message.strip())
            msg = "**Фильтрация слов**\n\nСтоп-слова:\n"
            for i in get_stops(mod_id):
                msg += f"{i[1]}\n"
            msg += "\n\nФильтры:\n"
            for i in get_filter_words(mod_id):
                msg += f"{i[1]} -> {i[2]}\n"
            await bot.send_message(event.message.peer_id, msg, buttons=filterConfig+[[back, cancel]])
            set_user_state(mod_id, 'start')
        elif userState[0] == 'add_filter':
            msg = "**Фильтрация слов**\n**Добавить слова**\n\nВведите текст на замену"
            filterConfigText = event.message.message
            await bot.send_message(event.message.peer_id, msg, buttons=filterNoReplacement+[[cancel]])
            set_user_state(mod_id, 'add_filter_replacement')
        elif userState[0] == 'add_filter_replacement':
            msg = "**Фильтрация слов**\n**Добавить слова**\n\n"
            if not add_filter_word(mod_id, filterConfigText, event.message.message):
                msg += "Не удалось добавить фильтры\nСтоп-слова:\n"
                for i in get_stops(mod_id):
                    msg += f"{i[1]}\n"
                msg += "\n\nФильтры:\n"
                for filter in get_filter_words(mod_id):
                    msg += f"{filter[1]} -> {filter[2]}\n"
                await bot.send_message(event.message.peer_id, msg, buttons=filterConfig+[[back, cancel]])
            else:
                msg += "Фильтры добавлены\nСтоп-слова:\n"
                for i in get_stops(mod_id):
                    msg += f"{i[1]}\n"
                msg += "\n\nФильтры:\n"
                for filter in get_filter_words(mod_id):
                    msg += f"{filter[1]} -> {filter[2]}\n"
                await bot.send_message(event.message.peer_id, msg, buttons=filterConfig+[[back, cancel]])
            set_user_state(mod_id, 'start')
        elif userState[0] == 'add_source':
            msg = "**Управление источниками**\n**Добавить источник**\n\n"
            try:
                if event.message.message.startswith('@'):
                        await client(channelsFunc.JoinChannelRequest(await client.get_input_entity(event.message.message)))
                else:
                        await client(messagesFunc.ImportChatInviteRequest(event.message.message.split('/')[-1]))
                source_id = await client.get_peer_id(event.message.message)
                if not add_source(mod_id, source_id):
                    msg += "Не удалось добавить источник(__ошибка бд__)\n\nИсточники:\n\n"
                    msg += parseSources(mod_id)
                    await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
                else:
                    add_source_tag(mod_id, source_id, event.message.message)
                    if source_id in channels: channels[source_id] += 1
                    else: channels[source_id] = 1
                    name = f"{utils.get_display_name(await client.get_entity(event.message.message))} ({event.message.message})"
                    set_source_name(mod_id, source_id, name)
                    msg += "Источник добавлен\n\nИсточники:\n\n"
                    msg += parseSources(mod_id)
                    await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
            except errors.UserAlreadyParticipantError:
                source_id = await client.get_peer_id(event.message.message)
                if not add_source(mod_id, source_id):
                    msg += "Не удалось добавить источник(__канал уже в бд__)\n\nИсточники:\n\n"
                    msg += parseSources(mod_id)
                    await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
                else:
                    add_source_tag(mod_id, source_id, event.message.message)
                    if source_id in channels: channels[source_id] += 1
                    else: channels[source_id] = 1
                    name = f"{utils.get_display_name(await client.get_entity(event.message.message))} ({event.message.message})"
                    set_source_name(mod_id, source_id, name)
                    msg += "Источник добавлен\n\nИсточники:\n\n"
                    msg += parseSources(mod_id)
                    await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
            except errors.ChannelsTooMuchError:
                msg += "Не удалось добавить источник(__клиент вступил в слишком большое количество каналов__)\n\nИсточники:\n\n"
                msg += parseSources(mod_id)
                await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
            except errors.InviteHashExpiredError:
                msg += "Не удалось добавить источник(__канал не существует или неверная ссылка__)\n\nИсточники:\n\n"
                msg += parseSources(mod_id)
                await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
            except Exception as e:
                print(e)
                msg += "Не удалось добавить источник(__что-то пошло не так__)\n\nИсточники:\n\n"
                msg += parseSources(mod_id)
                await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
            set_user_state(mod_id, 'start')
            set_user_prev_action(mod_id, 'grabber_config')
            client.remove_event_handler(clientMessageHandler)
            client.remove_event_handler(clientAlbumHandler)
            client.add_event_handler(clientMessageHandler, events.NewMessage(chats=list(channels)))
            client.add_event_handler(clientAlbumHandler, events.Album(chats=list(channels)))
        elif userState[0] == 'edit_prefix':
            set_prefix(mod_id, event.message.message)
            await bot.send_message(event.message.peer_id, f"**Настройки граббера**\n\n**Префикс:**\n{get_prefix(mod_id)}\n**Постфикс:**\n{get_postfix(mod_id)}", buttons=grabConfig+[[cancel]])
            set_user_state(mod_id, 'start')
        elif userState[0] == 'edit_postfix':
            set_postfix(mod_id, event.message.message)
            await bot.send_message(event.message.peer_id, f"**Настройки граббера**\n\n**Префикс:**\n{get_prefix(mod_id)}\n**Постфикс:**\n{get_postfix(mod_id)}", buttons=grabConfig+[[cancel]])
            set_user_state(mod_id, 'start')
        elif userState[0] == 'add_source_remove_link':
            add_source_remove_link(mod_id, userState[1], event.message.message)
            msg = f"**Управление источниками**\n**Настроить источник**\n__{get_source_name(mod_id, id=userState[1])}__"
            msg += parseSourceRemoveLinks(mod_id, userState[1])
            await bot.send_message(event.message.peer_id, msg, buttons=sourceEdit(get_source_config(mod_id, userState[1]))+[[back, cancel]])
            set_user_state(mod_id, 'edit_source '+userState[1])
            set_user_prev_action(mod_id, 'edit_source')
            set_user_prev_state(mod_id, 'start')
        elif userState[0] == 'set_source_name':
            set_source_name(mod_id, userState[1], event.message.message)
            msg = f"**Управление источниками**\n**Настроить источник**\n__{get_source_name(mod_id, id=userState[1])}__"
            if get_source_config(mod_id, userState[1])['remove_links'] == 2: 
                msg += parseSourceRemoveLinks(mod_id, userState[1])
            await bot.send_message(event.message.peer_id, msg, buttons=sourceEdit(get_source_config(mod_id, userState[1]))+[[back, cancel]])
            set_user_state(mod_id, 'edit_source '+userState[1])
            set_user_prev_action(mod_id, 'edit_source')
            set_user_prev_state(mod_id, 'start')
        elif userState[0] == 'set_watermark':
            msg = f"**Настройки граббера**\n**Водяной знак**\n\nПрозрачность: {get_watermark_opacity(mod_id)}%"
            if event.message.media != None and type(event.message.media) == types.MessageMediaPhoto or type(event.message.media) == types.MessageMediaDocument:
                await bot.download_media(event.message.media, './watermark/'+str(mod_id)+'/watermark.png')
                set_watermark(mod_id, '', 'image')
            elif event.message.media == None:
                set_watermark(mod_id, event.message.message, 'text')
            if get_watermark(mod_id)['type'] == 'text':
                msg += f"\nРазмер шрифта: {get_watermark_font_size(mod_id)}px"
                msg += f"\nЦвет шрифта: {get_watermark_font_color(mod_id)}"
            wm = await parseWatermark(mod_id)
            msg += wm['msg']
            if event.message.media != None and type(event.message.media) != types.MessageMediaPhoto and type(event.message.media) != types.MessageMediaDocument:
                msg += "\n\n__Неверный формат__"
            await bot.send_message(event.message.peer_id, msg, file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
            set_user_state(mod_id, 'edit_watermark')
            set_user_prev_state(mod_id, 'start')
            set_user_prev_action(mod_id, 'grabber_config')
        elif userState[0] == 'set_watermark_opacity':
            set_watermark_opacity(mod_id, event.message.message)
            msg = f"**Настройки граббера**\n**Водяной знак**\n\nПрозрачность: {get_watermark_opacity(mod_id)}%"
            if get_watermark(mod_id)['type'] == 'text':
                msg += f"\nРазмер шрифта: {get_watermark_font_size(mod_id)}px"
                msg += f"\nЦвет шрифта: {get_watermark_font_color(mod_id)}"
            wm = await parseWatermark(mod_id)
            msg += wm['msg']
            await bot.send_message(event.message.peer_id, msg, file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
            set_user_state(mod_id, 'edit_watermark')
            set_user_prev_state(mod_id, 'start')
            set_user_prev_action(mod_id, 'grabber_config')
        elif userState[0] == 'set_watermark_font_size':
            set_watermark_font_size(mod_id, event.message.message)
            msg = f"**Настройки граббера**\n**Водяной знак**\n\nПрозрачность: {get_watermark_opacity(mod_id)}%"
            msg += f"\nРазмер шрифта: {get_watermark_font_size(mod_id)}px"
            msg += f"\nЦвет шрифта: {get_watermark_font_color(mod_id)}"
            wm = await parseWatermark(mod_id)
            msg += wm['msg']
            await bot.send_message(event.message.peer_id, msg, file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
            set_user_state(mod_id, 'edit_watermark')
            set_user_prev_state(mod_id, 'start')
            set_user_prev_action(mod_id, 'grabber_config')
        elif userState[0] == 'set_watermark_font_color':
            set_watermark_font_color(mod_id, event.message.message)
            msg = f"**Настройки граббера**\n**Водяной знак**\n\nПрозрачность: {get_watermark_opacity(mod_id)}%"
            msg += f"\nРазмер шрифта: {get_watermark_font_size(mod_id)}px"
            msg += f"\nЦвет шрифта: {get_watermark_font_color(mod_id)}"
            wm = await parseWatermark(mod_id)
            msg += wm['msg']
            await bot.send_message(event.message.peer_id, msg, file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
            set_user_state(mod_id, 'edit_watermark')
            set_user_prev_state(mod_id, 'start')
            set_user_prev_action(mod_id, 'grabber_config')
        elif userState[0] == 'set_watermark_font':
            msg = f"**Настройки граббера**\n**Водяной знак**\n\nПрозрачность: {get_watermark_opacity(mod_id)}%"
            msg += f"\nРазмер шрифта: {get_watermark_font_size(mod_id)}px"
            msg += f"\nЦвет шрифта: {get_watermark_font_color(mod_id)}"
            wm = await parseWatermark(mod_id)
            msg += wm['msg']
            if event.message.media != None and type(event.message.media) == types.MessageMediaDocument:
                await bot.download_media(event.message.media, './font.ttf')
                msg += "\n\n__Шрифт загружен__"
            else:
                msg += "\n\n__Неверный формат__"
            await bot.send_message(event.message.peer_id, msg, file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
            set_user_state(mod_id, 'edit_watermark')
            set_user_prev_state(mod_id, 'start')
            set_user_prev_action(mod_id, 'grabber_config')
        elif userState[0] == 'set_mod_channel':
            if event.message.message.startswith('@'):
                try:
                    await client(channelsFunc.JoinChannelRequest(await client.get_input_entity(event.message.message)))
                except errors.ChannelsTooMuchError:
                    msg = "Не удалось добавить канал(__клиент вступил в слишком большое количество каналов__)"
                    await bot.send_message(event.message.peer_id, msg, buttons=sourceConfig+[[back, cancel]])
                except:
                    pass
            else:
                try:
                    await client(messagesFunc.ImportChatInviteRequest(event.message.message.split('/')[-1]))
                except errors.ChannelsTooMuchError:
                    msg = "Не удалось добавить канал(__клиент вступил в слишком большое количество каналов__)"
                    await bot.send_message(event.message.peer_id, msg)
                except:
                    pass
            channel_id = await client.get_peer_id(event.message.message)
            set_mod_channel(mod_id, channel_id)
            add_mod_channel_tag(mod_id, channel_id, event.message.message)
            name = f"{utils.get_display_name(await client.get_entity(event.message.message))} ({event.message.message})"
            set_mod_channel_name(mod_id, name)
            mod_channels[mod_id] = channel_id
            await mainMenu(mod_id)
        elif userState[0] == 'edit_post':
            await event.delete()
            await bot.delete_messages(await event.get_input_chat(), moderating[mod_id]['edit_message_id'])
            msg = await mb_modGet(mod_id)
            msg['msg'].message = event.message.text
            msg['clmsg'].message = event.message.text
            if not msg: 
                await event.respond("Нет постов, ожидающих модерации", buttons=cancel) 
            else:
                modMsgId = await bot.send_message(event.message.peer_id, message=msg['msg'].message, file=msg['msg'].media, formatting_entities=msg['msg'].entities)
                moderating[mod_id] = msg
                moderating[mod_id]['mod_msg_id'] = modMsgId
                await event.respond(moderating[mod_id]['post_info'], buttons=moderation+[[cancel]])
                set_user_state(mod_id, 'moderating')
            
    else:
        if event.message.video or event.message.document:
            while not noDownloadBuffer[event.message.message]: await asyncio.sleep(0)
            for msg in noDownloadBuffer[event.message.message]:
                msg['bot'] = event.message.id
            set_no_download_message_bot_id(event.message.message, [event.message.id])
            if noDownloadCond.locked(): 
                noDownloadCond.release()
        else:
            await bot.send_message(event.message.peer_id, "Вы не модератор")

@bot.on(events.Album())
async def botAlbumHandler(event):
    message_ids = []
    for i, message in enumerate(event.messages):
        noDownloadBuffer[event.original_update.message.message][i]['bot'] = message.id
        message_ids += [message.id]
    set_no_download_message_bot_id(event.original_update.message.message, message_ids)
    if noDownloadCond.locked():
        noDownloadCond.release()

async def moderate(event, msg, mod_id):
    if not msg: 
        await event.respond("Нет постов, ожидающих модерации", buttons=cancel) 
    else:
        try:
            modMsgId = await event.respond(message=msg['msg'].message, file=msg['msg'].media, formatting_entities=msg['msg'].entities)
            moderating[mod_id] = msg
            moderating[mod_id]['mod_msg_id'] = modMsgId
            await event.respond(moderating[mod_id]['post_info'], buttons=moderation+[[cancel]])
            set_user_state(mod_id, 'moderating')
        except Exception as e:
            print(e)
            modTag = get_mod_tag(event.query.user_id)
            shutil.rmtree('./posts/waiting/'+modTag+'/'+msg['dir'], ignore_errors=True)
            if mod_id in mb_clientBuffer and mb_clientBuffer[mod_id]: mb_clientBuffer[mod_id].popleft()
            if msg['noDownloadKey'] in noDownloadBuffer:
                remove_no_download_message(mod_id, msg['noDownloadKey'])
                noDownloadBuffer.pop(msg['noDownloadKey'])
            mb_modBuffer[mod_id].popleft()
            mod_waiting_messages[mod_id] -= 1
            msg = await mb_modGet(mod_id)
            await moderate(event, msg, mod_id)

@bot.on(events.CallbackQuery())
async def bot_callback_handler(event):
    global moderating
    mod_id = event.query.user_id
    if user_exists(event.query.user_id):
        data = event.data.decode("utf-8")
        if data == 'main':
                await event.delete()
                await mainMenu(event.query.user_id)
                return
        elif data == 'back':
            await event.delete()
            set_user_state(event.query.user_id, get_user_prev_state(event.query.user_id))
            data = get_user_prev_action(event.query.user_id)
        mod_main_id[mod_id] = 0
        userState = get_user_state(event.query.user_id).split()
        if userState[0] == 'start':
            if data == 'moderation':
                await event.delete()
                msg = await mb_modGet(mod_id)
                await moderate(event, msg, mod_id)
            elif data == 'grabber_config':
                await event.delete()
                await event.respond(f"**Настройки граббера**\n\n**Префикс:**\n{get_prefix(mod_id)}\n**Постфикс:**\n{get_postfix(mod_id)}", buttons=grabConfig+[[cancel]])
            elif data == 'source_config':
                await event.delete()
                msg = "**Управление источниками**\n\nИсточники:\n\n"
                msg += parseSources(mod_id)
                await event.respond(msg, buttons=sourceConfig+[[back, cancel]])
                set_user_prev_action(event.query.user_id, 'grabber_config')
                set_user_prev_state(event.query.user_id, 'start')
            elif data == 'add_source':
                await event.delete()
                await event.respond("**Управление источниками**\n**Добавить источник**\n\nОтправьте ссылку-приглашение или @юзернейм канала", buttons=[back, cancel])
                set_user_state(event.query.user_id, 'add_source')
                set_user_prev_action(event.query.user_id, 'source_config')
            elif data == 'remove_source':
                await event.delete()
                sources = []
                for source in get_sources_ids(mod_id):
                    sources += [[button.Button.inline(get_source_name(mod_id, id=source), get_source_tag(mod_id, source))]]
                await event.respond("**Управление источниками**\n**Удалить источник**\n\nВыберите канал", buttons=sources+[[back, cancel]])
                set_user_state(event.query.user_id, 'remove_source')
                set_user_prev_action(event.query.user_id, 'source_config')
            elif data == 'edit_source':
                await event.delete()
                sources = []
                for source in get_sources_ids(mod_id):
                    sources += [[button.Button.inline(get_source_name(mod_id, id=source), get_source_tag(mod_id, source))]]
                await event.respond("**Управление источниками**\n**Настроить источник**\n\nВыберите источник", buttons=sources+[[back, cancel]])
                set_user_state(event.query.user_id, 'edit_source')
                set_user_prev_action(event.query.user_id, 'source_config')
            elif data == 'word_filter':
                await event.delete()
                msg = "**Фильтрация слов**\n\nСтоп-слова:\n"
                for i in get_stops(mod_id):
                    msg += f"{i[1]}\n"
                msg += "\n\nФильтры:\n"
                for i in get_filter_words(mod_id):
                    msg += f"{i[1]} -> {i[2]}\n"
                await event.respond(msg, buttons=filterConfig+[[back, cancel]])
                set_user_prev_action(event.query.user_id, 'grabber_config')
                set_user_prev_state(event.query.user_id, 'start')
            elif data == 'add_stop':
                await event.delete()
                await event.respond("**Фильтрация слов**\n**Добавить стоп-слова**\n\nВведите текст, который хотите заменить", buttons=[back, cancel])
                set_user_state(event.query.user_id, 'add_stop')
                set_user_prev_action(event.query.user_id, 'word_filter')
            elif data == 'remove_stop':
                await event.delete()
                stops = []
                for stop in get_stops(mod_id):
                    stop = list(stop)
                    if len(stop[1]) > 20: stop[1] = stop[1][:20] + '...'
                    stops += [[button.Button.inline(f"{stop[1]}", stop[0])]]
                await event.respond("**Фильтрация слов**\n**Удалить стоп-слова**\n\nВыберите слово", buttons=stops+[[back, cancel]])
                set_user_state(event.query.user_id, 'remove_stop')
                set_user_prev_action(event.query.user_id, 'word_filter')
            elif data == 'add_words':
                await event.delete()
                await event.respond("**Фильтрация слов**\n**Добавить фильтр**\n\nВведите текст, который хотите заменить", buttons=[back, cancel])
                set_user_state(event.query.user_id, 'add_filter')
                set_user_prev_action(event.query.user_id, 'word_filter')
            elif data == 'remove_words':
                await event.delete()
                filters = []
                for filter in get_filter_words(mod_id):
                    filter = list(filter)
                    if len(filter[1]) > 20: filter[1] = filter[1][:20] + '...'
                    if len(filter[2]) > 20: filter[2] = filter[2][:20] + '...'
                    filters += [[button.Button.inline(f"{filter[1]} -> {filter[2]}", filter[0])]]
                await event.respond("**Фильтрация слов**\n**Удалить фильтры**\n\nВыберите фильтр", buttons=filters+[[back, cancel]])
                set_user_state(event.query.user_id, 'remove_filter')
                set_user_prev_action(event.query.user_id, 'word_filter')
            elif data == 'mod_control':
                await event.delete()
                msg = "**Управление модераторами**\n\nМодераторы:\n"
                for i in get_mods():
                    msg += f"{get_mod_tag(i)}\n"
                await event.respond(msg, buttons=modControl+[[cancel]])
                set_user_prev_state(event.query.user_id, 'start')
            elif data == 'add_mod':
                await event.delete()
                await event.respond("**Управление модераторами**\n**Добавить модератора**\n\nВведите @юзернейм или юзер айди", buttons=[back, cancel])
                set_user_state(event.query.user_id, 'add_mod')
                set_user_prev_action(event.query.user_id, 'mod_control')
            elif data == 'remove_mod':
                await event.delete()
                mods = []
                for mod in get_mods():
                    mods += [[button.Button.inline(get_mod_tag(mod), mod)]]
                await event.respond("**Управление модераторами**\n**Удалить модератора**\n\nВыберите модератора", buttons=mods+[[back, cancel]])
                set_user_state(event.query.user_id, 'remove_mod')
                set_user_prev_action(event.query.user_id, 'mod_control')
            elif data == 'edit_prefix':
                await event.delete()
                await event.respond("**Настройки граббера**\n**Префикс**\n\nВведите новый префикс", buttons=[[clear],[back, cancel]])
                set_user_prev_action(event.query.user_id, 'grabber_config')
                set_user_state(event.query.user_id, 'edit_prefix')
            elif data == 'edit_postfix':
                await event.delete()
                await event.respond("**Настройки граббера**\n**Постфикс**\n\nВведите новый постфикс", buttons=[[clear],[back, cancel]])
                set_user_prev_action(event.query.user_id, 'grabber_config')
                set_user_state(event.query.user_id, 'edit_postfix')
            elif data == 'edit_watermark':
                await event.delete()
                msg = f"**Настройки граббера**\n**Водяной знак**\n\nПрозрачность: {get_watermark_opacity(mod_id)}%"
                if get_watermark(mod_id)['type'] == 'text':
                    msg += f"\nРазмер шрифта: {get_watermark_font_size(mod_id)}px"
                    msg += f"\nЦвет шрифта: {get_watermark_font_color(mod_id)}"
                wm = await parseWatermark(mod_id)
                await event.respond(msg+wm['msg'], file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
                set_user_state(event.query.user_id, 'edit_watermark')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'grabber_config')
            elif data == 'set_mod_channel':
                await event.delete()
                clientUsername = '@'+(await client.get_me()).username
                await event.respond(f"Отправьте ссылку-приглашение или @юзернейм канала и назначьте {clientUsername} адимнистратором с правом на отправку сообщений")
                set_user_state(event.query.user_id, 'set_mod_channel')              
        elif userState[0] == 'moderating':
            await event.delete()
            await bot.delete_messages(await event.get_input_chat(), moderating[mod_id]['mod_msg_id'])
            if data == 'edit_post':
                moderating[mod_id]['edit_message_id'] = await event.respond('Введите новый текст для поста', buttons=[[back, cancel]])
                set_user_state(event.query.user_id, 'edit_post')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'moderation')
            else:
                modTag = get_mod_tag(event.query.user_id)
                if data == 'pass':
                    shutil.move('./posts/waiting/'+modTag+'/'+moderating[mod_id]['dir'], './posts/archived/'+modTag+'/'+moderating[mod_id]['dir'])
                    await modPassMessage(event.query.user_id, moderating[mod_id]['clmsg'], moderating[mod_id]['filepaths'], moderating[mod_id]['noDownloadKey'])
                elif data == 'delete':
                    shutil.rmtree('./posts/waiting/'+modTag+'/'+moderating[mod_id]['dir'], ignore_errors=True)
                    if mod_id in mb_clientBuffer and mb_clientBuffer[mod_id]: mb_clientBuffer[mod_id].popleft()
                if moderating[mod_id]['noDownloadKey'] in noDownloadBuffer:
                    remove_no_download_message(mod_id, moderating[mod_id]['noDownloadKey'])
                    noDownloadBuffer.pop(moderating[mod_id]['noDownloadKey'])
                mb_modBuffer[mod_id].popleft()
                mod_waiting_messages[mod_id] -= 1
                msg = await mb_modGet(mod_id)
                await moderate(event, msg, mod_id)
        elif userState[0] == 'remove_mod':    
            await event.delete()
            mods = []
            shutil.rmtree('./watermark/'+str(data))
            shutil.rmtree('./posts/waiting/'+get_mod_tag(data))
            shutil.rmtree('./posts/archived/'+get_mod_tag(data))
            if not remove_mod(data):
                for mod in get_mods():
                    mods += [[button.Button.inline(get_mod_tag(mod), mod)]]
                await event.respond("**Управление модераторами**\n**Удалить модератора**\n\nНе удалось удалить модератора\nВыберите модератора", buttons=mods+[[back, cancel]])
            else:
                for mod in get_mods():
                    mods += [[button.Button.inline(get_mod_tag(mod), mod)]]
                await event.respond("**Управление модераторами**\n**Удалить модератора**\n\nМодератор удалён\nВыберите модератора", buttons=mods+[[back, cancel]])
        elif userState[0] == 'remove_stop':
            await event.delete()
            stops = []
            if not remove_stop(mod_id, data):
                for stop in get_stops(mod_id):
                    stop = list(stop)
                    if len(stop[1]) > 20: stop[1] = stop[1][:20] + '...'
                    stops += [[button.Button.inline(f"{stop[1]}", stop[0])]]
                await event.respond("**Фильтрация слов**\n**Удалить стоп-слова**\n\nНе удалось удалить стоп-слово\nВыберите слово для удаления", buttons=stops+[[back, cancel]])
            else:
                for stop in get_stops(mod_id):
                    stop = list(stop)
                    if len(stop[1]) > 20: stop[1] = stop[1][:20] + '...'
                    stops += [[button.Button.inline(f"{stop[1]}", stop[0])]]
                await event.respond("**Фильтрация слов**\n**Удалить стоп-слова**\n\nСтоп-слово удалёно\nВыберите слово для удаления", buttons=stops+[[back, cancel]])
        elif userState[0] == 'remove_filter':
            await event.delete()
            filters = []
            if not remove_filter_word(mod_id, data):
                for filter in get_filter_words(mod_id):
                    filter = list(filter)
                    if len(filter[1]) > 20: filter[1] = filter[1][:20] + '...'
                    if len(filter[2]) > 20: filter[2] = filter[2][:20] + '...'
                    filters += [[button.Button.inline(f"{filter[1]} -> {filter[2]}", filter[0])]]
                await event.respond("**Фильтрация слов**\n**Удалить слова**\n\nНе удалось удалить фильтр\nВыберите фильтр для удаления", buttons=filters+[[back, cancel]])
            else:
                for filter in get_filter_words(mod_id):
                    filter = list(filter)
                    if len(filter[1]) > 20: filter[1] = filter[1][:20] + '...'
                    if len(filter[2]) > 20: filter[2] = filter[2][:20] + '...'
                    filters += [[button.Button.inline(f"{filter[1]} -> {filter[2]}", filter[0])]]
                await event.respond("**Фильтрация слов**\n**Удалить слова**\n\nФильтр удалён\nВыберите фильтр для удаления", buttons=filters+[[back, cancel]])
        elif userState[0] == 'remove_source':
            await event.delete()
            sources = []
            source_id = await client.get_peer_id(data)
            if not remove_source(mod_id, source_id):
                for source in get_sources_ids(mod_id):
                    sources += [[button.Button.inline(get_source_name(mod_id, id=source), get_source_tag(mod_id, source))]]
                await event.respond("**Управление источниками**\n**Удалить источник**\n\nНе удалось удалить источник\nВыберите источник для удаления", buttons=sources+[[back, cancel]])
            else:
                remove_source_tag(mod_id, source_id)
                channels[source_id] -= 1
                if not channels[source_id]: 
                    channels.pop(source_id)
                    try:
                        asyncio.create_task(client(channelsFunc.LeaveChannelRequest(await client.get_input_entity(data))))
                    except:
                        pass
                for source in get_sources_ids(mod_id):
                    sources += [[button.Button.inline(get_source_name(mod_id, id=source), get_source_tag(mod_id, source))]]
                await event.respond("**Управление источниками**\n**Удалить источник**\n\nИсточник удалён\nВыберите источник для удаления", buttons=sources+[[back, cancel]])
            client.remove_event_handler(clientMessageHandler)
            client.remove_event_handler(clientAlbumHandler)
            client.add_event_handler(clientMessageHandler, events.NewMessage(chats=list(channels)))
            client.add_event_handler(clientAlbumHandler, events.Album(chats=list(channels)))
        elif userState[0] == 'edit_source':
            await event.delete()
            if len(userState)==1:
                source_id = await client.get_peer_id(data)
                msg = f"**Управление источниками**\n**Настроить источник**\n__{get_source_name(mod_id, tag=data)}__"
                if get_source_config(mod_id, source_id)['remove_links'] == 2:
                    msg += parseSourceRemoveLinks(mod_id, source_id)
                await event.respond(msg, buttons=sourceEdit(get_source_config(mod_id, source_id))+[[back, cancel]])
                set_user_state(event.query.user_id, f'edit_source {source_id}')
            else:
                msg = f"**Управление источниками**\n**Настроить источник**\n__{get_source_name(mod_id, id=userState[1])}__"
                if data == 'source_config_active':
                    set_source_active(mod_id, userState[1], 0)
                elif data == 'source_config_inactive':
                    set_source_active(mod_id, userState[1], 1)
                elif data == 'source_config_moderation_on':
                    set_source_moderation(mod_id, userState[1], 0)
                elif data == 'source_config_moderation_off':
                    set_source_moderation(mod_id, userState[1], 1) 
                elif data == 'source_config_allow_links_true':
                    set_source_allow_links(mod_id, userState[1], 0)
                elif data == 'source_config_allow_links_false':
                    set_source_allow_links(mod_id, userState[1], 1)
                elif data == 'source_config_remove_links_specified':
                    set_source_remove_links(mod_id, userState[1], 1)
                elif data == 'source_config_remove_links_all':
                    set_source_remove_links(mod_id, userState[1], 0)
                elif data == 'source_config_remove_links_false':
                    set_source_remove_links(mod_id, userState[1], 2)
                elif data == 'source_config_media_mode_without':
                    set_source_media_mode(mod_id, userState[1], 1)
                elif data == 'source_config_media_mode_with':
                    set_source_media_mode(mod_id, userState[1], 2)
                elif data == 'source_config_media_mode_any':
                    set_source_media_mode(mod_id, userState[1], 0)
                elif data == 'add_source_remove_link':
                    msg += "\n\n Введите ссылки(каждая с новой строки)"
                    await event.respond(msg, buttons=[[back, cancel]])
                    set_user_state(event.query.user_id, 'add_source_remove_link '+userState[1])
                    set_user_prev_action(event.query.user_id, get_source_tag(mod_id, userState[1]))
                    set_user_prev_state(event.query.user_id, userState[0])
                    return
                elif data == 'remove_source_remove_link':
                    msg += "\n\n Ввыберите ссылки для удаления"
                    links = []
                    for i in get_source_remove_links(mod_id, userState[1]):
                        links += [[button.Button.inline(i)]]
                    await event.respond(msg, buttons=links+[[back, cancel]])
                    set_user_state(event.query.user_id, 'remove_source_remove_link '+userState[1])
                    set_user_prev_action(event.query.user_id, get_source_tag(mod_id, userState[1]))
                    set_user_prev_state(event.query.user_id, userState[0])
                    return
                elif data == 'set_source_name':
                    msg += "\n\n Введите название"
                    await event.respond(msg, buttons=[[back, cancel]])
                    set_user_state(event.query.user_id, 'set_source_name '+userState[1])
                    set_user_prev_action(event.query.user_id, get_source_tag(mod_id, userState[1]))
                    set_user_prev_state(event.query.user_id, userState[0])
                    return
                config = get_source_config(mod_id, userState[1])
                if config['allow_links'] and config['remove_links'] == 2: 
                        msg += parseSourceRemoveLinks(mod_id, userState[1])
                await event.respond(msg, buttons=sourceEdit(get_source_config(mod_id, userState[1]))+[[back, cancel]])
            set_user_prev_action(event.query.user_id, 'edit_source')
            set_user_prev_state(event.query.user_id, 'start')
        elif userState[0] == 'edit_prefix':
            await event.delete()
            set_prefix(mod_id, "")
            await bot.send_message(event.query.user_id, f"**Настройки граббера**\n\n**Префикс:**\n{get_prefix(mod_id)}\n**Постфикс:**\n{get_postfix(mod_id)}", buttons=grabConfig+[[cancel]])
            set_user_state(event.query.user_id, 'start')
        elif userState[0] == 'edit_postfix':
            await event.delete()
            set_postfix(mod_id, "")
            await bot.send_message(event.query.user_id, f"**Настройки граббера**\n\n**Префикс:**\n{get_prefix(mod_id)}\n**Постфикс:**\n{get_postfix(mod_id)}", buttons=grabConfig+[[cancel]])
            set_user_state(event.query.user_id, 'start')
        elif userState[0] == 'remove_source_remove_link':
            await event.delete()
            remove_source_remove_link(mod_id, userState[1], data)
            msg = f"**Управление источниками**\n**Настроить источник**\n__{get_source_name(mod_id, id=userState[1])}__\n\n Выберите ссылку для удаления"
            links = []
            for i in get_source_remove_links(mod_id, userState[1]):
                links += [[button.Button.inline(i)]]
            await event.respond(msg, buttons=links+[[back, cancel]])
        elif userState[0] == 'edit_watermark':
            await event.delete()
            if data == 'clear':
                set_watermark(mod_id, '', '')
                msg = "**Настройки граббера**\n**Водяной знак**"
                wm = await parseWatermark(mod_id)
                await event.respond(msg+wm['msg'], file=wm['image'], buttons=watermark(get_watermark(mod_id)['type'])+[[clear],[back, cancel]])
            elif data == 'watermark':
                await event.respond("**Настройки граббера**\n**Водяной знак**\n\nОтправьте текст или изображение(**БЕЗ СЖАТИЯ**)", buttons=[[back, cancel]])
                set_user_state(event.query.user_id, 'set_watermark')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'edit_watermark')
            elif data == 'watermark_opacity':
                await event.respond("**Настройки граббера**\n**Водяной знак**\n\nВведите значение прозрачности(1-100)", buttons=[[back, cancel]])
                set_user_state(event.query.user_id, 'set_watermark_opacity')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'edit_watermark')
            elif data == 'watermark_font_size':
                await event.respond("**Настройки граббера**\n**Водяной знак**\n\nВведите размер шрифта(px)", buttons=[[back, cancel]])
                set_user_state(event.query.user_id, 'set_watermark_font_size')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'edit_watermark')
            elif data == 'watermark_font_color':
                await event.respond("**Настройки граббера**\n**Водяной знак**\n\nВведите цвет шрифта в формате: # t.me/tg_inc_softw   FFFFFF", buttons=[[back, cancel]])
                set_user_state(event.query.user_id, 'set_watermark_font_color')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'edit_watermark')
            elif data == 'watermark_font':
                await event.respond("**Настройки граббера**\n**Водяной знак**\n\nОтправьте .ttf файл шрифта", buttons=[[back, cancel]])
                set_user_state(event.query.user_id, 'set_watermark_font')
                set_user_prev_state(event.query.user_id, 'start')
                set_user_prev_action(event.query.user_id, 'edit_watermark')
        elif userState[0] == 'add_filter_replacement':
            msg = "**Фильтрация слов**\n**Добавить слова**\n\n"
            if not add_filter_word(mod_id, filterConfigText, ''):
                msg += "Не удалось добавить фильтры\nФильтры:\n"
                for filter in get_filter_words(mod_id):
                    msg += f"{filter[1]} -> {filter[2]}\n"
                await event.respond(msg, buttons=filterConfig+[[back, cancel]])
            else:
                msg += "Фильтры добавлены\nФильтры:\n"
                for filter in get_filter_words(mod_id):
                    msg += f"{filter[1]} -> {filter[2]}\n"
                await event.respond(msg, buttons=filterConfig+[[back, cancel]])
            set_user_state(mod_id, 'start')
            
    else:
        await event.respond("Вы не модератор")
            
        
async def clientMessageHandler(event):
    if event.message and not event.message.grouped_id:
        mods = get_mods()
        for mod in mods:            
            if str(utils.get_peer_id(event.message.peer_id)) in get_sources_ids(mod):
                config = get_source_config(mod, utils.get_peer_id(event.message.peer_id))
                if config['active'] and ((config['media_mode'] == 1 and event.message.media) or (config['media_mode'] == 0 and not event.message.media) or config['media_mode'] == 2): 
                    if any(x[1] in event.message.message for x in get_stops(mod)): return
                    if event.message.entities and any(x[1] in e.url for x in get_stops(mod) for e in event.message.entities if isinstance(e, types.MessageEntityTextUrl)): return
                    if not config['allow_links'] and event.message.entities and any(isinstance(e, (types.MessageEntityUrl, MessageEntityTextUrl)) for e in event.message.entities):  return
                    if not config['allow_links'] and event.message.buttons and any(b.url for row in event.message.buttons for b in row): return
                    if event.message.sticker: return
                    if event.message.media and isinstance(event.message.media, MessageMediaDocument) and any(attr.voice for attr in event.message.media.document.attributes if isinstance(attr, types.DocumentAttributeAudio)): return

                    messageId = event.message.to_dict()['id']
                    date = event.message.to_dict()['date'].strftime('%Y-%m-%d-%H-%M-%S')
                    dirName = get_mod_tag(mod)
                    srcName = removeRestrictedCharacters(get_source_name(mod, id=utils.get_peer_id(event.message.peer_id)))
                    if ' (@' in srcName:
                        dirName += f'/{date}_{messageId}_{srcName}'
                    else:
                        dirName += f"/{date}_{messageId}_{srcName.split('(http')[0]}"
                    dirName = dirName.strip()

                    # t.me/tg_inc_softw    Putting watermark
                    if event.message.media != None:
                        wm = get_watermark(mod)
                        if isinstance(event.message.media, types.MessageMediaPhoto) and len(wm['type']) != 0:
                            await client.download_media(event.message.media, f'./watermark/{str(mod)}/{dirName}/image.png')
                            if wm['type'] == 'text':
                                watermark_text(f'./watermark/{mod}/{dirName}/image.png', wm['watermark'], (0,0), get_watermark_opacity(mod), get_watermark_font_size(mod), get_watermark_font_color(mod))
                            else:
                                watermark_image(f'./watermark/{mod}/{dirName}/image.png', f'./watermark/{mod}/watermark.png', (0,0), get_watermark_opacity(mod))
                    
                    # t.me/tg_inc_softw    Filtering message and adjusting remaning entities' offsets and lengths
                    filterDict = {}
                    for filter in get_filter_words(mod):
                        filterDict[filter[1]] = filter[2]
                    if event.message.entities != None:
                        if config['remove_links'] == 1:
                            event.message.entities = [i for i in event.message.entities if not isinstance(i, types.MessageEntityTextUrl)]
                            offset = 0
                            for e in event.message.entities:
                                e.offset -= offset
                                if isinstance(e, types.MessageEntityUrl):
                                    event.message.message = event.message.message[:e.offset] + event.message.message[e.offset+e.length+1:]
                                    offset += len(event.message.message[e.offset:e.offset+e.length])+1              
                        elif config['remove_links'] == 2:
                            entities = []
                            links = get_source_remove_links(mod, utils.get_peer_id(event.message.peer_id))
                            offset = 0
                            for e in event.message.entities:
                                e.offset -= offset
                                if type(e) == types.MessageEntityTextUrl:
                                    word = event.message.message[e.offset:e.offset+e.length]
                                    if any(l in e.url for l in links):
                                        continue 
                                    if word in filterDict.keys():
                                        e.length = len(filterDict[word])
                                        offset += len(word) - len(filterDict[word])
                                elif type(e) == types.MessageEntityUrl:
                                    url = event.message.message[e.offset:e.offset+e.length]
                                    if any(l in url for l in links):
                                        event.message.message = event.message.message[:e.offset] + event.message.message[e.offset+e.length+1:]
                                        offset += len(url)+1
                                entities += [e]
                            event.message.entities = entities
                        else:
                            offset = 0
                            for e in event.message.entities:
                                e.offset -= offset
                                if type(e) == types.MessageEntityTextUrl:
                                    word = event.message.message[e.offset:e.offset+e.length]
                                    if word in filterDict.keys():
                                        e.length = len(filterDict[word])
                                        offset += len(word) - len(filterDict[word])                        
                        if len(get_prefix(mod)) > 0:
                            for i, _ in enumerate(event.message.entities):
                                event.message.entities[i].offset += len(get_prefix(mod))+2
                    for k in filterDict.keys():
                        event.message.message = re.sub(fr'(?<!\w){re.escape(k)}(?!\w)', filterDict[k], event.message.message)
                        
                    prefix = get_prefix(mod)
                    postfix = get_postfix(mod)
                    if prefix: 
                        event.message.message = prefix + "\n\n" + event.message.message
                    if postfix:
                        event.message.message = event.message.message + "\n\n" + postfix
                    
                    # t.me/tg_inc_softw    Saving message 
                    os.mkdir('./posts/waiting/'+dirName)
                    path = './posts/waiting/'+dirName+'/'
                    with open(path+"message.json", 'w', encoding='utf-8') as f:
                        json.dump(json.loads(event.message.to_json()), f, indent=4)
                    if isinstance(event.message.media, types.MessageMediaPhoto) and len(wm['type']) != 0:
                        await copyFile(f'./watermark/{mod}/{dirName}/image.png', path+"file.png")
                        shutil.rmtree(f'./watermark/{mod}/{dirName}')
                    elif not event.message.web_preview:
                        if not event.message.gif and (event.message.video or event.message.document):
                            await noDownloadCond.acquire()
                            noDownloadBuffer[dirName] = []
                            msg = await client.send_message(BOT_USERNAME, message=dirName, file=event.message.media)
                            noDownloadBuffer[dirName] = [{'client': msg.id, 'bot': None}]
                            add_no_download_message(mod, dirName, msg.id, 0)
                        else:
                            filename = 'file'
                            if not isinstance(event.message.media, types.MessageMediaPhoto):
                                extension = utils.get_extension(event.message.media)
                            else:
                                extension = '.png'
                            if isinstance(event.message.media, types.MessageMediaDocument):
                                for attr in event.message.media.document.attributes:
                                    if isinstance(attr, types.DocumentAttributeFilename):
                                        splitName = attr.file_name.split('.')
                                        filename = splitName[0]
                                        if len(splitName) > 2:
                                            if splitName[-2] == 'gif': extension = '.gif'
                            await client.download_media(event.message.media, path+filename+extension)

                    if config['moderation']:
                        mb_addTasks[mod].append(asyncio.create_task(mb_add(mod, True)))
                        await asyncio.sleep(0)
                        if noDownloadCond.locked():
                            await noDownloadCond.acquire()
                            noDownloadCond.release()
                    else:
                        index = await mb_add(mod, False)
                        if noDownloadCond.locked():
                            await noDownloadCond.acquire()
                            noDownloadCond.release()
                        msg = await mb_modGet(mod, index)
                        shutil.move(path, path.replace('waiting', 'archived'))
                        asyncio.create_task(modPassMessage(mod, msg['clmsg'], msg['filepaths'], msg['noDownloadKey'], True))
                        del mb_modBuffer[mod][index]
                        mod_waiting_messages[mod] -= 1
		
async def clientAlbumHandler(event):
    mods = get_mods()
    for mod in mods:            
        if str(utils.get_peer_id(event.original_update.message.peer_id)) in get_sources_ids(mod):
            config = get_source_config(mod, utils.get_peer_id(event.original_update.message.peer_id))
            if any(x[1] in event.original_update.message.message for x in get_stops(mod)): return
            if event.original_update.message.entities and any(x[1] in e.url for x in get_stops(mod) for e in event.original_update.message.entities if isinstance(e, types.MessageEntityTextUrl)): return
            if config['media_mode'] == 0 or config['active'] == 0: return
            elif not config['allow_links'] and event.original_update.message.entities and any(isinstance(e, (types.MessageEntityUrl, MessageEntityTextUrl)) for e in event.original_update.message.entities):  return
            elif not config['allow_links'] and event.original_update.message.buttons and any(b.url for row in event.original_update.message.buttons for b in row): return
            else:
                messageId = event.original_update.message.to_dict()['id']
                date = event.original_update.message.to_dict()['date'].strftime('%Y-%m-%d-%H-%M-%S')
                dirName = get_mod_tag(mod)
                srcName = removeRestrictedCharacters(get_source_name(mod, id=utils.get_peer_id(event.original_update.message.peer_id)))
                if ' (@' in srcName:
                    dirName += f'/{date}_{messageId}_{srcName}'
                else:
                    dirName += f"/{date}_{messageId}_{srcName.split('(http')[0]}"
                dirName = dirName.strip()

                # t.me/tg_inc_softw    Putting watermark
                for i, message in enumerate(event.messages):
                    if message.media != None:
                        wm = get_watermark(mod)
                        if type(message.media) == types.MessageMediaPhoto and len(wm['type']) != 0:
                            await client.download_media(message.media, f'./watermark/{mod}/{dirName}/image{i}.png')
                            if wm['type'] == 'text':
                                watermark_text(f'./watermark/{mod}/{dirName}/image{i}.png', wm['watermark'], (0,0), get_watermark_opacity(mod), get_watermark_font_size(mod), get_watermark_font_color(mod))
                            else:
                                watermark_image(f'./watermark/{mod}/{dirName}/image{i}.png', f'./watermark/{mod}/watermark.png', (0,0), get_watermark_opacity(mod))
                
                # t.me/tg_inc_softw    Filtering message and adjusting remaning entities' offsets and lengths
                filterDict = {}
                for filter in get_filter_words(mod):
                    filterDict[filter[1]] = filter[2]
                if event.original_update.message.entities != None:
                    if config['remove_links'] == 1:
                        event.original_update.message.entities = [i for i in event.original_update.message.entities if not isinstance(i, types.MessageEntityTextUrl)]
                        offset = 0
                        for e in event.original_update.message.entities:
                            e.offset -= offset
                            if isinstance(e, types.MessageEntityUrl):
                                event.original_update.message.message = event.original_update.message.message[:e.offset] + event.original_update.message.message[e.offset+e.length+1:]
                                offset += len(event.original_update.message.message[e.offset:e.offset+e.length])+1
                    elif config['remove_links'] == 2:
                        entities = []
                        links = get_source_remove_links(mod, utils.get_peer_id(event.original_update.message.peer_id))
                        offset = 0
                        for e in event.original_update.message.entities:
                            e.offset -= offset
                            if type(e) == types.MessageEntityTextUrl:
                                word = event.original_update.message.message[e.offset:e.offset+e.length]
                                if any(l in e.url for l in links):
                                    continue 
                                if word in filterDict.keys():
                                    e.length = len(filterDict[word])
                                    offset += len(word) - len(filterDict[word])
                            elif type(e) == types.MessageEntityUrl:
                                url = event.original_update.message.message[e.offset:e.offset+e.length]
                                if any(l in url for l in links):
                                    event.original_update.message.message = event.original_update.message.message[:e.offset] + event.original_update.message.message[e.offset+e.length+1:]
                                    offset += len(url)+1
                            entities += [e]
                        event.original_update.message.entities = entities
                    else:
                        offset = 0
                        for e in event.original_update.message.entities:
                            e.offset -= offset
                            if type(e) == types.MessageEntityTextUrl:
                                word = event.original_update.message.message[e.offset:e.offset+e.length]
                                if word in filterDict.keys():
                                    e.length = len(filterDict[word])
                                    offset += len(word) - len(filterDict[word])
                    if len(get_prefix(mod)) > 0:
                        for i, _ in enumerate(event.original_update.message.entities):
                            event.original_update.message.entities[i].offset += len(get_prefix(mod))+2
                for k in filterDict.keys():
                    event.original_update.message.message = re.sub(fr'(?<!\w){re.escape(k)}(?!\w)', filterDict[k], event.original_update.message.message)
                    
                prefix = get_prefix(mod)
                postfix = get_postfix(mod)
                if prefix: 
                    event.original_update.message.message = prefix + "\n\n" + event.original_update.message.message
                if postfix:
                    event.original_update.message.message = event.original_update.message.message + "\n\n" + postfix
                    
                # t.me/tg_inc_softw    Saving message 
                os.mkdir('./posts/waiting/'+dirName)
                path = './posts/waiting/'+dirName+'/'
                with open(path+"message.json", 'w', encoding='utf-8') as f:
                    json.dump(json.loads(event.original_update.message.to_json()), f, indent=4)
                noDownload = []
                for i, message in enumerate(event.messages):
                    if message.video or message.document:
                        noDownload += [message.media]
                    else:
                        if isinstance(message.media, types.MessageMediaPhoto) and len(wm['type']) != 0:
                            await copyFile(f'./watermark/{mod}/{dirName}/image{i}.png', path+f'image{i}.png')
                        else:
                            filename = f'file{i}'
                            if not isinstance(message.media, types.MessageMediaPhoto):
                                extension = utils.get_extension(message.media)
                            else:
                                extension = '.png'
                            if isinstance(message.media, types.MessageMediaDocument):
                                for attr in message.media.document.attributes:
                                    if isinstance(attr, types.DocumentAttributeFilename):
                                        filename = attr.file_name.split('.')[0]
                            await client.download_media(message.media, path+filename+extension)
                if noDownload:
                    await noDownloadCond.acquire()
                    noDownloadBuffer[dirName] = []
                    msg = await client.send_message(BOT_USERNAME, message=dirName, file=noDownload)
                    for message in msg:
                        noDownloadBuffer[dirName] += [{'client': message.id, 'bot': None}]
                        add_no_download_message(mod, dirName, message.id, 0)

                if len(wm['type']) != 0:
                    shutil.rmtree(f'./watermark/{mod}/{dirName}')

                if config['moderation']:
                    mb_addTasks[mod].append(asyncio.create_task(mb_add(mod, True)))
                    await asyncio.sleep(0)
                    if noDownloadCond.locked():
                        await noDownloadCond.acquire()
                        noDownloadCond.release()
                else:
                    index = await mb_add(mod, False)
                    if noDownloadCond.locked():
                        await noDownloadCond.acquire()
                        noDownloadCond.release()
                    msg = await mb_modGet(mod, index)
                    shutil.move(path, path.replace('waiting', 'archived'))
                    asyncio.create_task(modPassMessage(mod, msg['clmsg'], msg['filepaths'], msg['noDownloadKey'], True))
                    del mb_modBuffer[mod][index]
                    mod_waiting_messages[mod] -= 1

client.start()
client.add_event_handler(clientMessageHandler, events.NewMessage(chats=list(channels)))
client.add_event_handler(clientAlbumHandler, events.Album(chats=list(channels)))
bot.start()
async def restoreNoDownload():
    for mod in get_mods():
        messages = get_no_download_messages(mod)
        for msg in messages: noDownloadBuffer[msg['path']] = []
        for msg in messages:
            noDownloadBuffer[msg['path']] += [{'client': msg['client_id'], 'bot': msg['bot_id']}]
asyncio.get_event_loop().run_until_complete(restoreNoDownload())

asyncio.create_task(client.run_until_disconnected())
asyncio.create_task(bot.run_until_disconnected())