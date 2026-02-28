"""shskills — install agent skills from GitHub repositories."""

from shskills._version import __version__
from shskills.core.installer import doctor, install
from shskills.core.manifest import installed_skills
from shskills.core.planner import list_skills

__all__ = [
    "__version__",
    "install",
    "list_skills",
    "installed_skills",
    "doctor",
]
