from fastapi import FastAPI

from src.tasks.task_router import task_router
from src.user.user_router import user_router
from src.utils.db import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(task_router)
app.include_router(user_router)
