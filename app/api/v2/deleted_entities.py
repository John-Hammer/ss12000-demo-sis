"""SS12000 /deletedEntities endpoint.

Response shape: paged flat list of {entityType, id, deletedAt}. The spec
leaves this shape partially open — this is our documented contract,
mirrored by the skolSköld client (verify against a real provider at
onboarding).
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.deleted_entity import DeletedEntity
from ...auth.dependencies import get_current_client
from ...schemas.common import paginate

router = APIRouter(prefix="/deletedEntities", tags=["Borttag"])


@router.get("")
async def list_deleted_entities(
    after: Optional[str] = Query(None),
    entities: Optional[List[str]] = Query(None),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    query = select(DeletedEntity).order_by(DeletedEntity.id)
    if entities:
        query = query.filter(DeletedEntity.entity_type.in_(entities))
    if after:
        from datetime import datetime
        from fastapi import HTTPException
        try:
            after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail={
                "code": "invalid_filter", "message": "after is not a valid timestamp"})
        query = query.filter(DeletedEntity.deleted_at > after_dt)

    result = await db.execute(query)
    rows = result.scalars().all()
    rows, next_token = paginate(rows, limit, pageToken)
    return {"data": [r.to_dict() for r in rows], "pageToken": next_token}
