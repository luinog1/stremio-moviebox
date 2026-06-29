from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

from server.routes import router as main_router
from server.settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
        limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
        follow_redirects=True,
        proxy=settings.PROXY_URL
    )
    yield
    await app.state.http_client.aclose()

app = FastAPI(
    title="MovieBox Stremio Addon",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)

@app.get("/logo.png")
async def get_logo():
    return FileResponse("assets/logo.png", media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host=settings.HOST, port=settings.PORT, reload=True)
