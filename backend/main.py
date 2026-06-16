from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import watchlist, summary, chain, expiry, unusual

app = FastAPI(title="Options Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(watchlist.router, prefix="/api")
app.include_router(summary.router,   prefix="/api")
app.include_router(chain.router,     prefix="/api")
app.include_router(expiry.router,    prefix="/api")
app.include_router(unusual.router,   prefix="/api")
