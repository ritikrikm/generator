"""Application-specific exceptions."""


class AREError(Exception):
    """Base exception for Automation Repository Explorer."""


class ParserError(AREError):
    """Raised when a supported file cannot be parsed."""


class RepositoryScanError(AREError):
    """Raised when repository scanning fails."""


class GraphBuildError(AREError):
    """Raised when relationship graph construction fails."""
