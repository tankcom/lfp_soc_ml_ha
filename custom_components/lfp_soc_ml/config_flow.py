from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

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


def _build_full_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_BMS_SOC_ENTITY, default=current.get(CONF_BMS_SOC_ENTITY, "")): str,
            vol.Optional(CONF_BMS_SOH_ENTITY, default=current.get(CONF_BMS_SOH_ENTITY, "")): str,
            vol.Required(CONF_TOTAL_VOLTAGE_ENTITY, default=current.get(CONF_TOTAL_VOLTAGE_ENTITY, "")): str,
            vol.Optional(CONF_CHARGE_POWER_ENTITY, default=current.get(CONF_CHARGE_POWER_ENTITY, "")): str,
            vol.Optional(CONF_DISCHARGE_POWER_ENTITY, default=current.get(CONF_DISCHARGE_POWER_ENTITY, "")): str,
            vol.Optional(CONF_RAW_POWER_ENTITY, default=current.get(CONF_RAW_POWER_ENTITY, "")): str,
            vol.Optional(CONF_CURRENT_ABS_ENTITY, default=current.get(CONF_CURRENT_ABS_ENTITY, "")): str,
            vol.Optional(CONF_TEMPERATURE_MIN_ENTITY, default=current.get(CONF_TEMPERATURE_MIN_ENTITY, "")): str,
            vol.Optional(CONF_TEMPERATURE_MAX_ENTITY, default=current.get(CONF_TEMPERATURE_MAX_ENTITY, "")): str,
            vol.Optional(CONF_TEMPERATURE_ENTITY, default=current.get(CONF_TEMPERATURE_ENTITY, "")): str,
            vol.Optional(
                CONF_ENERGY_CHARGED_TOTAL_ENTITY,
                default=current.get(CONF_ENERGY_CHARGED_TOTAL_ENTITY, ""),
            ): str,
            vol.Optional(
                CONF_ENERGY_DISCHARGED_TOTAL_ENTITY,
                default=current.get(CONF_ENERGY_DISCHARGED_TOTAL_ENTITY, ""),
            ): str,
            vol.Optional(
                CONF_MODULE_MIN_VOLTAGE_ENTITIES,
                default=current.get(CONF_MODULE_MIN_VOLTAGE_ENTITIES, ""),
            ): str,
            vol.Optional(
                CONF_MODULE_MAX_VOLTAGE_ENTITIES,
                default=current.get(CONF_MODULE_MAX_VOLTAGE_ENTITIES, ""),
            ): str,
            vol.Optional(
                CONF_NOMINAL_CAPACITY_KWH,
                default=current.get(CONF_NOMINAL_CAPACITY_KWH, DEFAULT_NOMINAL_CAPACITY_KWH),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_NOMINAL_CAPACITY_AH,
                default=current.get(CONF_NOMINAL_CAPACITY_AH, DEFAULT_NOMINAL_CAPACITY_AH),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_CHARGE_EFFICIENCY,
                default=current.get(CONF_CHARGE_EFFICIENCY, DEFAULT_CHARGE_EFFICIENCY),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_UPDATE_INTERVAL_SECONDS,
                default=current.get(CONF_UPDATE_INTERVAL_SECONDS, DEFAULT_UPDATE_INTERVAL_SECONDS),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_BALANCE_SOC_THRESHOLD,
                default=current.get(CONF_BALANCE_SOC_THRESHOLD, DEFAULT_BALANCE_SOC_THRESHOLD),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_BALANCE_SPREAD_THRESHOLD_V,
                default=current.get(CONF_BALANCE_SPREAD_THRESHOLD_V, DEFAULT_BALANCE_SPREAD_THRESHOLD_V),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_DISCHARGE_CUTOFF_CELL_V,
                default=current.get(CONF_DISCHARGE_CUTOFF_CELL_V, DEFAULT_DISCHARGE_CUTOFF_CELL_V),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_MAX_SOC_STEP_PER_UPDATE,
                default=current.get(CONF_MAX_SOC_STEP_PER_UPDATE, DEFAULT_MAX_SOC_STEP_PER_UPDATE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_HISTORY_LEARNING_ENABLED,
                default=current.get(CONF_HISTORY_LEARNING_ENABLED, DEFAULT_HISTORY_LEARNING_ENABLED),
            ): bool,
            vol.Optional(
                CONF_HISTORY_WINDOW_SAMPLES,
                default=current.get(CONF_HISTORY_WINDOW_SAMPLES, DEFAULT_HISTORY_WINDOW_SAMPLES),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_HISTORY_MIN_SAMPLES,
                default=current.get(CONF_HISTORY_MIN_SAMPLES, DEFAULT_HISTORY_MIN_SAMPLES),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_HISTORY_LEARNING_RATE,
                default=current.get(CONF_HISTORY_LEARNING_RATE, DEFAULT_HISTORY_LEARNING_RATE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_HISTORY_MAX_RESIDUAL,
                default=current.get(CONF_HISTORY_MAX_RESIDUAL, DEFAULT_HISTORY_MAX_RESIDUAL),
            ): vol.Coerce(float),
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
