"""One module per job platform. Each knows its feed's address and how to read its JSON."""

from .ashby import Ashby
from .greenhouse import Greenhouse
from .lever import Lever

SOURCES = {source.platform: source for source in (Greenhouse(), Lever(), Ashby())}

__all__ = ["SOURCES", "Ashby", "Greenhouse", "Lever"]
