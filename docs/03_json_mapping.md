# 03 — JSON mapping

Runtime configuration for CMSumoCosim is a single file:

**`CoSim/cosim_vehicle_mapping.json`**

Editor hover and validation use the sibling schema:

**`CoSim/cosim_vehicle_mapping.schema.json`**

In the mapping JSON keep:

```json
"$schema": "cosim_vehicle_mapping.schema.json"
```

(so the schema resolves next to the file). The kit sample under `CoSim/examples/CoSim/` already keeps mapping + schema as siblings with `"$schema": "cosim_vehicle_mapping.schema.json"` — copy that whole folder into your project `CoSim/`.

---

## Where the app looks

Search order (typical):

1. Environment variable **`COSIM_VEHICLE_MAPPING_JSON`** (full path), if set  
2. `CoSim/cosim_vehicle_mapping.json` under the project / AppDir  
3. `./CoSim/cosim_vehicle_mapping.json` from the process working directory  

On HIL, the project folder name must be exactly **`CoSim`** (Linux case-sensitive).

Generate or refresh the file with `CoSim/Orchestrator/CoSim_Orchestrator_Wizard.py` ([02](02_orchestrator_and_first_test.md)).

---

## Office vs HIL (flag matrix)

| Goal | Key settings |
|------|----------------|
| Office in-process TraCI | `cosim_enable: true`, valid `sumo_sumocfg_path`|
| HIL + host SUMO | `cosim_enable: true`, `rt_host_rx_enable: true`, `rt_ego_tx_enable: true`, ports/IPs match Cosim_bridge |
| CM-only (no SUMO/RT) | `cosim_enable: false` |

RT-only keys are parsed on office builds but unused when RX is off. On office, requesting `rt_host_rx_enable` is forced off and in-process SUMO is used instead.

---


### Core / SUMO

| Key | Type | Purpose |
|-----|------|---------|
| `cosim_enable` | bool | Master switch. `false` = no SUMO / RT bring-up. |
| `sumo_sumocfg_path` | string | Path to `.sumocfg` for in-process TraCI (`Simulation::start -c`). Required for office. Prefer forward slashes. |
| `sumo_home` | string | Optional SUMO install root for **Cosim_bridge** spawn (`<sumo_home>/bin/sumo.exe`). Empty → env `SUMO_HOME` or PATH. Not used by office in-process libsumo. |
| `sumo_gui` / `SUMO_gui` | bool | Start sumo-gui vs headless for in-process init / Cosim_bridge `--sumo-gui`. |
| `SUMO_lights` | bool | Mirror signals to SUMO / write traffic light DVAs when true. |
| `sumo_substeps` | int | CarMaker cycles between TraCI steps. |
| `sumo_step_length_s` | number | SUMO seconds per TraCI step (`--step-length`). |
| `cosim_logging_enabled` | bool | Verbose cosim / Cosim_bridge logs. |

### Advance-sync (experimental)

| Key | Type | Purpose |
|-----|------|---------|
| `cosim_advance_sync` | bool | A★→B Hermite / predictive sync (office + RT when enabled). |
| `cosim_ego_predict_horizon_s` | number | Look-ahead [s] for ego push when advance-sync is on (`0` → use step length). |

### ROI

| Key | Type | Purpose |
|-----|------|---------|
| `roi` | `null` \| number \| `{ "radius_m" }` | Keep / assign vehicles within radius [m] of ego in Fr0. Number form (e.g. `200`) is accepted. |

### Vehicles and slots

| Key | Type | Purpose |
|-----|------|---------|
| `vehicles` | array | Entries with `role` (`ego` / `actor` / …), `length_m`, optional `template`. Ego `length_m` sets rear→front conversion. |
| `traffic_slots` | array | `slot_index`, `ipg_name` (must match TestRun Traffic name), `expected_vtype_id`, `length_m`. |
| `flow_prefixes` | string[] | SUMO id prefixes assigned to the pool (e.g. `flow0.`). |
| `vtype_slot_indices` | object | SUMO vType id → list of slot indices. |
| `actor_enabled` | bool | Roleplay / non-pool actor mirroring. |
| `actor_instances` | array | Optional actors (`ipg_name`, `template`, …). |

### Coordinate alignment

| Key | Type | Purpose |
|-----|------|---------|
| `coordinate_alignment` | object | `g_theta_rad`, `g_dx`, `g_dy` — SUMO ↔ IPG Fr0. See [02](02_orchestrator_and_first_test.md). |

### HIL / UDP (with Cosim_bridge)

| Key | Type | Purpose |
|-----|------|---------|
| `rt_host_rx_enable` | bool | XENO: receive traffic UDP from host. |
| `rt_host_rx_port` | int | Traffic RX port on RT (host TX target). |
| `rt_host_rx_timeout_s` | number | Hide stale traffic after timeout. |
| `rt_ego_tx_enable` | bool | XENO: send ego (and actors) UDP to host. |
| `rt_ego_tx_ip` | string | Host IP for ego TX. |
| `rt_ego_tx_port` | int | Host UDP port for ego. |
| `rt_ego_tx_decimation` | int | Send ego every N CM cycles. |
| `rt_actor_tx_decimation` | int | Actor TX decimation. |
| `rt_bridge_hz` | number | **(host)** Bridge loop rate. |
| `rt_target_ip` / `rt_traffic_tx_ip` | string | **(host)** Destination IP for traffic UDP to RT. |


## Traffic DVA (what moves in CarMaker)

For each bound slot `ipg_name`, the library writes quantities such as:

| Quantity | Meaning |
|----------|---------|
| `Traffic.<name>.tx`, `.ty` | Rear-axle position Fr0 [m] |
| `Traffic.<name>.rz` | Heading [rad] |
| `Traffic.<name>.State` | `3` active, `0` hidden / recycled |
| `Traffic.<name>.LongVel` / `.LatVel` | Speeds from TraCI (not Δposition) |
| `Traffic.<name>.Lights.*` | When `SUMO_lights` is true |

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No hover on JSON keys | Schema missing beside mapping, or `$schema` path wrong |
| Mapping not found on RT | Folder must be `CoSim` (case); AppDir / cwd |
| SUMO init failed | `sumo_sumocfg_path` readable; net/route files exist |
| Traffic never appears | `traffic_slots[].ipg_name` vs TestRun names; ROI too small; `cosim_enable` |