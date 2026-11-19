from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.utils.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(url=settings.DB_CONNECTION_STRING)

LocalSession = sessionmaker(bind=engine)


def get_db():
    session = LocalSession()
    try:
        yield session
    finally:
        session.close()
