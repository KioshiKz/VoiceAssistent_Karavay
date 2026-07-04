from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, events, execution, folders, ingredients, orders, products, roles, users, voice

app = FastAPI(title="Karavay Production Console")

frontend_origins = {
    settings.frontend_origin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
if "localhost" in settings.frontend_origin:
    frontend_origins.add(settings.frontend_origin.replace("localhost", "127.0.0.1"))
if "127.0.0.1" in settings.frontend_origin:
    frontend_origins.add(settings.frontend_origin.replace("127.0.0.1", "localhost"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(frontend_origins),
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(folders.router)
app.include_router(ingredients.router)
app.include_router(events.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(execution.router)
app.include_router(voice.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
