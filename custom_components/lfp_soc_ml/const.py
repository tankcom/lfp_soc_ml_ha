from __future__ import annotations

DOMAIN = "lfp_soc_ml"
PLATFORMS = ["sensor"]

CONF_BMS_SOC_ENTITY = "bms_soc_entity"
CONF_BMS_SOH_ENTITY = "bms_soh_entity"
CONF_TOTAL_VOLTAGE_ENTITY = "total_voltage_entity"
CONF_CHARGE_POWER_ENTITY = "charge_power_entity"
CONF_DISCHARGE_POWER_ENTITY = "discharge_power_entity"
CONF_RAW_POWER_ENTITY = "raw_power_entity"
CONF_CURRENT_ABS_ENTITY = "current_abs_entity"
CONF_TEMPERATURE_MIN_ENTITY = "temperature_min_entity"
CONF_TEMPERATURE_MAX_ENTITY = "temperature_max_entity"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_ENERGY_CHARGED_TOTAL_ENTITY = "energy_charged_total_entity"
CONF_ENERGY_DISCHARGED_TOTAL_ENTITY = "energy_discharged_total_entity"
CONF_MODULE_MIN_VOLTAGE_ENTITIES = "module_min_voltage_entities"
CONF_MODULE_MAX_VOLTAGE_ENTITIES = "module_max_voltage_entities"

CONF_NOMINAL_CAPACITY_KWH = "nominal_capacity_kwh"
CONF_NOMINAL_CAPACITY_AH = "nominal_capacity_ah"
CONF_CHARGE_EFFICIENCY = "charge_efficiency"
CONF_UPDATE_INTERVAL_SECONDS = "update_interval_seconds"
CONF_BALANCE_SOC_THRESHOLD = "balance_soc_threshold"
CONF_BALANCE_SPREAD_THRESHOLD_V = "balance_spread_threshold_v"
CONF_DISCHARGE_CUTOFF_CELL_V = "discharge_cutoff_cell_v"
CONF_MAX_SOC_STEP_PER_UPDATE = "max_soc_step_per_update"
CONF_HISTORY_LEARNING_ENABLED = "history_learning_enabled"
CONF_HISTORY_WINDOW_SAMPLES = "history_window_samples"
CONF_HISTORY_MIN_SAMPLES = "history_min_samples"
CONF_HISTORY_LEARNING_RATE = "history_learning_rate"
CONF_HISTORY_MAX_RESIDUAL = "history_max_residual"

DEFAULT_NAME = "LFP SOC ML"
DEFAULT_UPDATE_INTERVAL_SECONDS = 10
DEFAULT_CHARGE_EFFICIENCY = 0.99
DEFAULT_BALANCE_SOC_THRESHOLD = 98.9
DEFAULT_BALANCE_SPREAD_THRESHOLD_V = 0.015
DEFAULT_DISCHARGE_CUTOFF_CELL_V = 2.80
DEFAULT_MAX_SOC_STEP_PER_UPDATE = 2.0
DEFAULT_NOMINAL_CAPACITY_KWH = 10.0
DEFAULT_NOMINAL_CAPACITY_AH = 280.0
DEFAULT_HISTORY_LEARNING_ENABLED = True
DEFAULT_HISTORY_WINDOW_SAMPLES = 720
DEFAULT_HISTORY_MIN_SAMPLES = 60
DEFAULT_HISTORY_LEARNING_RATE = 0.05
DEFAULT_HISTORY_MAX_RESIDUAL = 15.0

ATTR_OPERATION_MODE = "operation_mode"
ATTR_CONFIDENCE = "confidence"
ATTR_LAST_ANCHOR_TYPE = "last_anchor_type"
ATTR_LAST_ANCHOR_AGE_MIN = "last_anchor_age_min"
ATTR_SIGNED_CURRENT_A = "signed_current_a"
ATTR_MODEL_VERSION = "model_version"
ATTR_IMBALANCE_MAX_V = "imbalance_max_v"
ATTR_IMBALANCE_MEDIAN_V = "imbalance_median_v"
