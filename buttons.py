from telethon.tl.custom import button

admins = []
def startButtons(mod_id):
    buttons = [
        [button.Button.inline('🔧Настройки граббера', 'grabber_config')],
        [button.Button.inline('Модерация', 'moderation')],
        [button.Button.inline('Сменить канал', 'set_mod_channel')]
    ]
    if mod_id in admins:
        buttons += [[button.Button.inline('👮‍♂️Управление модераторами', 'mod_control')]]
    return buttons

grabConfig = [
    [button.Button.inline('Управление источниками', 'source_config')],
    [button.Button.inline('Фильтрация слов', 'word_filter')],
    [button.Button.inline('Префикс', 'edit_prefix'), button.Button.inline('Постфикс', 'edit_postfix')],
    [button.Button.inline('Водяной знак', 'edit_watermark')]
]

def watermark(type):
    b = [
        [button.Button.inline('Изменить знак', 'watermark')],
        [button.Button.inline('Прозрачность', 'watermark_opacity')]
    ]
    if type == 'text':
        b += [[
            button.Button.inline('Размер', 'watermark_font_size'),
            button.Button.inline('Цвет', 'watermark_font_color'),
            button.Button.inline('Шрифт', 'watermark_font')
            ]]
    return b

filterConfig = [
    [button.Button.inline('➕Добавлить стоп-слова', 'add_stop')],
    [button.Button.inline('➖Удалить стоп-слова', 'remove_stop')],
    [button.Button.inline('➕Добавлить фильтр', 'add_words')],
    [button.Button.inline('➖Удалить фильтр', 'remove_words')]
]

sourceConfig = [
    [button.Button.inline('➕Добавить источник', 'add_source')],
    [button.Button.inline('➖Удалить источник', 'remove_source')],
    [button.Button.inline('⚙️Настроить источник', 'edit_source')]
]

def sourceEdit(config):
    b = []
    if bool(config['active']):
        b += [[button.Button.inline('Состояние: Активен', 'source_config_active')]]
    else:
        b += [[button.Button.inline('Состояние: Неактивен', 'source_config_inactive')]]
    if config['moderation']:
        b += [[button.Button.inline('Модерация: Вкл', 'source_config_moderation_on')]]
    else:
        b += [[button.Button.inline('Модерация: Выкл', 'source_config_moderation_off')]]
    if config['media_mode'] == 0:
        b += [[button.Button.inline('Допускать посты: Без медиа', 'source_config_media_mode_without')]]
    elif config['media_mode'] == 1:
        b += [[button.Button.inline('Допускать посты: С медиа', 'source_config_media_mode_with')]]
    else:
        b += [[button.Button.inline('Допускать посты: Любые', 'source_config_media_mode_any')]]
    if config['allow_links']:
        b += [[button.Button.inline('Разрешить посты со ссылками: Да', 'source_config_allow_links_true')]]
        if config['remove_links'] == 2:
            b += [[button.Button.inline('Удалять ссылки: Указанные', 'source_config_remove_links_specified')]]
            b += [[button.Button.inline('+ ссылки', 'add_source_remove_link'), button.Button.inline('- ссылки', 'remove_source_remove_link')]]
        elif config['remove_links'] == 1:
            b += [[button.Button.inline('Удалять ссылки: Все', 'source_config_remove_links_all')]]
        else:
            b += [[button.Button.inline('Удалять ссылки: Нет', 'source_config_remove_links_false')]]
    else:
        b += [[button.Button.inline('Разрешить посты со ссылками: Нет', 'source_config_allow_links_false')]]
    b += [[button.Button.inline('✏️Изменить название', 'set_source_name')]]
    return b

moderation = [
    [button.Button.inline('Изменить текст', 'edit_post')],
    [button.Button.inline('Удалить', 'delete'), button.Button.inline('Пропустить', 'pass')]
]
    
modControl = [
    [button.Button.inline('➕Добавить модератора', 'add_mod')],
    [button.Button.inline('➖Удалить модератора', 'remove_mod')],
]

filterNoReplacement = [
    [button.Button.inline('Стирать без замены', 'add_filter_no_replacement')]
]

clear = button.Button.inline('Очистить', 'clear')
back = button.Button.inline('◀️Назад', 'back')
cancel = button.Button.inline('🏠Главная', 'main')