import re
from datetime import datetime

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import ADMINS, BASE_NAME, LOGFILE
from dialog_classes import (DialogClass, StateProcessorClass,
                            ValidationException)
from models import AgeCategories, Appointment, Service

logger.add(LOGFILE, format="{time} {level} {message}", level="ERROR", rotation="400KB", compression="zip")

engine = create_engine(BASE_NAME, echo=True)
Session = sessionmaker(bind=engine)


class Menu(StateProcessorClass):
    text_message = """Здравствуйте!
Вы присоединились к боту помощнику Гузель Хаметовой.

Я помогу вам записаться на консультацию или приобрести вебинар.

Если у вас есть вопросы, пишите @Guzel_Khametova

Отзывы вы можете прочитать тут 
https://t.me/otzyv_mre"""
    inline_buttons = {"get_consultation": "Начать"}


class SelectAgeCategory(StateProcessorClass):
    text_message = "Выберите возраст вашего ребёнка"
    inline_buttons = {category.name: category.value for category in AgeCategories}

    def business_logic(self):
        if self.callback != "get_consultation":
            self.text_message = Menu.text_message
            self.inline_buttons = Menu.inline_buttons
            self.next_state = "@menu"


class SelectService(StateProcessorClass):
    text_message = "Выберите проблему"

    invalid_message = "Похоже, вы не выбрали возрастную категорию. Пожалуйста выберите."

    def is_valid(self):
        if self.callback in [category.name for category in AgeCategories]:
            return True
        else:
            return False

    def get_inline_buttons(self):
        session = Session()
        try:
            services = session.query(Service).filter_by(age_category=self.callback)
            inline_buttons = {}
            for service in services:
                inline_buttons[service.id] = service.name
            return inline_buttons
        except Exception as e:
            logger.error(e)
            self.text_message = "Ошибка!"
            self.redirect_class = Menu
            return None
        finally:
            session.close()


class ShowService(StateProcessorClass):

    invalid_message = "Ошибка. Пожалуйста, выберите проблему."

    def is_valid(self):
        if (
            self.callback is not None and self.callback.isdigit()
        ):  # 'NoneType' object has no attribute 'isdigit'

            return True
        return False

    def business_logic(self):

        session = Session()
        try:
            service_id = self.callback
            self.service = session.query(Service).get(service_id)
        except:
            raise ValidationException
        finally:
            session.close()

    def get_message_text(self):
        text_message = f"<b>{self.service.name}</b>\n<b>Описание:</b>\n{self.service.description}\n<b>Возрастная категория: </b>{self.service.age_category.value}"
        return text_message

    def get_inline_buttons(self):
        if self.service.is_link:
            inline_buttons = {
                "link": {"text": "перейти по ссылке", "url": self.service.link},
                "menu": "Вернуться в меню"
            }
            self.next_state = "@menu"
        else:
            inline_buttons = {f"appoint__{self.callback}": "записаться"}
        return inline_buttons


class WhatIsName(StateProcessorClass):
    text_message = "Как Вас зовут?"

    invalid_message = 'Чтобы записаться нажмите на кнопку "записаться", чтобы вернуться в начало нажмите /menu'

    def is_valid(self):
        pattern = r"^appoint__[1-9]\d*$"
        if self.callback is not None and re.match(pattern, self.callback) is not None:
            return True
        return False

    def business_logic(self):
        self.context["service_id"] = self.callback.split("__")[1]
        self.set_context(self.context)


class DescribeProblem(StateProcessorClass):
    text_message = "Опишите Вашу проблему"

    invalid_message = "Ошибка. Пожалуйста, введите Ваше имя."

    def is_valid(self):
        if self.users_message is None:
            return False
        else:
            return True

    def business_logic(self):
        self.context["name"] = self.users_message
        self.set_context(self.context)


class DescribeRequest(StateProcessorClass):
    text_message = "Опишите Ваш запрос. Каких результатов Вы хотели бы достичь?"

    invalid_message = "Ошибка. Пожалуйста, введите описание проблемы."

    def is_valid(self):
        if self.users_message is None:
            return False
        else:
            return True

    def business_logic(self):
        self.context["problem"] = self.users_message
        self.set_context(self.context)


class SetPhoneNumber(StateProcessorClass):
    text_message = "Напишите Ваш номер телефона"

    invalid_message = "Ошибка. Пожалуйста, опишите Ваш запрос."

    def is_valid(self):
        if self.users_message is None:
            return False
        else:
            return True

    def business_logic(self):
        self.context["request"] = self.users_message
        self.set_context(self.context)


class Agreement(StateProcessorClass):
    text_message = "Я согласен(сна), что результат может быть достигнут только если соблюдать все рекомендации"

    inline_buttons = {"agree": "Согласен(сна)"}

    invalid_message = "Ошибка. Пожалуйста, введите номер телефона."

    def is_valid(self):
        if self.users_message is None:
            return False
        else:
            return True

    def business_logic(self):
        self.context["phone_number"] = self.users_message
        self.set_context(self.context)


class Appoint(StateProcessorClass):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_state = "@menu"

    invalid_message = (
        "Чтобы записаться дайте согласие, чтобы вернуться в начало нажмите /menu"
    )

    def is_valid(self):
        if self.callback != "agree":
            return False
        else:
            return True

    def business_logic(self):
        message_text = f"<b>Поступила заявка на консультацию</b>\n<b>Имя клиента:</b> {self.context['name']}\n<b>Алиас:</b> @{self.user.username}\n<b>Описание проблемы:</b>\n{self.context['problem']}\n<b>Запрос:</b>\n{self.context['request']}\n<b>Номер телефона:</b>\n{self.context['phone_number']}"
        self.send_message(user_id=ADMINS[0], message_text=message_text)
        self.text_message = "Ваша заявка принята, в ближайшее время я с Вами свяжусь"
        try:
            session = Session()
            new_user = Appointment(
                service_id=self.context["service_id"],
                client_name=self.context["name"],
                problem_description=self.context["problem"],
                request=self.context["request"],
                phone_number=self.context["phone_number"],
                username=self.user.username,
                date=datetime.today().date(),
            )
            session.add(new_user)
            session.commit()
        except Exception as e:
            logger.error(e)
        finally:
            self.redirect_class = Menu
            self.redirect_next_state = "@menu"


class UserServices(DialogClass):
    states = {
        "menu": Menu,
        "select_age_category": SelectAgeCategory,
        "select_service": SelectService,
        "show_service": ShowService,
        "what_is_name": WhatIsName,
        "describe_problem": DescribeProblem,
        "describe_request": DescribeRequest,
        "set_phone_number": SetPhoneNumber,
        "agreement": Agreement,
        "appoint": Appoint,
    }
