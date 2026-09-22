from fastapi import FastAPI

from app.api.routes.investigations import router as investigations_router
from app.db.database import Base, engine
from app.db import tables


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="RETRACE",
    description="Find the story behind the story.",
    version="0.1.0",
)


app.include_router(investigations_router)


from fastapi.staticfiles import StaticFiles

# Remove the root route and mount the frontend directory
import os
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

