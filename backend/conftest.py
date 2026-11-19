"""
pytest configuration for DeepPredict backend.
Enables pytest-django with the correct settings module.
"""
import django
from django.conf import settings


def pytest_configure(config):
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
