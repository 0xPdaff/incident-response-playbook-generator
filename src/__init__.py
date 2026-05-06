# Incident Response Playbook Generator
"""AI-powered incident response playbook generator."""

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("ir-playbook")
except Exception:
    __version__ = "1.0.0"
