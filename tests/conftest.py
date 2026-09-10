"""Shared fixtures: let HA's test harness load custom_components/meross_cloud."""
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """enable_custom_integrations is provided by pytest-homeassistant-custom-component."""
    yield
