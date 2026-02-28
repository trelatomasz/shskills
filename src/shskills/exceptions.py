"""Exceptions for shskills."""


class ShskillsError(Exception):
    """Base exception for all shskills errors."""


class FetchError(ShskillsError):
    """Failed to fetch skills from a remote repository."""


class ValidationError(ShskillsError):
    """A skill directory failed structural validation."""


class InstallError(ShskillsError):
    """Installation could not be completed."""


class ManifestError(ShskillsError):
    """Failed to read or write the manifest file."""


class ConfigError(ShskillsError):
    """Invalid configuration or CLI arguments."""
