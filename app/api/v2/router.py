"""
Main router for SS12000 v2 API.
"""
from fastapi import APIRouter

from .organisations import router as organisations_router
from .persons import router as persons_router
from .groups import router as groups_router
from .duties import router as duties_router

router = APIRouter(tags=["SS12000 v2"])

# Include all entity routers
router.include_router(organisations_router)
router.include_router(persons_router)
router.include_router(groups_router)
router.include_router(duties_router)
