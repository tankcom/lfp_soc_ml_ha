from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_BALANCE_SOC_THRESHOLD,
    CONF_BALANCE_SPREAD_THRESHOLD_V,
    CONF_BMS_SOC_ENTITY,
    CONF_BMS_SOH_ENTITY,
    CONF_CHARGE_EFFICIENCY,
    CONF_CHARGE_POWER_ENTITY,
    CONF_CURRENT_ABS_ENTITY,
    CONF_DISCHARGE_CUTOFF_CELL_V,
    CONF_DISCHARGE_POWER_ENTITY,
    CONF_ENERGY_CHARGED_TOTAL_ENTITY,
    CONF_ENERGY_DISCHARGED_TOTAL_ENTITY,
    CONF_HISTORY_LEARNING_ENABLED,
    CONF_HISTORY_LEARNING_RATE,
    CONF_HISTORY_MAX_RESIDUAL,
    CONF_HISTORY_MIN_SAMPLES,
    CONF_HISTORY_WINDOW_SAMPLES,
    CONF_MAX_SOC_STEP_PER_UPDATE,
    CONF_MODULE_MAX_VOLTAGE_ENTITIES,
    CONF_MODULE_MIN_VOLTAGE_ENTITIES,
    CONF_NOMINAL_CAPACITY_AH,
    CONF_NOMINAL_CAPACITY_KWH,
    CONF_RAW_POWER_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_TEMPERATURE_MAX_ENTITY,
    CONF_TEMPERATURE_MIN_ENTITY,
    CONF_TOTAL_VOLTAGE_ENTITY,
    CONF_UPDATE_INTERVAL_SECONDS,
    DEFAULT_BALANCE_SOC_THRESHOLD,
    DEFAULT_BALANCE_SPREAD_THRESHOLD_V,
    DEFAULT_CHARGE_EFFICIENCY,
    DEFAULT_DISCHARGE_CUTOFF_CELL_V,
    DEFAULT_HISTORY_LEARNING_ENABLED,
    DEFAULT_HISTORY_LEARNING_RATE,
    DEFAULT_HISTORY_MAX_RESIDUAL,
    DEFAULT_HISTORY_MIN_SAMPLES,
    DEFAULT_HISTORY_WINDOW_SAMPLES,
    DEFAULT_MAX_SOC_STEP_PER_UPDATE,
    DEFAULT_NAME,
    DEFAULT_NOMINAL_CAPACITY_AH,
    DEFAULT_NOMINAL_CAPACITY_KWH,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)


def _entity_default(current: dict[str, Any], key: str) -> str:
    value = current.get(key, "")
    if isinstance(value, str):
        return value
    return ""


def _entity_list_default(current: dict[str, Any], key: str) -> list[str]:
    value = current.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str) and item]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _build_full_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_NAME)): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_BMS_SOC_ENTITY, default=_entity_default(current, CONF_BMS_SOC_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_BMS_SOH_ENTITY, default=_entity_default(current, CONF_BMS_SOH_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_TOTAL_VOLTAGE_ENTITY,
                default=_entity_default(current, CONF_TOTAL_VOLTAGE_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_CHARGE_POWER_ENTITY,
                default=_entity_default(current, CONF_CHARGE_POWER_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_DISCHARGE_POWER_ENTITY,
                default=_entity_default(current, CONF_DISCHARGE_POWER_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(CONF_RAW_POWER_ENTITY, default=_entity_default(current, CONF_RAW_POWER_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_CURRENT_ABS_ENTITY,
                default=_entity_default(current, CONF_CURRENT_ABS_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_TEMPERATURE_MIN_ENTITY,
                default=_entity_default(current, CONF_TEMPERATURE_MIN_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_TEMPERATURE_MAX_ENTITY,
                default=_entity_default(current, CONF_TEMPERATURE_MAX_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(CONF_TEMPERATURE_ENTITY, default=_entity_default(current, CONF_TEMPERATURE_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_ENERGY_CHARGED_TOTAL_ENTITY,
                default=_entity_default(current, CONF_ENERGY_CHARGED_TOTAL_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_ENERGY_DISCHARGED_TOTAL_ENTITY,
                default=_entity_default(current, CONF_ENERGY_DISCHARGED_TOTAL_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_MODULE_MIN_VOLTAGE_ENTITIES,
                default=_entity_list_default(current, CONF_MODULE_MIN_VOLTAGE_ENTITIES),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", multiple=True)),
            vol.Optional(
                CONF_MODULE_MAX_VOLTAGE_ENTITIES,
                default=_entity_list_default(current, CONF_MODULE_MAX_VOLTAGE_ENTITIES),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", multiple=True)),
            vol.Optional(
                CONF_NOMINAL_CAPACITY_KWH,
                default=current.get(CONF_NOMINAL_CAPACITY_KWH, DEFAULT_NOMINAL_CAPACITY_KWH),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=1000.0, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_NOMINAL_CAPACITY_AH,
                default=current.get(CONF_NOMINAL_CAPACITY_AH, DEFAULT_NOMINAL_CAPACITY_AH),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1.0, max=5000.0, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_CHARGE_EFFICIENCY,
                default=current.get(CONF_CHARGE_EFFICIENCY, DEFAULT_CHARGE_EFFICIENCY),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.8, max=1.0, step=0.001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL_SECONDS,
                default=current.get(CONF_UPDATE_INTERVAL_SECONDS, DEFAULT_UPDATE_INTERVAL_SECONDS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=300, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_BALANCE_SOC_THRESHOLD,
                default=current.get(CONF_BALANCE_SOC_THRESHOLD, DEFAULT_BALANCE_SOC_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50.0, max=100.0, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_BALANCE_SPREAD_THRESHOLD_V,
                default=current.get(CONF_BALANCE_SPREAD_THRESHOLD_V, DEFAULT_BALANCE_SPREAD_THRESHOLD_V),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.001, max=0.2, step=0.001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_DISCHARGE_CUTOFF_CELL_V,
                default=current.get(CONF_DISCHARGE_CUTOFF_CELL_V, DEFAULT_DISCHARGE_CUTOFF_CELL_V),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=2.0, max=3.5, step=0.01, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_MAX_SOC_STEP_PER_UPDATE,
                default=current.get(CONF_MAX_SOC_STEP_PER_UPDATE, DEFAULT_MAX_SOC_STEP_PER_UPDATE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=20.0, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_HISTORY_LEARNING_ENABLED,
                default=current.get(CONF_HISTORY_LEARNING_ENABLED, DEFAULT_HISTORY_LEARNING_ENABLED),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_HISTORY_WINDOW_SAMPLES,
                default=current.get(CONF_HISTORY_WINDOW_SAMPLES, DEFAULT_HISTORY_WINDOW_SAMPLES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=20000, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_HISTORY_MIN_SAMPLES,
                default=current.get(CONF_HISTORY_MIN_SAMPLES, DEFAULT_HISTORY_MIN_SAMPLES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=3, max=5000, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_HISTORY_LEARNING_RATE,
                default=current.get(CONF_HISTORY_LEARNING_RATE, DEFAULT_HISTORY_LEARNING_RATE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.001, max=1.0, step=0.001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_HISTORY_MAX_RESIDUAL,
                default=current.get(CONF_HISTORY_MAX_RESIDUAL, DEFAULT_HISTORY_MAX_RESIDUAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1.0, max=100.0, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
        }
    )


class LfpSocConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = _build_full_schema({CONF_NAME: DEFAULT_NAME})
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return LfpSocOptionsFlow(config_entry)


class LfpSocOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            new_name = user_input.get(CONF_NAME, self._config_entry.title)
            if new_name and new_name != self._config_entry.title:
                self.hass.config_entries.async_update_entry(self._config_entry, title=new_name)
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        schema = _build_full_schema(current)
        return self.async_show_form(step_id="init", data_schema=schema)
