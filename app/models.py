from .database import Base
from sqlalchemy import Column, Integer, String

class Example(Base):
    __tablename__ = 'example'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
