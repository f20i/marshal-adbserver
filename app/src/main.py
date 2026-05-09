from os import getenv
import logging
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .routers import healthz_router
from .register import register
from .cleanup import cleanup

from marshal_adbserver_k8s import Settings as K8sSettings, K8sManager
from marshal_database import make_engine, make_session_factory

logging.basicConfig(level=logging.INFO)

engine = make_engine(getenv("DATABASE_URL"))
session_factory = make_session_factory(engine)

k8s_settings = K8sSettings()
k8s_manager = K8sManager(k8s_settings)
k8s_manager.configure()
k8s_manager.prepare()

@asynccontextmanager
async def lifespan(app: FastAPI):
    adb_service = None
    if getenv("ENV") == "production":
        adb_service = k8s_manager.create_service()
    register(session_factory, k8s_manager, adb_service=adb_service)
    yield
    cleanup(session_factory)

app = FastAPI(lifespan=lifespan)
app.include_router(healthz_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)