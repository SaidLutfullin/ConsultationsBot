import json

import telebot
from loguru import logger
from telebot.types import BotCommand

from admin_services import AdminServices
from config import ADMINS, BOT_TOKEN
from models import User
from user_services import UserServices

bot = telebot.TeleBot(BOT_TOKEN)

dialog_classes_router = {
    "admin_services": AdminServices,
    "user_services": UserServices,
}

def routing(user, users_message=None, callback=None, command=None):

    state_arguments = User.get_state(user.id).split("__")

    context = json.loads(state_arguments[2]) if len(state_arguments) > 2 else {}
    state = state_arguments[1] if len(state_arguments) > 1 else None

    state_processor = dialog_classes_router[state_arguments[0]]
    if type(state_processor) != dict:
        dialog_class = state_processor
    else:
        for str_options in state_processor:
            options = str_options.split("__")
            if "" in options or callback in options:
                dialog_class = state_processor[str_options]
                break
        else:
            raise Exception("Ошибка обработки состояния с аргументом")
    dialog_class(
        bot=bot,
        user=user,
        dialog_name=state_arguments[0],
        state=state,
        context=context,
        users_message=users_message,
        callback=callback,
    ).process_message()


def update_commands(user_id):
    commands = [
        BotCommand(command="/menu", description="Меню"),
    ]
    if user_id in ADMINS:
        commands.append(BotCommand(command="/admin_menu", description="Меню администратора"))
    bot.set_my_commands(commands)


@bot.message_handler(commands=["start"])
def send_welcome(message):
    update_commands(message.from_user.id)
    User.create_user(message.from_user.id)
    routing(message.from_user, command="menu")


@bot.message_handler(commands=["menu"])
def send_welcome(message):
    User.set_state(message.from_user.id, "user_services__menu")
    routing(message.from_user, command="menu")


@bot.message_handler(commands=["admin_menu"])
def send_welcome(message):
    if message.from_user.id in ADMINS:
        User.set_state(message.from_user.id, "admin_services__my_services")
        routing(message.from_user, command="menu")


@bot.message_handler(func=lambda message: True)
def message_router(message):
    routing(message.from_user, users_message=message.text)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    routing(call.from_user, callback=call.data)


if __name__ == "__main__":
    bot.infinity_polling()
