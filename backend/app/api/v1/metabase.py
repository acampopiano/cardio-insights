import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import jwt

from app.core.config import get_settings
from app.core.security import get_current_claims

router = APIRouter(prefix="/metabase", tags=["Metabase"])


@router.get("/embed-token")
def get_embed_token(
    dashboard_id: int | None = Query(
        default=None,
        description="Numeric ID of the Metabase dashboard to embed. Defaults to METABASE_DEFAULT_DASHBOARD_ID.",
    ),
    _claims: dict = Depends(get_current_claims),
) -> dict:
    """Return a signed iframe URL for embedding a Metabase dashboard.

    The caller must be authenticated. The URL uses Metabase static embedding
    (a JWT signed with the embedding secret key) and should be used directly as
    the `src` of an <iframe>.
    """
    settings = get_settings()

    if settings.metabase_secret_key == "change-me":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="METABASE_SECRET_KEY no está configurado. Configuralo en .env y habilitá Static Embedding en Metabase Admin → Embedding.",
        )

    resolved_dashboard_id = dashboard_id or settings.metabase_default_dashboard_id
    ttl = settings.metabase_embed_token_ttl_seconds

    payload = {
        "resource": {"dashboard": resolved_dashboard_id},
        "params": {},
        "exp": int(time.time()) + ttl,
    }

    token = jwt.encode(payload, settings.metabase_secret_key, algorithm="HS256")
    # titled=false: el título ya lo muestra el frontend.
    # background=false + bordered=false: el embed se integra mejor con el layout de la app.
    # downloads=true: permite exportar resultados desde el chrome de Metabase (CSV/XLSX/PNG).
    iframe_url = (
        f"{settings.metabase_site_url}/embed/dashboard/{token}"
        f"#bordered=false&titled=false&background=false&downloads=true"
    )

    return {
        "iframe_url": iframe_url,
        "dashboard_id": resolved_dashboard_id,
        "expires_in": ttl,
    }
