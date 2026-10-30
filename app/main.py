"""
Fake SIS - SS12000 v2.1 API Implementation
A demo School Information System for Skolsköld testing.
"""
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import create_tables

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await create_tables()

    # Import and run seeder if needed
    from .seed.seeder import seed_database
    await seed_database()

    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "service": "fake_sis", "version": settings.api_version}


@app.get("/comvius/sample.zip")
async def comvius_sample():
    """
    Serve the anonymised Comvius export for the demo's migration wizard.

    Lives here rather than in the Skolsköld repo on purpose: names and
    personnummer are replaced, but the incident and referral free-text is a
    genuine extract, so it must not ship inside the product image that runs
    on every school's node. Only the demo fetches this.
    """
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    sample = Path(__file__).resolve().parent.parent / "comvius_anon.zip"
    if not sample.exists():
        raise HTTPException(status_code=404, detail="No Comvius sample on this instance")
    return FileResponse(
        sample, media_type="application/zip", filename="comvius_sample.zip"
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs": "/docs",
        "admin": "/admin/",
        "endpoints": {
            "auth": "/token",
            "organisations": "/v2/organisations",
            "persons": "/v2/persons",
            "groups": "/v2/groups",
            "duties": "/v2/duties",
        }
    }


# Import and include routers
from .auth.routes import router as auth_router
from .auth.dependencies import get_current_client
from .api.v2.router import router as api_v2_router
from .seed import seeder


async def scenario_gate(request: Request):
    """Register scenarios (seeder.SCENARIOS, the Tallviken per-school views):
    the same SS12000 API is mounted under /v2 (the base roster) and under
    /scenario/<name>/v2 (that "next state"); the instance reseeds itself
    when a request asks for a state it does not hold. A sync source whose
    base URL ends in /scenario/moved/v2 therefore sees the moved pupil, and
    one pointed back at /v2 sees the base roster again — no rebuild, no env
    var, no admin call (series C1, 2026-10-30)."""
    name = request.path_params.get("scenario", "base")
    try:
        await seeder.ensure_scenario(name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown register scenario {name!r}; this dataset has "
                   f"{sorted(seeder.SCENARIOS) or 'none'}")


@app.get("/scenario")
async def scenario_status():
    """Which register scenario this instance holds, and which it can show."""
    return {"scenario": seeder.current_scenario(),
            "available": ["base", *sorted(seeder.SCENARIOS)],
            "dataset": seeder.DATASET_STAMP}


@app.post("/scenario/{name}", dependencies=[Depends(get_current_client)])
async def scenario_set(name: str):
    """Flip the instance to register scenario ``name`` now (the URL prefix
    does the same lazily on the next sync; this is for a hand on the lever)."""
    try:
        await seeder.ensure_scenario(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown register scenario {name!r}")
    return await scenario_status()


app.include_router(auth_router)
app.include_router(api_v2_router, prefix="/v2",
                   dependencies=[Depends(scenario_gate)])
app.include_router(api_v2_router, prefix="/scenario/{scenario}/v2",
                   dependencies=[Depends(scenario_gate)])

# Admin UI at /admin/
from .database import sync_engine
from .admin import setup_admin
setup_admin(app, sync_engine)
