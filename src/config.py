from pydantic import BaseModel


class EnvironmentConfig(BaseModel):
    watched_message: int
    given_role_t1: int
    given_role_t2: int
    debug_channel: int
    guild_id: int
    automatic_role_t2_waittime: int
    automatic_role_t2: bool
    grube_channel: int
    sticker_names: dict[str, str]
    event_role_message: int
    event_role: int
    afd_role: int
    afd_react_message: int
    afd_green_role: int
    afd_orange_role: int
    spoiler_tiers_map: dict[str, int]
    gooey_id: int
    pluralkit_member: int | None = None
    pluralkit_role: int | None = None


class Configuration(BaseModel):
    version: str
    debug: EnvironmentConfig
    live: EnvironmentConfig
