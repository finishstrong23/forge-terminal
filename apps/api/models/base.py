from sqlalchemy.orm import DeclarativeBase
import uuid


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())
