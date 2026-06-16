import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import jwt

from app.core.config import get_settings
from app.core.security import get_current_claims

router = APIRouter(prefix="/metabase", tags=["Metabase"])


@router.get("/embed-token")
def get_embed_token(
    dashboard_id: int = Query(..., description="Numeric ID of the Metabase dashboard to embed"),
    _claims: dict = Depends(get_current_claims),
) -> dict:
    """Return a signed iframe URL for embedding a Metabase dashboard.

    The caller must be authenticated. The returned URL is valid for 10 minutes
    and should be used directly as the `src` of an <iframe>.
    """
    settings = get_settings()

    if settings.metabase_secret_key == "change-me":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="METABASE_SECRET_KEY no está configurado. Configuralo en .env y habilitá Static Embedding en Metabase Admin → Embedding.",
        )

    payload = {
        "resource": {"dashboard": dashboard_id},
        "params": {},
        "exp": int(time.time()) + 600,
    }

    token = jwt.encode(payload, settings.metabase_secret_key, algorithm="HS256")
    iframe_url = f"{settings.metabase_site_url}/embed/dashboard/{token}#bordered=true&titled=true"

    return {"iframe_url": iframe_url, "expires_in": 600}
