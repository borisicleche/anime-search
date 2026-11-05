from pydantic import BaseModel, Field


class Anime(BaseModel):
    id: str
    title: str
    synopsis: str = Field(
        description=(
            "short description of the main plot of anime, no more than 20 words"
        ),
        max_length=200,
    )
    genres: list[str]
    episodes: int
    ongoing: bool
