# Cosim_bridge (HIL host)

`Cosim_bridge.exe` talks TraCI to **your** local SUMO and UDP to CarMaker xeno on the HIL.

## Quick start

1. Keep the DLLs in this folder next to `Cosim_bridge.exe` (do **not** replace them with Eclipse Sumo’s `libtracicpp`).
2. Point at your SUMO install (any of these):
   - mapping JSON: `"sumo_home": "C:/Program Files (x86)/Eclipse/Sumo"`
   - env `SUMO_HOME`
   - CLI `--sumo-bin "C:\...\bin\sumo.exe"`
   - or put `sumo.exe` on `PATH`
3. Launch:

```
Cosim_bridge.exe --mapping-json C:\CM_Projects\MyProject\CoSim\cosim_vehicle_mapping.json
```
or

```bat
run_Cosim_bridge.bat --mapping-json C:\path\to\MyProject\CoSim\cosim_vehicle_mapping.json
```
Spawn mode starts SUMO for you. Attach mode: start SUMO yourself, then add `--traci-connect`.

See kit docs chapter **04 — Cosim_bridge**.
