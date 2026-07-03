from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, events, execution, folders, ingredients, orders, products, roles, users

app = FastAPI(title="Karavay Production Console")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
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


@app.get("/health")
async def health():
    return {"status": "ok"}
