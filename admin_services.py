from datetime import datetime
from io import BytesIO

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import BASE_NAME, LOGFILE
from dialog_classes import (DialogClass, StateProcessorClass,
                            ValidationException)
from models import AgeCategories, Appointment, Service

logger.add(LOGFILE, format="{time} {level} {message}", level="ERROR", rotation="400KB", compression="zip")

engine = create_engine(BASE_NAME, echo=True)
Session = sessionmaker(bind=engine)


class MyServices(StateProcessorClass):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_state = "@my_services_waiting_callback"

    text_message = "Список ваших услуг"

    def get_inline_buttons(self):
        try:
            session = Session()
            services = session.query(Service).all()

            buttons = {}
            for service in services:
                buttons[service.id] = service.name
            session.close()
            buttons["new_service"] = "Добавить новую"
            buttons["get_statistics"] = "Выгрузить список заявок"
            return buttons
        except Exception as e:
            logger.error(e)
            raise ValidationException


class SetNameService(StateProcessorClass):  # вход по коллбеку
    text_message = "Введите название услуги"


class SetDescription(StateProcessorClass):
    text_message = "Введите описание услуги"

    invalid_message = "Ошибка. Введите правильно название услуги"

    def is_valid(self):
        if self.callback is not None:
            return False
        if self.users_message is None:
            return False
        return True

    def business_logic(self):
        context = {
            "name": self.users_message,
        }
        self.set_context(context)


class SetAgeCategory(StateProcessorClass):
    text_message = "Для какой возрастной категории услуга?"
    inline_buttons = {category.name: category.value for category in AgeCategories}

    invalid_message = "Ошибка. Пожалуйста, введите описание."

    def is_valid(self):
        if self.users_message is None:
            return False
        else:
            return True

    def business_logic(self):
        self.context["description"] = self.users_message
        self.set_context(self.context)


class IsLink(StateProcessorClass):
    text_message = "Услуга-ссылка или услуга-запись?"
    inline_buttons = {
        "True": "Услуга-ссылка",
        "False": "услуга-запись",
    }

    invalid_message = "Похоже, вы не выбрали возрастную категорию. Пожалуйста выберите."

    def is_valid(self):
        if self.callback in [category.name for category in AgeCategories]:
            return True
        else:
            return False

    def business_logic(self):
        self.context["age_category"] = self.callback
        self.set_context(self.context)


def save_service(service_data):

    session = Session()
    if "service_id" in service_data:
        service = session.query(Service).get(service_data["service_id"])

        service.age_category = service_data["age_category"]
        service.name = service_data["name"]
        service.description = service_data["description"]
        service.is_link = service_data["is_link"]
        service.link = service_data["link"]
    else:
        new_user = Service(
            age_category=service_data["age_category"],
            name=service_data["name"],
            description=service_data["description"],
            is_link=service_data["is_link"],
            link=service_data["link"],
        )
        session.add(new_user)
    session.commit()


class WaitingForIsLink(StateProcessorClass):

    def is_valid(self):
        if self.callback in list(IsLink.inline_buttons.keys()):
            return True
        else:
            return False

    def business_logic(self):

        self.is_link = True if self.callback == "True" else False
        self.context["is_link"] = self.is_link

        if self.is_link:
            self.text_message = "Введите ссылку"
            self.set_context(self.context)
        else:
            try:
                self.context["link"] = None
                save_service(self.context)
                self.text_message = "Услуга сохранена успешно"
            except Exception as e:
                logger.error(e)
                self.text_message = "Ошибка сохранения услуги"
            finally:
                self.redirect_class = MyServices


class WaitingForLink(StateProcessorClass):

    redirect_class = MyServices

    invalid_message = "Ошибка. Пришлите верную ссылку."

    def is_valid(self):
        if self.users_message is None:
            return False
        else:
            return True

    def business_logic(self):
        self.context["is_link"] = True
        self.context["link"] = self.text_message
        try:
            save_service(self.context)
            self.text_message = "Услуга сохранена успешно"
        except Exception as e:
            logger.error(e)
            self.text_message = "Ошибка сохранения услуги"


class GetStatistics(StateProcessorClass):  # вход по коллбеку
    text_message = "Введите дату, с которой выгрузить список заявок. Формат даты: DD.MM.YYYY. Например: 01.01.2024"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_state = "@waiting_for_date"

    def get_reply_buttons(self):
        session = Session()
        min_date = (
            session.query(Appointment)
            .order_by(Appointment.date)
            .first()
            .date.strftime("%d.%m.%Y")
        )
        return [min_date]


class WaitingForDate(StateProcessorClass):
    text_message = "Введите дату, до которой выгрузить список заявок."

    invalid_message = "Неверный формат даты. Введите корректную дату."

    def is_valid(self):
        if self.users_message is None:
            return False
        try:
            datetime.strptime(self.users_message, "%d.%m.%Y")
            return True
        except ValueError:
            return False

    def get_reply_buttons(self):
        return [datetime.today().date().strftime("%d.%m.%Y")]

    def business_logic(self):
        self.context["since_date"] = self.users_message
        self.set_context(self.context)


class SendingStatistics(StateProcessorClass):

    text_message = "Теперь вы можете скачать документ."
    redirect_class = MyServices

    invalid_message = "Неверный формат даты. Введите корректную дату."

    def is_valid(self):
        if self.users_message is None:
            return False
        try:
            datetime.strptime(self.users_message, "%d.%m.%Y")
            return True
        except ValueError:
            return False

    def business_logic(self):
        since_date = datetime.strptime(self.context["since_date"], "%d.%m.%Y")
        until_date = datetime.strptime(self.users_message, "%d.%m.%Y")

        session = Session()
        try:
            appointments = (
                session.query(Appointment)
                .filter(Appointment.date > since_date, Appointment.date < until_date)
                .all()
            )
            data = [
                {
                    "Алиас": appointment.username,
                    "Имя": appointment.client_name,
                    "Услуга": appointment.service.name,
                    "Описание проблемы": appointment.problem_description,
                    "Запрос": appointment.request,
                    "Номер телефона": appointment.phone_number,
                    "Дата": appointment.date.strftime("%d.%m.%Y"),
                }
                for appointment in appointments
            ]
            session.close()

            df = pd.DataFrame(data)
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            excel_buffer.seek(0)
            excel_buffer.name = "Запись на консультации.xlsx"
            self.document = excel_buffer
        except Exception as e:
            logger.error(e)
            self.invalid_message = "Ошибка создания документа"


class SelectService(StateProcessorClass):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_state = "@edit_delete_service"

    invalid_message = "Ошибка. Выберите пункт из меню."

    def is_valid(self):
        if self.callback is None or not self.callback.isdigit():  #'NoneType' object has no attribute 'isdigit'
            return False
        return True

    inline_buttons = {
        "edit_service": "Редактировать",
        "delete_service": "Удалить",
        "back": "Назад",
    }

    def business_logic(self):
        session = Session()
        try:
            service = session.query(Service).get(self.callback)
            self.text_message = f"<b>Название услуги:</b> {service.name}\n<b>Описание:</b>\n{service.description}\n<b>Возрастная категория:</b>{service.age_category.value}"
            if service.is_link:
                self.text_message += f"\n<b>Ссылка:</b>\n{service.link}"

            self.set_context(
                {
                    "service_id": service.id,
                    "name": service.name,
                    "description": service.description,
                    "age_category": service.age_category.name,
                    "is_link": service.is_link,
                    "link": service.link,
                }
            )
        except:
            raise ValidationException
        finally:
            session.close()


class DeleteService(StateProcessorClass):# вход по колбеку
    redirect_class = MyServices

    def business_logic(self):
        try:
            session = Session()
            service = session.query(Service).get(self.context["service_id"])
            session.delete(service)
            session.commit()
            self.text_message = "Услуга успешно удалена"
        except Exception as e:
            logger.error(e)
            self.text_message = "Ошибка удаления услуги"


class SetNewService(SetNameService):  # вход по колбеку

    inline_buttons = {"save_previous": "Сохранить прежнее название"}

    def business_logic(self):
        message = f"<b>Прежнее название услуги:</b>\n{self.context['name']}"
        self.send_message(message_text=message)
        self.set_context(self.context)


class SetNewDescription(SetDescription):

    inline_buttons = {"save_previous": "Сохранить прежнее описание"}

    invalid_message = "Ошибка. Введите название услуги."

    def is_valid(self):
        if (
            self.callback == "save_previous" or self.users_message is not None
        ):  # 'NoneType' object has no attribute 'isdigit'
            return True
        return False

    def business_logic(self):
        if self.callback != "save_previous":
            self.context["name"] = self.users_message
        self.set_context(self.context)
        message = f"<b>Прежнее описание услуги:</b>\n{self.context['description']}"
        self.send_message(message_text=message)


class SetNewAgeCategory(SetAgeCategory):
    invalid_message = "Ошибка. Введите описание."

    def is_valid(self):
        if (
            self.callback == "save_previous" or self.users_message is not None
        ):  # 'NoneType' object has no attribute 'isdigit'
            return True
        return False

    def business_logic(self):
        if self.callback != "save_previous":
            self.context["description"] = self.users_message
        self.set_context(self.context)

        old_category = AgeCategories[self.context["age_category"]].value
        message = f"<b>Прежняя возрастная категория:</b>\n{old_category}"
        self.send_message(message_text=message)
        self.inline_buttons["save_previous"] = "Сохранить прежнюю возрастную категорию"


class NewIsLink(IsLink):

    def is_valid(self):
        if self.callback == "save_previous" or self.callback in [
            category.name for category in AgeCategories
        ]:
            return True
        else:
            return False

    def business_logic(self):
        if self.callback != "save_previous":
            if self.callback in [category.name for category in AgeCategories]:
                self.context["age_category"] = self.callback
        self.set_context(self.context)


class NewWaitingForIsLink(WaitingForIsLink):  # валидатор унаследован
    def business_logic(self):
        super().business_logic()
        if self.is_link:
            self.inline_buttons = {"save_previous": "Сохранить прежнюю ссылку"}


class NewWaitingForLink(WaitingForLink):
    redirect_class = MyServices

    def is_valid(self):
        if (
            self.callback == "save_previous" or self.users_message is not None
        ):  # 'NoneType' object has no attribute 'isdigit'
            return True
        return False

    def business_logic(self):

        self.context["is_link"] = True
        if self.callback != "save_previous":
            self.context["link"] = self.users_message
        try:
            save_service(self.context)
            self.text_message = "Услуга сохранена успешно"
        except Exception as e:
            logger.error(e)
            self.text_message = "Ошибка сохранения услуги"


class AdminServices(DialogClass):
    states = {
        "my_services": MyServices,
        "my_services_waiting_callback": {
            "new_service": SetNameService,
            "get_statistics": GetStatistics,
            "": SelectService,
        },
        "set_description": SetDescription,
        "set_age_category": SetAgeCategory,
        "is_link": IsLink,
        "waiting_for_is_link": WaitingForIsLink,
        "waiting_for_link": WaitingForLink,
        "edit_delete_service": {
            "delete_service": DeleteService,
            "edit_service": SetNewService,
            "back": MyServices,
            "": MyServices,
        },
        "set_new_description": SetNewDescription,
        "set_new_age_category": SetNewAgeCategory,
        "new_is_link": NewIsLink,
        "new_waiting_for_is_link": NewWaitingForIsLink,
        "new_waiting_for_link": NewWaitingForLink,
        "waiting_for_date": WaitingForDate,
        "sending_statistics": SendingStatistics,
    }
