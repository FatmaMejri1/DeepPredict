"""
pytest configuration for DeepPredict backend.
Enables pytest-django with the correct settings module.
"""
import django
from django.conf import settings


def pytest_configure(config):
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def pytest_sessionstart(session):
    """Validate database isolation before pytest-django creates test DBs."""
    from django.conf import settings

    from config.test_database import validate_test_databases

    validate_test_databases(settings.DATABASES)
