import json

import telebot
from loguru import logger

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

    if command == "start":
        logger.success(user.id)
        if user.id in ADMINS:
            state_arguments = ["admin_services", "my_services"]
        else:
            state_arguments = ["user_services", "menu"]
    else:
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


@bot.message_handler(commands=["aes"])
def send_welcome(message):
    User.set_state(message.from_user.id, "admin_services__my_services")


@bot.message_handler(commands=["start"])
def send_welcome(message):
    routing(message.from_user, command="start")


@bot.message_handler(func=lambda message: True)
def message_router(message):
    routing(message.from_user, users_message=message.text)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    routing(call.from_user, callback=call.data)


if __name__ == "__main__":
    bot.infinity_polling()
