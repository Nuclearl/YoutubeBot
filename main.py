import logging, threading, time
from config import token, admins, API_KEY
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from python_mysql import read_db_config
from mysql.connector import MySQLConnection, Error
from aiogram.utils.exceptions import ChatNotFound
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from ParseFile import *
import asyncio
from concurrent.futures import ProcessPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=token)
dp = Dispatcher(bot, storage=MemoryStorage())

# keyboard
panel_administrators = 'Панель администратора 👨‍💻'
panel_custom = 'Панель пользователя 👨‍🦰'
statistics = 'Статистика📊'
my_redirects = "Мои перенаправления📁"
tree_btn = "Дерево🗃"


def menu_keyboard(user_id):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton(my_redirects), KeyboardButton(tree_btn))
    if user_id in admins:
        keyboard.row(KeyboardButton(panel_administrators))
    return keyboard


back_btn = '⬅️Назад'
main_back_btn = 'Вернуться в основное меню'
mail_but = "Рассылка"
backMail_but = 'Назад ◀️'
preMail_but = 'Предпросмотр 👁'
startMail_but = 'Старт 🏁'
textMail_but = 'Текст 📝'
butMail_but = 'Ссылка-кнопка ⏺'
photoMail_but = 'Фото 📸'

admin_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
admin_keyboard.add(*[KeyboardButton(name) for name in [panel_custom]])
admin_keyboard.add(*[KeyboardButton(name) for name in [mail_but, statistics]])

mail_menu = ReplyKeyboardMarkup(resize_keyboard=True)
mail_menu.add(*[KeyboardButton(name) for name in [textMail_but, photoMail_but]])
mail_menu.add(*[KeyboardButton(name) for name in [butMail_but, preMail_but]])
mail_menu.add(*[KeyboardButton(name) for name in [backMail_but, startMail_but]])


# state
class TelegramStates(StatesGroup):
    id = State()


class YoutubeStates(StatesGroup):
    url = State()


class TextStates(StatesGroup):
    text = State()


class MailingStates(StatesGroup):
    admin_mailing = State()


class ProcessTextMailing(StatesGroup):
    text = State()


class ProcessEditTextBut(StatesGroup):
    text = State()


class ProcessEditUrlBut(StatesGroup):
    text = State()


class WaitPhoto(StatesGroup):
    text = State()


class CheckerState(StatesGroup):
    check = State()


async def mailing(user_ids, lively, banned, deleted, chat_id, mail_text, mail_photo, mail_link, mail_link_text):
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    c = conn.cursor(buffered=True)
    users_block = []
    start_mail_time = time.time()
    c.execute('''SELECT COUNT(*) FROM users''')
    allusers = int(c.fetchone()[0])
    for user_id in user_ids:
        try:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(text=mail_link_text, url=mail_link))
            if str(mail_photo) != '0':
                if str(mail_link_text) != '0':
                    await bot.send_photo(user_id, caption=mail_text, photo=mail_photo, parse_mode='HTML',
                                         reply_markup=keyboard)
                else:
                    await bot.send_photo(user_id, caption=mail_text, parse_mode='HTML', photo=mail_photo)
            else:
                if str(mail_link_text) not in '0':
                    await bot.send_message(user_id, text=mail_text, parse_mode='HTML',
                                           reply_markup=keyboard)
                else:
                    await bot.send_message(user_id, parse_mode='HTML', text=mail_text)
            lively += 1
        except Exception as e:
            if 'bot was blocked by the user' in str(e):
                users_block.append(user_id)
                banned += 1
                # database is locked
    print(users_block)
    for user_id in users_block:
        c.execute("UPDATE users SET lively = (%s) WHERE user_id = (%s)", ('block', user_id,))
    admin_text = '*Рассылка окончена! ✅\n\n' \
                 '🙂 Количество живых пользователей:* {0}\n' \
                 '*% от числа всех:* {1}%\n' \
                 '*💩 Количество заблокировавших:* {3}\n' \
                 '*🕓 Время рассылки:* {2}'.format(str(lively), str(round(lively / allusers * 100, 2)),
                                                   str(round(time.time() - start_mail_time, 2)) + ' сек', str(banned))
    await bot.send_message(chat_id, admin_text, parse_mode='Markdown', reply_markup=admin_keyboard)
    c.close()
    conn.commit()


async def send_video_to_channel():
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    c = conn.cursor(buffered=True)
    unique_list = []
    c.execute(
        "SELECT DISTINCT * FROM user_channel WHERE youtube_channel_id IS NOT NULL and youtube_name IS NOT NULL")
    current_channel = c.fetchall()

    for channel in current_channel:
        c.execute("SELECT DISTINCT video_id FROM video_channel WHERE youtube_channel_id = %s", (channel[2],))
        list_video_from_bd = c.fetchall()
        list_video_from_bd = [i[0] for i in list_video_from_bd][-50:]
        list_video_from_youtube = get_video_by_channelID(API_KEY, channel[2])
        if list_video_from_youtube == False:
            break
        print(list_video_from_youtube)
        print(list_video_from_bd)
        for video in list_video_from_youtube[::-1]:
            if video not in list_video_from_bd:
                try:
                    if "[name]" not in channel[3]:
                        await bot.send_message(channel[1], (channel[3].replace("[link]", "{0}")).format(
                            f"https://www.youtube.com/watch?v={video}"), parse_mode="HTML")
                    else:
                        await bot.send_message(channel[1],
                                               (channel[3].replace("[name]", "{0}").replace("[link]", "{1}")).format(
                                                   channel[4], f"https://www.youtube.com/watch?v={video}"),
                                               parse_mode="HTML")
                    if [channel[2], video] not in unique_list:
                        unique_list.append([channel[2], video])
                except Exception as e:
                    print(e)
    for unique in unique_list:
        c.execute(
            "INSERT INTO video_channel (youtube_channel_id, video_id) VALUES (%s, %s)",
            (unique[0], unique[1]))
    conn.commit()
    c.close()


"""
@dp.message_handler(lambda m: m.from_user.id in admins, commands=["admin"])
async def admin_command(message: types.Message):
    await bot.send_message(message.chat.id, "Админ меню", reply_markup=admin_keyboard)
"""


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    c = conn.cursor(buffered=True)
    user_id = message.from_user.id
    c.execute("select * from users where user_id = %s", (user_id,))
    repeat = c.fetchall()
    if not repeat:
        try:
            c.execute("insert into users (user_id) values (%s)", (user_id,))
        except Exception as error:
            print("Error:", error)
    conn.commit()
    c.close()
    await bot.send_message(message.from_user.id,
                           "Привет!✋\n\n Я способен отправлять 📤 новые видео твоего любимого видеоблоггера 📹, на твой собственный телеграмм канал, единственное что ты должен сделать, это добавить меня в телеграмм канал <b>(не забудь дать мне права администратора)</b>, и подключить свой телеграмм канал к боту с помощью кнопки <b>Мои перенаправления📁</b>",
                           reply_markup=menu_keyboard(user_id), parse_mode="HTML")


@dp.message_handler(lambda m: m.text == mail_but and m.chat.id in admins and m.from_user.id == m.chat.id)
async def cheker(message: types.Message):
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)

    async def admin_mailing(message: types.Message):
        chat_id = message.chat.id
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        msgtext = message.text
        c.execute("""select textMail from users where user_id = %s""" % chat_id)
        textMailUser = str(c.fetchone()[0])
        c.execute("""select photoMail from users where user_id = %s""" % chat_id)
        photoMailUser = str(c.fetchone()[0])
        c.execute("""select butTextMail from users where user_id = %s""" % chat_id)
        butTextMail = str(c.fetchone()[0])
        c.execute("""select butUrlMail from users where user_id = %s""" % chat_id)
        butUrlMail = str(c.fetchone()[0])
        if msgtext == mail_but:
            await bot.send_message(chat_id, '*Вы попали в меню рассылки *📢\n\n'
                                            'Для возврата нажмите *{0}*\n\n'
                                            'Для отмены какой-либо операции нажмите /start\n\n'
                                            'Используйте *{1}* для предварительного просмотра рассылки, а *{2}* для начала'
                                            ' рассылки\n\n'
                                            'Текст рассылки поддерживает разметку *HTML*, то есть:\n'
                                            '<b>*Жирный*</b>\n'
                                            '<i>_Курсив_</i>\n'
                                            '<pre>`Моноширный`</pre>\n'
                                            '<a href="ссылка-на-сайт">[Обернуть текст в ссылку](test.ru)</a>'.format(
                backMail_but, preMail_but, startMail_but
            ),
                                   parse_mode="markdown", reply_markup=mail_menu)
            await MailingStates.admin_mailing.set()

        elif msgtext == backMail_but:
            await bot.send_message(chat_id, backMail_but, reply_markup=admin_keyboard)
            # bot.clear_step_handler(message)

        elif msgtext == preMail_but:
            try:
                if butTextMail == '0' and butUrlMail == '0':
                    if photoMailUser == '0':
                        await bot.send_message(chat_id, textMailUser, parse_mode='html', reply_markup=mail_menu)
                    else:
                        await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                             reply_markup=mail_menu)
                else:
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton(text=butTextMail, url=butUrlMail))
                    if photoMailUser == '0':
                        await bot.send_message(chat_id, textMailUser, parse_mode='html',
                                               reply_markup=keyboard)
                    else:
                        await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                             reply_markup=keyboard)
            except:
                await bot.send_message(chat_id, "Упс..проверьте правильность введения данных")
            await MailingStates.admin_mailing.set()

        elif msgtext == startMail_but:
            c.execute("""update users set textMail = 0 where user_id = %s""" % chat_id)
            c.execute("""update users set photoMail = 0 where user_id = %s""" % chat_id)
            c.execute("""update users set butTextMail = 0 where user_id = %s""" % chat_id)
            c.execute("""update users set butUrlMail = 0 where user_id = %s""" % chat_id)
            user_ids = []
            c.execute("""select user_id from users""")
            user_id = c.fetchone()
            while user_id is not None:
                user_ids.append(user_id[0])
                user_id = c.fetchone()
            c.close()
            mail_thread = threading.Thread(target=mailing, args=(
                user_ids, 0, 0, 0, chat_id, textMailUser, photoMailUser, butUrlMail, butTextMail))
            mail_thread.start()
            await bot.send_message(chat_id, 'Рассылка началась!',
                                   reply_markup=admin_keyboard)

        elif textMail_but == msgtext:
            await bot.send_message(chat_id,
                                   'Введите текст рассылки. Допускаются теги HTML. Для отмены ввода нажите /start',
                                   reply_markup=mail_menu)
            await ProcessTextMailing.text.set()

        elif photoMail_but == msgtext:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton(text='Добавить фото 📝', callback_data='editPhotoMail'))
            keyboard.row(InlineKeyboardButton(text='Удалить фото ❌', callback_data='deletePhoto'))
            await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
            await MailingStates.admin_mailing.set()

        elif butMail_but == msgtext:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton(text='Изменить текст кнопки 📝', callback_data='editTextBut'))
            keyboard.row(InlineKeyboardButton(text='Изменить ссылку кнопки 🔗', callback_data='editUrlBut'))
            keyboard.row(InlineKeyboardButton(text='Убрать всё к чертям 🙅‍♂', callback_data='deleteBut'))
            await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
            await MailingStates.admin_mailing.set()

        elif msgtext == "/start":
            # bot.clear_step_handler(message)
            await start(message)

        else:
            # bot.clear_step_handler(message)
            await MailingStates.admin_mailing.set()

    user_id = message.chat.id
    c = conn.cursor(buffered=True)
    c.execute("select * from users where user_id = %s" % user_id)
    point = c.fetchone()
    if point is None:
        c.execute("insert into users (user_id, state) values (%s, %s)",
                  (user_id, 0))
        conn.commit()
    c.close()
    # bot.clear_step_handler(message)
    await admin_mailing(message)


@dp.message_handler(lambda message: message.text in [panel_custom,
                                                     panel_administrators,
                                                     statistics] and message.from_user.id == message.chat.id and message.from_user.id in admins)
async def take_massage_admin(message: types.Message):
    user_id = message.from_user.id
    if message.text == panel_custom:
        await bot.send_message(user_id, panel_custom,
                               reply_markup=menu_keyboard(user_id))
    elif message.text == panel_administrators:
        await bot.send_message(user_id, panel_administrators,
                               reply_markup=admin_keyboard)
    elif message.text == statistics:
        dbconfig = read_db_config()
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        c.execute('''SELECT COUNT(*) FROM users''')
        allusers = int(c.fetchone()[0])
        c.execute('''SELECT COUNT(*) FROM users WHERE lively = 1''')
        banned = int(c.fetchone()[0])
        c.close()
        conn.commit()
        lively = allusers - banned
        admin_text = '*🙂 Количество живых пользователей:* {0}\n' \
                     '*% от числа всех:* {1}%\n' \
                     '*💩 Количество заблокировавших:* {2}'.format(str(lively), str(round(lively / allusers * 100, 2)),
                                                                   str(banned))
        await bot.send_message(user_id, admin_text, parse_mode='Markdown', reply_markup=admin_keyboard)


@dp.message_handler(
    lambda message: message.text in [my_redirects, tree_btn] and message.from_user.id == message.chat.id)
async def take_massage(message: types.Message):
    user_id = message.from_user.id
    if message.text == my_redirects:
        keyboard = InlineKeyboardMarkup()
        dbconfig = read_db_config()
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        c.execute("SELECT DISTINCT telegram_channel_id FROM user_channel WHERE user_id = %s", (user_id,))
        telegram_channel_list = c.fetchall()
        if telegram_channel_list:
            for i in telegram_channel_list:
                try:
                    keyboard.row(
                        KeyboardButton((await bot.get_chat(chat_id=int(i[0])))['title'],
                                       callback_data=f"choose_telegram_{i[0]}"))
                except Exception as e:
                    print(e)
        keyboard.row(KeyboardButton("Добавить телеграмм канал 🖋", callback_data="add_telegram"))
        conn.commit()
        c.close()
        await bot.send_message(message.from_user.id, "📌Текущие перенаправления:", reply_markup=keyboard)
    elif message.text == tree_btn:
        dbconfig = read_db_config()
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        text = ""
        amount_telegram = 1
        amount_youtube = 1
        c.execute("SELECT DISTINCT telegram_channel_id FROM user_channel WHERE user_id = %s", (user_id,))
        telegram_channel_list = c.fetchall()
        for channel in telegram_channel_list:
            text += "• {0} #{1}\n".format((await bot.get_chat(chat_id=int(channel[0])))['title'], amount_telegram)
            amount_telegram += 1
            c.execute(
                "SELECT DISTINCT youtube_name FROM user_channel WHERE user_id = %s and telegram_channel_id = %s and youtube_channel_id IS NOT NULL",
                (user_id, channel[0]))
            youtube_channel_list = c.fetchall()
            for youtube in youtube_channel_list:
                text += "    - {0} #{1}\n".format(youtube[0], amount_youtube)
                amount_youtube += 1
        conn.commit()
        c.close()
        if text == "":
            await bot.send_message(user_id, "Пусто!")
        else:
            await bot.send_message(user_id, text)


@dp.callback_query_handler(state="*")
async def process_callback_messages(callback_query: types.CallbackQuery, state: FSMContext):
    '''Обработка callback запросов'''
    user_id = callback_query.from_user.id
    query_id = callback_query.id
    # CONNECT TO DATABASE
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    c = conn.cursor(buffered=True)
    try:
        message_id = callback_query.message.message_id
    except:
        message_id = callback_query.inline_message_id
    query_data = callback_query.data
    print(f'CallbackQuery: {user_id} -> {query_data}')
    start_data = query_data.split('_')[0]

    try:
        one_param = query_data.split('_')[1]
    except:
        one_param = None
    try:
        # something channel_id have symbol '_'
        two_param = query_data.split('_')[2:]
        two_param = '_'.join(two_param)
    except:
        two_param = None

    if 'hide' == start_data:
        # await state.finish()
        await bot.delete_message(user_id, message_id)
    elif "choose" == start_data:
        if one_param == "telegram":
            keyboard = InlineKeyboardMarkup()
            keyboard.row(KeyboardButton("Добавить YouTube канал🖋", callback_data=f"add_youtube"),
                         KeyboardButton("Изменить текст рассылки📄", callback_data=f"add_text"))
            c.execute(
                "SELECT DISTINCT youtube_name, youtube_channel_id FROM user_channel WHERE user_id = %s and telegram_channel_id = %s and youtube_channel_id IS NOT NULL",
                (user_id, two_param))
            youtube_channel_list = c.fetchall()
            if youtube_channel_list:
                for i in youtube_channel_list:
                    keyboard.row(
                        KeyboardButton(i[0], callback_data=f"choose_youtube_{i[1]}"))
            await state.update_data(telegram_channel_id=two_param)
            keyboard.row(KeyboardButton("Удалить телеграмм канал ❌", callback_data="delete_telegram"))
            keyboard.row(KeyboardButton("⬅Назад", callback_data=f"back_telegram"))
            await bot.edit_message_text(chat_id=user_id,
                                        text=f"📌Текущие перенаправления:\n      ➡{(await bot.get_chat(chat_id=int(two_param)))['title']}",
                                        message_id=message_id,
                                        reply_markup=keyboard)
        elif one_param == "youtube":
            keyboard = InlineKeyboardMarkup()
            keyboard.row(KeyboardButton("Удалить YouTube канал❌", callback_data=f"delete_youtube"))

            data = await state.get_data()
            telegram_channel_id = data.get("telegram_channel_id")
            print(telegram_channel_id)
            await state.update_data(youtube_channel_id=two_param)
            keyboard.row(KeyboardButton("⬅Назад", callback_data=f"choose_telegram_{telegram_channel_id}"))
            print(two_param)
            c.execute(
                "SELECT DISTINCT youtube_name FROM user_channel WHERE user_id = %s and telegram_channel_id = %s and youtube_channel_id =%s",
                (user_id, telegram_channel_id, two_param))
            youtube_name = c.fetchone()
            print(telegram_channel_id)
            await bot.edit_message_text(chat_id=user_id,
                                        text=f"📌Текущие перенаправления: \n       ➡{(await bot.get_chat(chat_id=int(telegram_channel_id)))['title']}➡{youtube_name[0]}",
                                        message_id=message_id,
                                        reply_markup=keyboard)
    elif "add" == start_data:
        if one_param == "telegram":
            await bot.send_message(user_id,
                                   "✏️Введите ID телеграмм канала (-100xxxxxxxxxx) или перешлите сообщение с канала:")
            await TelegramStates.id.set()
        elif one_param == "youtube":
            await bot.send_message(user_id,
                                   "✏Введите ссылку на YouTube канал или на видео с канала:\n\n<b>❗Допустимые значения</b>:\n<i>https://www.youtube.com/channel/UCUZHFZ9jIKrLroW8LcyJEQQ\nhttps://www.youtube.com/user/partnersupport\nhttps://www.youtube.com/watch?v=VKf6NF0OD5A&ab_channel=YouTubeCreators\nhttps://www.youtube.com/watch?v=VKf6NF0OD5A</i>",
                                   parse_mode="HTML", disable_web_page_preview=True)
            await YoutubeStates.url.set()
        elif one_param == "text":
            await bot.send_message(user_id,
                                   "✏️Введите текст рассылки:\n\n<b>Пример:</b>\nНа канале [name] вышло новое видео! Ссылка - [link]\n\n<i>[name]-маркер обозначающий, где будет находиться название канала <b>(не обязателен)</b>\n[link]-маркер обозначающий, где будет находиться ссылка на видео <b>(обязательный)</b></i>",
                                   parse_mode="HTML")
            await TextStates.text.set()
    elif "back" == start_data:
        if one_param == "telegram":
            keyboard = InlineKeyboardMarkup()
            c.execute("SELECT DISTINCT telegram_channel_id FROM user_channel WHERE user_id = %s", (user_id,))
            telegram_channel_list = c.fetchall()
            if telegram_channel_list:
                for i in telegram_channel_list:
                    try:
                        keyboard.row(
                            KeyboardButton((await bot.get_chat(chat_id=int(i[0])))['title'],
                                           callback_data=f"choose_telegram_{i[0]}"))
                    except Exception as e:
                        print(e)
            keyboard.row(KeyboardButton("Добавить телеграмм канал 🖋", callback_data="add_telegram"))
            await bot.edit_message_text(chat_id=user_id, text="📌Текущие перенаправления:", message_id=message_id,
                                        reply_markup=keyboard)
    elif "delete" == start_data:
        if one_param == "telegram":
            keyboard = InlineKeyboardMarkup().row(InlineKeyboardButton("Да", callback_data="confirm_delete"),
                                                  InlineKeyboardButton("Нет", callback_data="hide"))
            await bot.send_message(user_id, "Вы точно хотите удалить Telegram канал?", reply_markup=keyboard)

        elif one_param == "youtube":
            data = await state.get_data()
            telegram_channel_id = data.get("telegram_channel_id")
            youtube_channel_id = data.get("youtube_channel_id")
            # await state.finish()
            c.execute(
                "DELETE FROM user_channel WHERE user_id = %s and telegram_channel_id = %s and youtube_channel_id =%s",
                (user_id, telegram_channel_id, youtube_channel_id))
            keyboard = InlineKeyboardMarkup()
            keyboard.row(KeyboardButton("Добавить YouTube канал🖋", callback_data=f"add_youtube"),
                         KeyboardButton("Изменить текст рассылки📄", callback_data=f"add_text"))
            c.execute(
                "SELECT DISTINCT youtube_name, youtube_channel_id FROM user_channel WHERE user_id = %s and telegram_channel_id = %s and youtube_channel_id IS NOT NULL",
                (user_id, telegram_channel_id))
            youtube_channel_list = c.fetchall()
            if youtube_channel_list:
                for i in youtube_channel_list:
                    keyboard.row(
                        KeyboardButton(i[0], callback_data=f"choose_youtube_{i[1]}"))
            await state.update_data(telegram_channel_id=telegram_channel_id)
            keyboard.row(KeyboardButton("Удалить телеграмм канал 🖋", callback_data="delete_telegram"))
            keyboard.row(KeyboardButton("⬅Назад", callback_data=f"back_telegram"))
            await bot.edit_message_text(chat_id=user_id,
                                        text=f"📌Текущие перенаправления:\n      ➡{(await bot.get_chat(chat_id=int(telegram_channel_id)))['title']}",
                                        message_id=message_id,
                                        reply_markup=keyboard)
    elif "confirm" == start_data:
        if one_param == "delete":
            data = await state.get_data()
            telegram_channel_id = data.get("telegram_channel_id")
            c.execute("DELETE FROM user_channel WHERE user_id = %s and telegram_channel_id = %s",
                      (user_id, telegram_channel_id))
            # await state.finish()
            await bot.delete_message(user_id, message_id)
    elif 'editTextBut' == start_data:
        # bot.clear_step_handler(callback_query.message)
        await bot.send_message(user_id, "Введите текст для кнопки")
        # bot.register_next_step_handler(callback_query.message, process_editTextBut)
        await ProcessEditTextBut.text.set()

    elif 'editUrlBut' == start_data:
        # bot.clear_step_handler(callback_query.message)
        await bot.send_message(user_id, 'Введите ссылку 📝', reply_markup=mail_menu)
        await ProcessEditUrlBut.text.set()

    elif 'deleteBut' == start_data:
        c = conn.cursor(buffered=True)
        c.execute("""update users set butUrlMail = 0 where user_id = (%s)""", (user_id,))
        c.execute("""update users set butTextMail = 0 where user_id = (%s)""", (user_id,))
        conn.commit()
        c.close()
        await bot.send_message(user_id, 'Удалено! 🗑', reply_markup=mail_menu)
        await cheker(callback_query.message)

    elif 'editPhotoMail' == start_data:

        # bot.clear_step_handler(callback_query.message)
        await bot.send_message(user_id, 'Отправьте фотографию', reply_markup=mail_menu)
        await WaitPhoto.text.set()

    elif 'deletePhoto' == start_data:
        c = conn.cursor(buffered=True)
        c.execute("""update users set photoMail = 0 where user_id = (%s)""", (user_id,))
        conn.commit()
        c.close()
        await bot.send_message(user_id, 'Фото удалено! ✅', reply_markup=mail_menu)
        await cheker(callback_query.message)

    await bot.answer_callback_query(query_id)
    conn.commit()
    c.close()


@dp.message_handler(state=TelegramStates.id)
async def get_telegram_id(message: types.Message, state: FSMContext):
    def RepresentsInt(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    id = message.text
    if message.forward_from_chat:
        id = str(message.forward_from_chat.id)
    user_id = message.from_user.id
    if id in [my_redirects, tree_btn]:
        await state.finish()
        await take_massage(message)
    elif id in [admin_keyboard, panel_custom] and user_id in admins:
        await state.finish()
        await take_massage_admin(message)
    else:
        if id[0:4] == "-100" and RepresentsInt(id) and len(id) == 14:
            try:
                check_chat = await bot.get_chat(chat_id=int(id))
                dbconfig = read_db_config()
                conn = MySQLConnection(**dbconfig)
                c = conn.cursor(buffered=True)
                c.execute("INSERT INTO user_channel (user_id, telegram_channel_id) VALUES (%s, %s)",
                          (user_id, id))
                conn.commit()
                c.close()
                await bot.send_message(user_id, "Телеграмм канал успешно добавлен ✅")
                await state.finish()
            except ChatNotFound:
                await bot.send_message(user_id, "⭕️Канал не знайдено! Спробуйте еще раз:")
                await TelegramStates.id.set()

        else:
            await bot.send_message(user_id, "⭕️Спробуйте еще раз:")
            await TelegramStates.id.set()


@dp.message_handler(state=YoutubeStates.url)
async def get_telegram_id(message: types.Message, state: FSMContext):
    url = message.text
    user_id = message.from_user.id
    if url in [my_redirects, tree_btn]:
        await state.finish()
        await take_massage(message)
    elif url in [admin_keyboard, panel_custom] and user_id in admins:
        await state.finish()
        await take_massage_admin(message)
    else:
        url = url.replace(" ", "")
        url = url.replace("https://www.", "")
        print(url[0:11])
        print(len(url.split('/')))
        if url[0:11] == "youtube.com" and len(url.split('/')) == 3:
            dbconfig = read_db_config()
            conn = MySQLConnection(**dbconfig)
            c = conn.cursor(buffered=True)
            url = url.split('/')
            data = await state.get_data()
            telegram_channel_id = data.get("telegram_channel_id")
            if not telegram_channel_id:
                await bot.send_message(user_id,
                                       f"⛔Ошибка записи данных. Начните все с начала! (нажмите заново на кнопку <b>{my_redirects}</b>)",
                                       parse_mode="HTML")
                await state.finish()
                return False
            if url[1] == 'user':
                url[2] = get_id_from_user_id(API_KEY, url[1])
                if url[2] == False:
                    await bot.send_message(user_id, "⛔Ошибка!")
                    await state.finish()
                    return False
            c.execute("SELECT DISTINCT text FROM user_channel WHERE user_id = %s and telegram_channel_id = %s",
                      (user_id, telegram_channel_id))
            text = c.fetchone()
            if text:
                text = text[0]
                if not text:
                    text = "На канале [name] вышло новое видео!\nСсылка - [link]"
            else:
                text = "На канале [name] вышло новое видео!\nСсылка - [link]"
            youtube_name = get_name_channel_by_id(API_KEY, url[2])
            list_video_id = get_video_by_channelID(API_KEY, url[2])
            if list_video_id == False or youtube_name == False:
                await bot.send_message(user_id, "⛔Ошибка!")
                await state.finish()
                return False
            c.execute(
                "INSERT INTO user_channel (user_id, telegram_channel_id, youtube_channel_id, text, youtube_name) VALUES (%s, %s, %s, %s, %s)",
                (user_id, telegram_channel_id, url[2], text, youtube_name))
            if list_video_id:
                for i in list_video_id[::-1]:
                    c.execute(
                        "INSERT INTO video_channel (youtube_channel_id, video_id) VALUES (%s, %s)",
                        (url[2], i))
            conn.commit()
            c.close()
            await bot.send_message(user_id, "YouTube канал успешно добавлен ✅")
            await state.finish()
        else:
            if "watch?v=" in url or "&ab_channel=" in url:
                if "&ab_channel=" not in url:
                    video_id = url.split("watch?v=")[1]
                else:
                    video_id = url.split("watch?v=")[1].split("&ab_channel=")[0]
                print(video_id)
                channel_id = get_id_from_videoid(API_KEY, video_id)
                if channel_id == False:
                    await bot.send_message(user_id, "⛔Ошибка!")
                    await state.finish()
                    return False
                dbconfig = read_db_config()
                conn = MySQLConnection(**dbconfig)
                c = conn.cursor(buffered=True)
                data = await state.get_data()
                telegram_channel_id = data.get("telegram_channel_id")
                if not telegram_channel_id:
                    await bot.send_message(user_id,
                                           f"⛔Ошибка записи данных. Начните все с начала! (нажмите заново на кнопку <b>{my_redirects}</b>)",
                                           parse_mode="HTML")
                    await state.finish()
                    return False
                c.execute("SELECT DISTINCT text FROM user_channel WHERE user_id = %s and telegram_channel_id = %s",
                          (user_id, telegram_channel_id))
                text = c.fetchone()
                if text:
                    text = text[0]
                    if not text:
                        text = "На канале [name] вышло новое видео!\nСсылка - [link]"
                else:
                    text = "На канале [name] вышло новое видео!\nСсылка - [link]"
                youtube_name = get_name_channel_by_id(API_KEY, channel_id)
                list_video_id = get_video_by_channelID(API_KEY, channel_id)
                if list_video_id == False or youtube_name == False:
                    await bot.send_message(user_id, "⛔Ошибка!")
                    await state.finish()
                    return False
                c.execute(
                    "INSERT INTO user_channel (user_id, telegram_channel_id, youtube_channel_id, text, youtube_name) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, telegram_channel_id, channel_id, text, youtube_name))
                if list_video_id:
                    for i in list_video_id[::-1]:
                        c.execute(
                            "INSERT INTO video_channel (youtube_channel_id, video_id) VALUES (%s, %s)",
                            (channel_id, i))
                conn.commit()
                c.close()
                await bot.send_message(user_id, "YouTube канал успешно добавлен ✅")
                await state.finish()
            else:
                await bot.send_message(user_id, "⭕️Спробуйте еще раз:")
                await YoutubeStates.url.set()


@dp.message_handler(state=TextStates.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    text = message.text
    user_id = message.from_user.id
    data = await state.get_data()
    telegram_channel_id = data.get("telegram_channel_id")
    if text in [my_redirects, tree_btn]:
        await state.finish()
        await take_massage(message)
    elif text in [admin_keyboard, panel_custom] and user_id in admins:
        await state.finish()
        await take_massage_admin(message)
    else:
        if "[link]" in text:
            dbconfig = read_db_config()
            conn = MySQLConnection(**dbconfig)
            c = conn.cursor(buffered=True)
            c.execute("UPDATE user_channel SET text = %s WHERE user_id= %s and telegram_channel_id = %s",
                      (text, user_id, telegram_channel_id))
            conn.commit()
            c.close()
            await bot.send_message(user_id, "Текст успешно изменен ✅")
            await state.finish()
        else:
            await bot.send_message(user_id, "❗Не хватает обязательного параметра [link]. Попробуйте еще раз:")
            await TextStates.text.set()


@dp.message_handler(state=MailingStates.admin_mailing)
async def get_telegram_id(message: types.Message, state: FSMContext):
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    c = conn.cursor(buffered=True)
    chat_id = message.chat.id
    msgtext = message.text
    c.execute("""select textMail from users where user_id = %s""" % chat_id)
    textMailUser = str(c.fetchone()[0])
    c.execute("""select photoMail from users where user_id = %s""" % chat_id)
    photoMailUser = str(c.fetchone()[0])
    c.execute("""select butTextMail from users where user_id = %s""" % chat_id)
    butTextMail = str(c.fetchone()[0])
    c.execute("""select butUrlMail from users where user_id = %s""" % chat_id)
    butUrlMail = str(c.fetchone()[0])
    if msgtext == mail_but:
        await bot.send_message(chat_id, '*Вы попали в меню рассылки *📢\n\n'
                                        'Для возврата нажмите *{0}*\n\n'
                                        'Для отмены какой-либо операции нажмите /start\n\n'
                                        'Используйте *{1}* для предварительного просмотра рассылки, а *{2}* для начала'
                                        ' рассылки\n\n'
                                        'Текст рассылки поддерживает разметку *HTML*, то есть:\n'
                                        '<b>*Жирный*</b>\n'
                                        '<i>_Курсив_</i>\n'
                                        '<pre>`Моноширный`</pre>\n'
                                        '<a href="ссылка-на-сайт">[Обернуть текст в ссылку](test.ru)</a>'.format(
            backMail_but, preMail_but, startMail_but
        ),
                               parse_mode="markdown", reply_markup=mail_menu)
        await MailingStates.admin_mailing.set()

    elif msgtext == backMail_but:
        await bot.send_message(chat_id, backMail_but, reply_markup=admin_keyboard)
        # bot.clear_step_handler(message)

    elif msgtext == preMail_but:
        try:
            if butTextMail == '0' and butUrlMail == '0':
                if photoMailUser == '0':
                    await bot.send_message(chat_id, textMailUser, parse_mode='html', reply_markup=mail_menu)
                else:
                    await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                         reply_markup=mail_menu)
            else:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(text=butTextMail, url=butUrlMail))
                if photoMailUser == '0':
                    await bot.send_message(chat_id, textMailUser, parse_mode='html',
                                           reply_markup=keyboard)
                else:
                    await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                         reply_markup=keyboard)
        except:
            await bot.send_message(chat_id, "Упс..проверьте правильность введения данных")
        await MailingStates.admin_mailing.set()

    elif msgtext == startMail_but:
        c.execute("""update users set textMail = 0 where user_id = %s""" % chat_id)
        c.execute("""update users set photoMail = 0 where user_id = %s""" % chat_id)
        c.execute("""update users set butTextMail = 0 where user_id = %s""" % chat_id)
        c.execute("""update users set butUrlMail = 0 where user_id = %s""" % chat_id)
        user_ids = []
        c.execute("""select user_id from users""")
        user_id = c.fetchone()
        while user_id is not None:
            user_ids.append(user_id[0])
            user_id = c.fetchone()
        c.close()
        """
        mail_thread = threading.Thread(target=mailing, args=(
            user_ids, 0, 0, 0, chat_id, textMailUser, photoMailUser, butUrlMail, butTextMail))
        mail_thread.start()
        """
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                mailing(user_ids, 0, 0, 0, chat_id, textMailUser, photoMailUser, butUrlMail, butTextMail))
            await bot.send_message(chat_id, 'Рассылка началась!',
                                   reply_markup=admin_keyboard)
        except:
            pass
    elif textMail_but == msgtext:
        await bot.send_message(chat_id,
                               'Введите текст рассылки. Допускаются теги HTML. Для отмены ввода нажите /start',
                               reply_markup=mail_menu)
        await ProcessTextMailing.text.set()

    elif photoMail_but == msgtext:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton(text='Добавить фото 📝', callback_data='editPhotoMail'))
        keyboard.row(InlineKeyboardButton(text='Удалить фото ❌', callback_data='deletePhoto'))
        await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
        await MailingStates.admin_mailing.set()

    elif butMail_but == msgtext:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton(text='Изменить текст кнопки 📝', callback_data='editTextBut'))
        keyboard.row(InlineKeyboardButton(text='Изменить ссылку кнопки 🔗', callback_data='editUrlBut'))
        keyboard.row(InlineKeyboardButton(text='Убрать всё к чертям 🙅‍♂', callback_data='deleteBut'))
        await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
        await MailingStates.admin_mailing.set()

    elif msgtext == "/start":
        # bot.clear_step_handler(message)
        await state.finish()
        await start(message)
    else:
        # bot.clear_step_handler(message)
        await MailingStates.admin_mailing.set()


@dp.message_handler(state=ProcessTextMailing.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    chat_id = message.from_user.id
    if message.text:
        if message.text == "/start":
            await bot.send_message(chat_id, "Действие отменено")
        else:
            c = conn.cursor(buffered=True)
            c.execute("update users set textMail = (%s) where user_id = (%s)", (message.text,
                                                                                chat_id))
            conn.commit()
            c.close()
            await bot.send_message(chat_id, "Текст успешно установлен")
            await state.finish()
        await MailingStates.admin_mailing.set()


@dp.message_handler(state=ProcessEditTextBut.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    chat_id = message.from_user.id
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)
    c = conn.cursor(buffered=True)
    # c.execute("""update users set state = 0 where user_id = %s""" % (chat_id))
    c.execute("update users set butTextMail = (%s) where user_id = (%s)", (message.text,
                                                                           chat_id))
    conn.commit()
    c.close()
    await bot.send_message(chat_id, 'Текст кнопки обновлен! ✅', reply_markup=mail_menu)
    await state.finish()


@dp.message_handler(state=ProcessEditUrlBut.text)
async def get_telegram_id(message: types.Message, state: FSMContext):
    if message.text:
        chat_id = message.from_user.id
        dbconfig = read_db_config()
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        c.execute("update users set butUrlMail = (%s) where user_id = (%s)", (message.text,
                                                                              chat_id))
        conn.commit()
        c.close()
        await bot.send_message(chat_id, 'Ссылка кнопки обновлена! ✅', reply_markup=mail_menu)
        await state.finish()
        await cheker(message)


@dp.message_handler(state=CheckerState.check)
async def get_telegram_id(message: types.Message, state: FSMContext):
    dbconfig = read_db_config()
    conn = MySQLConnection(**dbconfig)

    async def admin_mailing(message: types.Message):
        chat_id = message.chat.id
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        msgtext = message.text
        c.execute("""select textMail from users where user_id = %s""" % chat_id)
        textMailUser = str(c.fetchone()[0])
        c.execute("""select photoMail from users where user_id = %s""" % chat_id)
        photoMailUser = str(c.fetchone()[0])
        c.execute("""select butTextMail from users where user_id = %s""" % chat_id)
        butTextMail = str(c.fetchone()[0])
        c.execute("""select butUrlMail from users where user_id = %s""" % chat_id)
        butUrlMail = str(c.fetchone()[0])
        if msgtext == mail_but:
            await bot.send_message(chat_id, '*Вы попали в меню рассылки *📢\n\n'
                                            'Для возврата нажмите *{0}*\n\n'
                                            'Для отмены какой-либо операции нажмите /start\n\n'
                                            'Используйте *{1}* для предварительного просмотра рассылки, а *{2}* для начала'
                                            ' рассылки\n\n'
                                            'Текст рассылки поддерживает разметку *HTML*, то есть:\n'
                                            '<b>*Жирный*</b>\n'
                                            '<i>_Курсив_</i>\n'
                                            '<pre>`Моноширный`</pre>\n'
                                            '<a href="ссылка-на-сайт">[Обернуть текст в ссылку](test.ru)</a>'.format(
                backMail_but, preMail_but, startMail_but
            ),
                                   parse_mode="markdown", reply_markup=mail_menu)
            await MailingStates.admin_mailing.set()

        elif msgtext == backMail_but:
            await bot.send_message(chat_id, backMail_but, reply_markup=admin_keyboard)
            # bot.clear_step_handler(message)

        elif msgtext == preMail_but:
            try:
                if butTextMail == '0' and butUrlMail == '0':
                    if photoMailUser == '0':
                        await bot.send_message(chat_id, textMailUser, parse_mode='html', reply_markup=mail_menu)
                    else:
                        await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                             reply_markup=mail_menu)
                else:
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton(text=butTextMail, url=butUrlMail))
                    if photoMailUser == '0':
                        await bot.send_message(chat_id, textMailUser, parse_mode='html',
                                               reply_markup=keyboard)
                    else:
                        await bot.send_photo(chat_id, caption=textMailUser, photo=photoMailUser, parse_mode='html',
                                             reply_markup=keyboard)
            except:
                await bot.send_message(chat_id, "Упс..проверьте правильность введения данных")
            await MailingStates.admin_mailing.set()

        elif msgtext == startMail_but:
            c.execute("""update users set textMail = 0 where user_id = %s""" % chat_id)
            c.execute("""update users set photoMail = 0 where user_id = %s""" % chat_id)
            c.execute("""update users set butTextMail = 0 where user_id = %s""" % chat_id)
            c.execute("""update users set butUrlMail = 0 where user_id = %s""" % chat_id)
            user_ids = []
            c.execute("""select user_id from users""")
            user_id = c.fetchone()
            while user_id is not None:
                user_ids.append(user_id[0])
                user_id = c.fetchone()
            c.close()
            """
            mail_thread = threading.Thread(target=mailing, args=(
                user_ids, 0, 0, 0, chat_id, textMailUser, photoMailUser, butUrlMail, butTextMail))
            mail_thread.start()
            """
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(
                    mailing(user_ids, 0, 0, 0, chat_id, textMailUser, photoMailUser, butUrlMail, butTextMail))
                await bot.send_message(chat_id, 'Рассылка началась!',
                                       reply_markup=admin_keyboard)
            except:
                pass

        elif textMail_but == msgtext:
            await bot.send_message(chat_id,
                                   'Введите текст рассылки. Допускаются теги HTML. Для отмены ввода нажите /start',
                                   reply_markup=mail_menu)
            await ProcessTextMailing.text.set()

        elif photoMail_but == msgtext:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton(text='Добавить фото 📝', callback_data='editPhotoMail'))
            keyboard.row(InlineKeyboardButton(text='Удалить фото ❌', callback_data='deletePhoto'))
            await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
            await MailingStates.admin_mailing.set()

        elif butMail_but == msgtext:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton(text='Изменить текст кнопки 📝', callback_data='editTextBut'))
            keyboard.row(InlineKeyboardButton(text='Изменить ссылку кнопки 🔗', callback_data='editUrlBut'))
            keyboard.row(InlineKeyboardButton(text='Убрать всё к чертям 🙅‍♂', callback_data='deleteBut'))
            await bot.send_message(chat_id, 'Выберите действие ⤵', reply_markup=keyboard)
            await MailingStates.admin_mailing.set()

        elif msgtext == "/start":
            # bot.clear_step_handler(message)
            await start(message)

        else:
            # bot.clear_step_handler(message)
            await MailingStates.admin_mailing.set()

    user_id = message.chat.id
    c = conn.cursor(buffered=True)
    c.execute("select * from users where user_id = %s" % user_id)
    point = c.fetchone()
    if point is None:
        c.execute("insert into users (user_id, state) values (%s, %s)",
                  (user_id, 0))
        conn.commit()
    c.close()
    # bot.clear_step_handler(message)
    await state.finish()
    await admin_mailing(message)


@dp.message_handler(state=WaitPhoto.text, content_types=['photo'])
async def get_telegram_id(message: types.Message, state: FSMContext):
    print("photo")
    chat_id = message.from_user.id
    if message.content_type == 'photo':
        dbconfig = read_db_config()
        conn = MySQLConnection(**dbconfig)
        c = conn.cursor(buffered=True)
        # msgphoto = message.json['photo'][0]['file_id']
        msgphoto = message.photo[0].file_id
        c.execute("""update users set photoMail = (%s) where user_id = (%s)""", (msgphoto, chat_id,))
        await bot.send_message(chat_id, 'Фото прикреплено! ✅', reply_markup=mail_menu)
        conn.commit()
        c.close()
        # bot.register_next_step_handler(message, cheker)
        await state.finish()
        await CheckerState.check.set()
    else:
        await bot.send_message(chat_id, "Упс...", reply_markup=mail_menu)
        await CheckerState.check.set()
        # bot.register_next_step_handler(message, cheker)


# send_msg = threading.Thread(target=send_video_to_channel)
# send_msg.start()
def repeat(coro, loop):
    asyncio.ensure_future(coro(), loop=loop)
    loop.call_later(360, repeat, coro, loop)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.call_later(360, repeat, send_video_to_channel, loop)
    executor.start_polling(dp, skip_updates=True)
