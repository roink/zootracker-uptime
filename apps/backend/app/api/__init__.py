"""Router modules for the Zoo Tracker API."""

from .animals import router as animals_router
from .auth import router as auth_router
from .contact import router as contact_router
from .images import router as images_router
from .location import router as location_router
from .sightings import router as sightings_router
from .site import router as site_router
from .users import router as users_router
from .visits import router as visits_router
from .zoos import router as zoos_router

__all__ = [
    "auth_router",
    "users_router",
    "zoos_router",
    "animals_router",
    "images_router",
    "visits_router",
    "location_router",
    "site_router",
    "sightings_router",
    "contact_router",
]
