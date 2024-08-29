import json

import loguru
from telebot import types
from telebot.types import InlineKeyboardMarkup, ReplyKeyboardRemove

from models import User


class ValidationException(Exception):
    pass


class DialogClass:
    def __init__(
        self, bot, user, dialog_name, state, context, users_message=None, callback=None
    ):
        self.user = user
        self.state = state
        self.dialog_name = dialog_name
        self.users_message = users_message
        self.callback = callback
        self.bot = bot
        self.context = context

    states = {}

    def process_message(self):
        states_names = list(self.states.keys())
        next_state_index = states_names.index(self.state) + 1
        if next_state_index < len(self.states):
            next_state = f"@{states_names[next_state_index]}"
        else:
            next_state = None
        state_processor = self.states.get(self.state)
        if type(state_processor) != dict:
            dialog_class = state_processor
        else:
            for str_options in state_processor:
                options = str_options.split("__")
                if "" in options or self.callback in options:
                    dialog_class = state_processor[str_options]
                    break
            else:
                raise Exception("Ошибка обработки состояния с аргументом")
        state_processor_object = dialog_class(
            user=self.user,
            bot=self.bot,
            dialog_name=self.dialog_name,
            next_state=next_state,
            context=self.context,
            users_message=self.users_message,
            callback=self.callback,
        )
        try:
            state_processor_object.process()
        except ValidationException:
            state_processor_object.process_invalid()


class StateProcessorClass:
    def __init__(
        self,
        user,
        bot,
        dialog_name,
        next_state,
        context,
        users_message=None,
        callback=None,
    ):
        self.user = user
        self.bot = bot
        self.users_message = users_message
        self.callback = callback
        self.dialog_name = dialog_name
        self.next_state = next_state
        self.context = context

    invalid_message = "некорректный ответ"

    def is_valid(self):
        return True

    def process_invalid(self):
        self.send_message(message_text=self.invalid_message)

    reply_buttons = []

    def get_reply_buttons(self):
        return self.reply_buttons

    inline_buttons = {}

    def get_inline_buttons(self):
        return self.inline_buttons

    link_buttons = {}

    def get_link_buttons(self):
        return self.link_buttons

    text_message = ""

    def get_message_text(self):
        return self.text_message

    def get_keyboard(self):
        reply_buttons = self.get_reply_buttons()
        inline_buttons = self.get_inline_buttons()
        if reply_buttons != []:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = [types.KeyboardButton(button) for button in reply_buttons]
            markup.add(*buttons)
            return markup
        elif inline_buttons != {}:
            buttons = []
            for button_label in inline_buttons:
                if type(inline_buttons[button_label]) == str:
                    buttons.append(
                        [
                            types.InlineKeyboardButton(
                                text=inline_buttons[button_label],
                                callback_data=button_label,
                            )
                        ]
                    )
                else:
                    buttons.append(
                        [
                            types.InlineKeyboardButton(
                                text=inline_buttons[button_label]["text"],
                                url=inline_buttons[button_label]["url"],
                            )
                        ]
                    )
            reply_markup = InlineKeyboardMarkup(buttons)
            return reply_markup
        else:
            return types.ReplyKeyboardRemove()

    def send_message(self, user_id=None, message_text=None, keyboard=None):
        if user_id is None:
            user_id = self.user.id
        if message_text is None:
            message_text = self.get_message_text()
        if keyboard is None:
            self.bot.send_message(
                user_id,
                message_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        else:
            self.bot.send_message(
                user_id,
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
    document = None

    def send_document(self, document=None, user_id=None):
        if user_id is None:
            user_id = self.user.id
        if document is None:
            document = self.document
        self.bot.send_document(user_id, document=document)

    def change_user_state(self):
        if self.next_state[0] == "@":
            next_state = f"{self.dialog_name}__{self.next_state[1:]}"
        else:
            next_state = self.next_state
        User.set_state(self.user.id, next_state, self.user.username)

    def set_context(self, context):
        context_json = json.dumps(context)
        self.next_state = f"{self.next_state}__{context_json}"

    def business_logic(self):
        pass

    redirect_class = None
    redirect_next_state = None

    def process(self):
        if self.is_valid():
            self.business_logic()
            self.send_message(keyboard=self.get_keyboard())
            self.change_user_state()
            if self.document is not None:
                self.send_document()
            if self.redirect_class is not None:
                self.redirect_class(
                    user=self.user,
                    bot=self.bot,
                    dialog_name=self.dialog_name,
                    next_state=self.redirect_next_state,
                    context=self.context,
                    users_message=self.users_message,
                    callback=self.callback,
                ).process()

        else:
            raise ValidationException
