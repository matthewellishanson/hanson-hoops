from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

# existing CORSMiddleware — keep it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # (you can lock to your GH pages origin later)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# add this too to guarantee the header on ALL responses
@app.middleware("http")
async def add_cors_header_everywhere(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        # ensure even error responses include CORS
        response = JSONResponse({"detail": "internal error"}, status_code=500)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Vary"] = "Origin"
    return response

# ⬇️ import routers here ⬇️
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app.include_router(players_router)
app.include_router(teams_router)

@app.get("/cors-test")
def cors_test():
    return {"ok": True}

