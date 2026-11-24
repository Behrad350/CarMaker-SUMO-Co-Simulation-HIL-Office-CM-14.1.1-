# 04 — Cosim_bridge (HIL host bridge)

`Cosim_bridge.exe` runs on the **office / host PC**. It talks to SUMO (TraCI) and exchanges UDP with the CarMaker **xeno** application on the HIL.

Office **win64** in-process TraCI does **not** need this binary.

In the **end-user** package the bridge lives under `CoSim/Cosim_bridge/` (exe + matched TraCI DLLs). The maintainer kit still builds it as `native_cosim` under `CoSim/native_cosim/`.

---

## When you need it

| Setup | Cosim_bridge? |
|-------|----------------|
| Office CarMaker + libsumo inside the app | No |
| HIL `CarMaker.xeno` + SUMO on host | **Yes** |

CarMaker XENO does not run TraCI. With `rt_host_rx_enable` / `rt_ego_tx_enable` in the mapping, the RT app only speaks UDP; the host bridge owns SUMO.

---

## Architecture (short)

```text
  CarMaker.xeno (RT)  --UDP ego/actors-->  Cosim_bridge  --TraCI-->  your SUMO
  CarMaker.xeno (RT)  <--UDP traffic----  Cosim_bridge  <--TraCI--  your SUMO
```

Ports and IPs come from `CoSim/cosim_vehicle_mapping.json` ([03](03_json_mapping.md)). They must match on both sides.

---

## Bring your own SUMO

Cosim_bridge ships with **matched TraCI client DLLs** (`libtracicpp.dll`, `libsumocpp.dll`, …). Keep those next to the exe — do **not** replace them with another SUMO install’s DLLs.

Your machine still supplies **`sumo.exe` / `sumo-gui.exe`**. The version can differ from the matched TraCI build; the bridge talks TraCI TCP to whatever `sumo.exe` you point at.

### How Cosim_bridge finds `sumo.exe` (spawn mode)

1. CLI **`--sumo-bin <path-to-sumo.exe>`** (highest priority)  
2. Mapping **`sumo_home`** → `<sumo_home>/bin/sumo.exe` (or `sumo-gui.exe` with `--sumo-gui`)  
3. Env **`SUMO_HOME`** → same `bin/...` rule  
4. Bare `sumo` / `sumo-gui` on **`PATH`**

Prefer setting `"sumo_home"` in the mapping (Orchestrator wizard asks for it) so HIL runs are reproducible without shell setup.

Example:

```json
"sumo_home": "C:/Program Files (x86)/Eclipse/Sumo"
```

**Office note:** in-process CarMaker TraCI uses the linked libsumo inside the app. `sumo_home` is for **Cosim_bridge** spawn mode, not for re-pointing office TraCI.

### Launcher (end-user package)

```bat
cd MyProject\CoSim\Cosim_bridge
 ".\Cosim_bridge.exe" `
>>   --mapping-json "C:\CM_Projects\MyProject\CoSim\cosim_vehicle_mapping.json"
```

---

## Modes

### Spawn mode (recommended)

Do **not** pass `--traci-connect`.  
Cosim_bridge starts SUMO (or sumo-gui with `--sumo-gui`), connects TraCI, and runs the bridge loop.

### Attach mode

Pass `--traci-connect`.  
SUMO must already be running with TraCI; the bridge only attaches (`--traci-host` / `--traci-port`).

---

## Before you start

1. Mapping under project **`CoSim/cosim_vehicle_mapping.json`** (exact casing). Kit sample: copy from `CoSim/examples/CoSim/`.
2. HIL flags: `rt_host_rx_enable`, `rt_ego_tx_enable`, ports/IPs for your network.
3. `sumo_sumocfg_path` valid for spawn mode.
4. `sumo_home` set (or `SUMO_HOME` / PATH / `--sumo-bin`) so `sumo.exe` is found.
5. Keep matched DLLs beside `Cosim_bridge.exe`.
6. Xeno app built/installed; GUI points at the Cosim-capable `bin/CarMaker.*.xeno`.

---

## Start order

1. On **host**: start Cosim_bridge (spawns or attaches to SUMO).  
2. On **RT**: start CarMaker / TestRun with the Cosim xeno app.  
3. Confirm RT log shows **`mapping ready`** (not “could not find cosim_vehicle_mapping.json”).  
4. Confirm traffic UDP is flowing (traffic objects move; optional `cosim_logging_enabled`).

---

## CLI essentials

Typical spawn:

```
Cosim_bridge.exe --mapping-json C:\CM_Projects\MyProject\CoSim\cosim_vehicle_mapping.json
```

Useful options:

| Option | Meaning |
|--------|---------|
| `--mapping-json <path>` | Mapping file |
| `--sumocfg <path>` | Override `sumo_sumocfg_path` |
| `--sumo-bin <path>` | Full path to `sumo.exe` / `sumo-gui.exe` |
| `--sumo-gui` | Spawn GUI SUMO |
| `--traci-connect` | Attach to existing TraCI |
| `--traci-host` / `--traci-port` | TraCI endpoint |
| `--rt-ip` / `--rt-traffic-port` | Override traffic UDP destination |
| `--host-ego-port` | Override host ego RX port |
| `--hz` | Bridge loop rate override |
| `--quiet` | Less periodic logging |
| `--self-test-traci` | Connect/version probe only |

**End-user binary:** `CoSim/Cosim_bridge/Cosim_bridge.exe`  
---

## Mapping keys used by the bridge

At minimum the host cares about:

- `sumo_sumocfg_path` (spawn mode)  
- optional `sumo_home` (SUMO install root)  
- `rt_host_rx_port` → traffic UDP to RT  
- `rt_ego_tx_port` / ego RX on host  
- `rt_target_ip` or equivalent TX destination to the RT  
- ego / actor length and traffic slot geometry  
- optional: `rt_bridge_hz`, advance-sync

Full field list: [03 — JSON mapping](03_json_mapping.md).

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| RT: mapping not found | Project folder not named `CoSim`; wrong AppDir |
| Bridge starts, RT silent | Ports/IPs mismatch; firewall; wrong xeno binary in `bin/` |
| CreateProcess / SUMO binary not found | Set `sumo_home`, `SUMO_HOME`, `--sumo-bin`, or PATH |
| TraCI / `vector too long` | Replaced matched DLLs next to Cosim_bridge — restore kit DLLs |
| Traffic jumps / stalls | Tune step length / substeps, or leave `cosim_advance_sync` off until aligned |
| Office works, HIL empty | Forgot to start Cosim_bridge, or `rt_host_rx_enable` false |

---
