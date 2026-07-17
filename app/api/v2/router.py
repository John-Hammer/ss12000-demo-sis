"""
Main router for SS12000 v2 API.
"""
from fastapi import APIRouter

from .organisations import router as organisations_router
from .persons import router as persons_router
from .groups import router as groups_router
from .duties import router as duties_router
from .activities import router as activities_router
from .deleted_entities import router as deleted_entities_router

router = APIRouter(tags=["SS12000 v2"])

# Include all entity routers
router.include_router(organisations_router)
router.include_router(persons_router)
router.include_router(groups_router)
router.include_router(duties_router)
router.include_router(activities_router)
router.include_router(deleted_entities_router)
