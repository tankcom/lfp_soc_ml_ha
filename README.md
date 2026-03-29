# LFP SOC ML Estimator

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/tankcom/lfp_soc_ml)](https://github.com/tankcom/lfp_soc_ml/releases)

A Home Assistant custom integration that estimates the **State of Charge (SoC)** and **State of Health (SoH)** of LFP (LiFePO₄) battery systems using a physics-based model enhanced by adaptive residual learning.

## Features

- Physics-based Coulomb counting with configurable efficiency
- Adaptive ML residual correction trained on live data
- Cell-imbalance detection and automatic SoC pinning at full charge
- SoH tracking via energy throughput
- Configurable via the Home Assistant UI (config flow)

## Provided Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.<name>_soc` | Estimated State of Charge (%) |
| `sensor.<name>_soh` | Estimated State of Health (%) |
| `sensor.<name>_confidence` | Estimation confidence (%) |
| `sensor.<name>_operation_mode` | Current operation mode of the state machine |
| `sensor.<name>_soc_voltage_ml` | Voltage-ML SoC estimate (%) |
| `sensor.<name>_voltage_ml_confidence` | Confidence of the Voltage-ML estimate (%) |

## Installation via HACS

1. Open HACS in Home Assistant.
2. Go to **Integrations** → three-dot menu → **Custom repositories**.
3. Add `https://github.com/tankcom/lfp_soc_ml` as type **Integration**.
4. Search for **LFP SOC ML Estimator** and install it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for **LFP SOC ML**.

## Manual Installation

1. Copy `custom_components/lfp_soc_ml/` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services**.

## Configuration

All settings are configurable through the UI. Required entities:

| Field | Description |
|-------|-------------|
| BMS SoC Entity | Entity providing the raw BMS State of Charge (%) |
| Total Voltage Entity | Entity providing total pack voltage (V) |

Optional entities (improve accuracy):

- BMS SoH Entity
- Charge / Discharge Power Entities (W)
- Raw Power Entity (unsigned W; direction is inferred from Charge/Discharge Power or voltage trend)
- Current (absolute) Entity (A)
- Temperature Entities (°C)
- Energy Charged / Discharged Total Entities (kWh)
- Per-module Min/Max Voltage Entities (comma-separated entity IDs)

### Advanced Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Nominal Capacity (kWh) | 10.0 | Nominal pack energy capacity |
| Nominal Capacity (Ah) | 280.0 | Pack capacity in Amp-hours for Coulomb counting — equals the Ah rating of your cells (e.g. 280 for 280 Ah cells); if unknown, divide kWh × 1000 by nominal cell voltage (e.g. 10 000 Wh / 51.2 V ≈ 195 Ah) |
| Charge Efficiency | 0.99 | Round-trip charge efficiency factor |
| Update Interval (s) | 10 | Polling interval in seconds |
| Balance SoC Threshold (%) | 98.9 | SoC at which cell balancing is assumed complete |
| Balance Spread Threshold (V) | 0.015 | Max cell voltage spread at balanced state |
| Discharge Cutoff Cell Voltage (V) | 2.80 | Minimum cell voltage for 0 % SoC anchor |
| Max SoC Step per Update (%) | 2.0 | Clamp for implausible SoC jumps |
| History Learning Enabled | true | Enable adaptive residual learning |
| History Window Samples | 720 | Number of samples in the learning window |
| History Min Samples | 60 | Minimum samples before learning activates |
| History Learning Rate | 0.05 | Learning rate for residual correction |
| History Max Residual (%) | 15.0 | Outlier threshold for residual samples |

## Requirements

- Home Assistant ≥ 2023.1.0

## License

MIT
