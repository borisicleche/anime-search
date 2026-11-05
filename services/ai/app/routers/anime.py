from fastapi import APIRouter, HTTPException

from app.models import Anime

router = APIRouter(prefix="/anime", tags=["anime"])

# Temporary in-memory data until a real data source is wired up
ANIME_BY_ID: dict[str, Anime] = {
    "cowboy-bebop": Anime(
        id="cowboy-bebop",
        title="Cowboy Bebop",
        synopsis=(
            "A ragtag crew of bounty hunters drifts through space chasing "
            "criminals while their pasts catch up with them."
        ),
        genres=["Action", "Sci-Fi", "Drama"],
        episodes=26,
        ongoing=False,
    ),
}


@router.get("/{anime_id}")
async def get_anime(anime_id: str) -> Anime:
    anime = ANIME_BY_ID.get(anime_id)
    if anime is None:
        raise HTTPException(status_code=404, detail="Anime not found")
    return anime
