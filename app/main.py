from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .routers import auth, bikes, catalog, components, services


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="BikeCheck API",
    version="1.0.0",
    description="Backend for the BikeCheck iOS app: bikes, components and service records.",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(bikes.router)
app.include_router(components.router)
app.include_router(services.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
