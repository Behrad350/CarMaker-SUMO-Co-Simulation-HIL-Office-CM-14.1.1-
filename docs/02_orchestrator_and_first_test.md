# 02 — Orchestrator and first test

Prepare a co-simulation scenario from zero: generate the mapping JSON, align coordinates, and run a first TestRun. Assumes the kit is already installed ([01 — Install](01_install_and_recompile.md)).

---

## What you need

| Input | Role |
|-------|------|
| CarMaker **TestRun** | Ego vehicle + traffic pool objects (`Traffic.T01`, …) |
| SUMO network + routes | At least a `.rou.xml` (and usually `.net.xml` / `.sumocfg`) |
| Python 3 | To run the Orchestrator wizard |
| Kit tools | `CoSim/Orchestrator/CoSim_Orchestrator_Wizard.py` and `Coordinate_Alignment_Wizard.py` |
| Kit samples | `CoSim/examples/CoSim/` (mapping/schema/SUMO) and optional `CoSim/examples/Data/` |

Typical project layout after setup (runtime paths — not the kit tree):

```text
MyProject/
  CoSim/
    cosim_vehicle_mapping.json          # from kit CoSim/examples/CoSim/
    cosim_vehicle_mapping.schema.json
    SUMO/…                              # from kit CoSim/examples/CoSim/SUMO/ (or your own)
    Orchestrator/…                      # optional: copy from kit CoSim/Orchestrator/
    Cosim_bridge/…                      # optional: HIL host bridge (exe + matched DLLs)
  Data/TestRun/…                        # optional samples under kit CoSim/examples/Data/
  Data/Traffic/…
```

---

## Step 1 — Prepare the TestRun

1. Create or open a TestRun with a free-driving or scripted ego.
2. Add **enough traffic objects** for the pool you want (names must match what the wizard writes into `traffic_slots[].ipg_name`, often `T01`, `T02`, …, the wizard will detect the names).
3. Pool objects used for SUMO flows should be free-motion / animatable. It is advised to prepare the test file in two steps, first use a spawn location for traffic vehicles that can be replicated in SUMO, to align the maps, and then customise all of the other routes in SUMO and add the rest of the traffic spawn locations. 
** You can also add non-free-motion vehicles in CM, as CM controlled Roleplay `actors` and their movement will be replicated in SUMO.

Keep a note of the TestRun file path — the wizard asks for it.

---

## Step 2 — Prepare SUMO

1. Have a SUMO scenario folder with routes (`.rou.xml`). A `.sumocfg` that references net + routes is required (`sumo_sumocfg_path`).
2. The wizard can point at a routes **file** or a **folder** containing `*.rou.xml` (`scenario.rou.xml` if present).
3. Sample maps ship under kit **`CoSim/examples/CoSim/SUMO/`**. Sample TestRuns / roads live under **`CoSim/examples/Data/`** — copy into your project `Data/` if you want a ready-made first run (e.g. `Cruising_3lanes`).

---

## Step 3 — Run the Orchestrator wizard

From a shell (project root or Orchestrator folder):

```bat
cd MyProject\CoSim\Orchestrator
python CoSim_Orchestrator_Wizard.py
```

Interactive prompts cover TestRun path, SUMO routes, IPG Traffic Template / Ego Vehicle roots (auto-discovered for CM 14.1.1), step length / substeps, ROI, advance-sync, RT IPs/ports (for HIL), lights, and logging. Defaults match the live BR692 mapping (`sumo_substeps=100`, `sumo_step_length_s=0.1`, `rt_bridge_hz=1000`, `roi=200`, `cosim_advance_sync=true`, …).

Non-interactive example:

```bat
python CoSim_Orchestrator_Wizard.py --no-wizard ^
  --testrun "C:\CM_Projects\MyProject\Data\TestRun\MyRun" ^
  --sumo-routes "C:\CM_Projects\MyProject\CoSim\SUMO" ^
  --output-json "C:\CM_Projects\MyProject\CoSim\cosim_vehicle_mapping.json"
```

### What the wizard produces

- Updates / writes **`CoSim/cosim_vehicle_mapping.json`** (default under the project).
- Rebuilds SUMO **vType** / route mix for type-aware slots (`vtype_slot_indices`, `traffic_slots`, `flow_prefixes`).
- Sets **`sumo_sumocfg_path`** when it can resolve a config.
- Preserves an existing **`coordinate_alignment`** block if one was already in the JSON.

Keep the **schema file** next to the mapping so the editor can hover fields — see [03 — JSON mapping](03_json_mapping.md).

---

## Step 4 — Coordinate alignment

SUMO and CarMaker Fr0 do not share an origin by default. Alignment is the rigid transform stored as:

```json
"coordinate_alignment": {
  "g_theta_rad": 0.0,
  "g_dx": 0.0,
  "g_dy": 0.0
}
```

| Field | Meaning |
|-------|---------|
| `g_theta_rad` | Rotation (radians) between frames |
| `g_dx`, `g_dy` | Translation (meters) |

### Alignment wizard

In order to align the two maps, you will need to run a basic simulation (look at step 5), using the map that you intend to work with, keep `ROI = Null`. During this test you need to record tx, ty, and tz from your Traffic pool's UAQ. Then using IPGMovie / IPGControl export the output to a `.csv`, and feed this CSV to the Coordinate_Alignment_Wizard. The script will detect the shifts at spawn time, and calculate the required offset accordingly. A sample CSV ships in the kit as `CoSim/examples/CoSim/alignment.CSV` (copy into your project `CoSim/` with the other examples if useful).
```bat
cd MyProject\CoSim\Orchestrator
python Coordinate_Alignment_Wizard.py
```

It walks you through picking the appropriate shift / checking the current transform and can write `coordinate_alignment` back into the mapping JSON (with confirmation).

### How to check

1. Place the free-motion vehicles at a known road feature in CarMaker.
2. In SUMO, place your traffic spawn location at the corresponding point on the map.
3. Run the cosimulation just long enough so that the vehicles start moving in CarMaker. (Traffic vehicles may spawn out of the paved area).
4. Create the CSV.
5. If traffic is consistently shifted or rotated, run the alignment wizard to populate `g_dx` / `g_dy` / `g_theta_rad` and re-test.

Wrong alignment looks like “CoSim runs but cars are in the wrong place,” not like a compile failure.

---

## Step 5 — First office TestRun (in-process TraCI)

1. Build the **win64** app with MSVC ([01](01_install_and_recompile.md)).
2. In the mapping:
   - `"cosim_enable": true`
   - Valid `"sumo_sumocfg_path"`
3. Start CarMaker from the **project** so `CoSim/` resolves (or set `COSIM_VEHICLE_MAPPING_JSON`).
4. Run the TestRun. With `"cosim_logging_enabled": true` you should see mapping / SUMO messages in the log.
5. Confirm pool traffic moves (`Traffic.<ipg_name>.State` → active, poses update).

If nothing happens: check folder name **`CoSim`**, mapping path, `sumocfg` readability, and that traffic names match slots ([03](03_json_mapping.md)).

---

## Step 6 — First HIL / RT test

1. Build **xeno** (`cmmake CM_TARGET=xeno`) and install/deploy the app the GUI points at under `bin/`.
2. Mapping: `"rt_host_rx_enable": true`, `"rt_ego_tx_enable": true`, ports/IPs matching the host PC.
3. On the **host**: start SUMO via **`Cosim_bridge`** (recommended) — see [04 — Cosim_bridge](04_cosim_bridge.md).
4. On the **RT**: start the TestRun. Confirm log shows `mapping ready` (not “could not find cosim_vehicle_mapping.json”).

Start order: **Cosim_bridge (SUMO) → HIL CarMaker TestRun**.

---

## Optional: Pipeline / DoE

`CoSim/Pipeline/` is included for batch / DoE studies (advanced). It is separate from a single first TestRun — Orchestrator + alignment wizards are enough to get started.

---

## Checklist

- [ ] TestRun has named traffic pool objects  
- [ ] SUMO routes / sumocfg exist  
- [ ] Wizard wrote `CoSim/cosim_vehicle_mapping.json`  
- [ ] Schema sits beside the JSON  
- [ ] `coordinate_alignment` set and checked  
- [ ] Office **or** HIL + Cosim_bridge as needed  

