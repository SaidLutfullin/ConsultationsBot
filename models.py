import enum

from loguru import logger
from sqlalchemy import (Boolean, Column, Date, Enum, ForeignKey, Integer,
                        String, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import BASE_NAME, ADMINS

Base = declarative_base()
engine = create_engine(BASE_NAME, echo=True)


class AgeCategories(enum.Enum):
    ZERO_SIX = "от 0 до 6 месяцев"
    SIX_ONE_YEAR = "от 6 месяцев до года"
    OLDER_ONE_YEAR = "старше года"


class Service(Base):
    __tablename__ = "service"
    id = Column(Integer, primary_key=True)
    age_category = Column(Enum(AgeCategories), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    is_link = Column(Boolean, default=False, nullable=False)
    link = Column(String, nullable=True)

    appointments = relationship("Appointment", back_populates="service")


class Appointment(Base):
    __tablename__ = "appointment"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("service.id"))
    client_name = Column(String, nullable=False)
    problem_description = Column(String, nullable=False)
    request = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    username = Column(String, nullable=True)
    date = Column(Date, nullable=False)

    service = relationship("Service", back_populates="appointments")


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    state = Column(String, nullable=False)
    previous_state = Column(String)
    username = Column(String, nullable=False)

    @staticmethod
    def create_user(user_id):
        engine = create_engine(BASE_NAME, echo=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        user = session.query(User).filter_by(user_id=user_id).first()
        if user_id in ADMINS:
            initial_state = "admin_services__my_services"
        else:
            initial_state = "user_services__menu"
        if user:
            user.state = initial_state
        else:
            user = User(user_id=user_id, state=initial_state)
            session.add(user)
        session.commit()
        session.close()

    @staticmethod
    def get_or_create_user(user_id):
        try:
            engine = create_engine(BASE_NAME, echo=True)
            Session = sessionmaker(bind=engine)
            session = Session()

            user = session.query(User).filter_by(user_id=user_id).first()
            session.close()
            if user:
                return user
            else:
                new_user = User(user_id=user_id, state="initial")
                session.add(new_user)
                session.commit()
                return new_user
        except Exception as e:
            logger.error(e)

    @staticmethod
    def get_state(user_id):
        try:
            engine = create_engine(BASE_NAME, echo=True)
            Session = sessionmaker(bind=engine)
            session = Session()

            user = session.query(User).filter_by(user_id=user_id).first()
            session.close()
            return user.state
        except Exception as e:
            logger.error(e)

    @staticmethod
    def set_state(user_id, state, username):
        try:
            engine = create_engine(BASE_NAME, echo=True)
            Session = sessionmaker(bind=engine)
            session = Session()

            user = session.query(User).filter_by(user_id=user_id).first()
            user.previous_state = user.state
            user.state = state
            user.username = username
            session.commit()
        except Exception as e:
            logger.error(e)


if __name__ == "__main__":
    try:
        Base.metadata.create_all(engine)
        logger.success("База данных успешно создана!")
    except Exception as e:
        logger.error(f"Ошибка при создании базы данных {e}")
