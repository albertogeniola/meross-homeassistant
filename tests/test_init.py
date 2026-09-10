"""Setup-entry error handling for meross_cloud."""
import errno
import logging
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from aiohttp import ClientConnectorError
from aiohttp.client_reqrep import ConnectionKey
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from meross_iot.model.http.exception import AuthenticatedPostException, TokenExpiredException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meross_cloud.common import (
    CONF_HTTP_ENDPOINT,
    CONF_MQTT_SKIP_CERT_VALIDATION,
    CONF_STORED_CREDS,
    DEVICE_LIST_COORDINATOR,
    DOMAIN,
)

ENDPOINT = "http://homeassistant.local:2003"
LOGGER_NAME = "custom_components.meross_cloud"
# Same class object as custom_components.meross_cloud.MerossHttpClient; patching here avoids
# importing the integration module ahead of HA's loader.
LIST_DEVICES = "meross_iot.http_api.MerossHttpClient.async_list_devices"
DEVICE_DISCOVERY = "meross_iot.manager.MerossManager.async_device_discovery"
MANAGER_CLOSE = "meross_iot.manager.MerossManager.close"
FORWARD_SETUPS = "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"


def _connector_error(host="homeassistant.local", port=2003, err=errno.EINVAL, msg="Invalid argument"):
    """Build a ClientConnectorError the way aiohttp's connector does.

    ConnectionKey is a NamedTuple whose fields differ across aiohttp releases, so fill it by
    field name and leave unknown fields at None.
    """
    values = {
        "host": host, "port": port, "is_ssl": False, "ssl": True, "proxy": None,
        "proxy_auth": None, "proxy_headers_hash": None, "server_hostname": None,
    }
    key = ConnectionKey(*[values.get(field) for field in ConnectionKey._fields])
    return ClientConnectorError(key, OSError(err, msg))


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ENDPOINT,
        data={
            CONF_HTTP_ENDPOINT: ENDPOINT,
            CONF_MQTT_SKIP_CERT_VALIDATION: True,
            CONF_STORED_CREDS: {
                "token": "token", "key": "key", "user_id": "1", "user_email": "user@example.com",
                "issued_on": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                "domain": ENDPOINT, "mqtt_domain": "homeassistant.local:2001",
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


def _retry_warnings(caplog):
    return [
        r for r in caplog.records
        if r.name == LOGGER_NAME and r.levelno == logging.WARNING
        and "Home Assistant will retry" in r.getMessage()
    ]


@pytest.mark.parametrize(
    "error",
    [
        _connector_error(),
        AuthenticatedPostException("Failed request to API. Response code: 502"),
        OSError(errno.ECONNREFUSED, "Connection refused"),
        TimeoutError(),  # what asyncio.timeout(SETUP_HTTP_TIMEOUT_SECONDS) raises on expiry
    ],
    ids=["client_connector_error_einval", "nginx_502", "connection_refused", "timeout"],
)
async def test_transient_error_schedules_retry(hass: HomeAssistant, config_entry, error, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME), patch(LIST_DEVICES, side_effect=error):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Error setting up entry" not in caplog.text  # HA's generic, non-retrying path
    assert _retry_warnings(caplog), caplog.text


async def test_token_expired_still_starts_reauth(hass: HomeAssistant, config_entry, caplog):
    with patch(LIST_DEVICES, side_effect=TokenExpiredException()):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()  # reauth flow is created as a task

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "Error setting up entry" not in caplog.text
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == SOURCE_REAUTH for flow in flows)


async def test_discovery_transport_error_schedules_retry_and_closes_manager(
    hass: HomeAssistant, config_entry, caplog
):
    """Failures after the device list (MQTT broker refused) must retry and release the manager."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME), \
            patch(LIST_DEVICES, return_value=[]), \
            patch(DEVICE_DISCOVERY, side_effect=ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")), \
            patch(MANAGER_CLOSE) as close:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Error setting up entry" not in caplog.text
    assert _retry_warnings(caplog), caplog.text
    assert close.call_count == 1


async def test_polling_transport_error_is_update_failed(hass: HomeAssistant, config_entry, caplog):
    with patch(LIST_DEVICES, return_value=[]), patch(DEVICE_DISCOVERY, return_value=[]), \
            patch(FORWARD_SETUPS):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]

    caplog.clear()
    with patch(LIST_DEVICES, side_effect=AuthenticatedPostException("Failed request to API. Response code: 502")):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert "Unexpected error fetching" not in caplog.text
    assert "Cannot reach the Meross HTTP API" in caplog.text
