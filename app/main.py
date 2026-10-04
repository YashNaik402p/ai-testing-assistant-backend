from fastapi import FastAPI

from app.database import Base, engine
from app import models  # noqa: F401  (import ensures models are registered on Base.metadata)
from app.routers import auth, project, source_code, analysis, chat, project_analysis

app = FastAPI(
    title="AI-Powered Software Testing Assistant",
    description="AI-assisted code analysis, test case generation, security review, and documentation.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(project.router)
app.include_router(source_code.router)
app.include_router(analysis.router)
app.include_router(chat.router)
app.include_router(project_analysis.router)


@app.on_event("startup")
def on_startup():
    # Dev convenience: create tables if they don't exist.
    # Once we add Alembic migrations, this will be replaced by `alembic upgrade head`.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}

#==============================================================================
#Cors
#==============================================================================

from fastapi.middleware.cors import CORSMiddleware

# Initialize your FastAPI app

# 1. Define the origins that are allowed to connect to your backend.
# If you are just opening the HTML file in your browser, you might need to use "*" for development.
# If you are using a local server (like Live Server in VS Code), it might be "http://127.0.0.1:5500".
origins = [
    "http://localhost",
    "https://ai-testing-assistant-frontend.onrender.com",
    "http://localhost:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "*" # Note: "*" allows all origins. Good for quick local testing, but restrict this in production!
]

# 2. Add the middleware to your app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers (including Authorization for your JWT)
)

# ... the rest of your routes and application logic below ...