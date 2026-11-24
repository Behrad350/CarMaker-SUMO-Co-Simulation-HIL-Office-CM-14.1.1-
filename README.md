# CMSumoCosim

CarMaker ↔ SUMO co-simulation kit for CarMaker **14.1.1** (CoSim only — no ViL / CAN / Vehico).
This package was developed using CM 14.1.1, it may or may not need adjustments to work with other versions.

This is the **end-user** package: libraries, patches, wizards, samples, and **Cosim_bridge** (HIL host).
The bridge was made specifically with the libraries from SUMO V1.23.1 binary. It is not tested with other versions.

## Guides

| Chapter | Topic |
|---------|--------|
| [01 — Install and recompile](docs/01_install_and_recompile.md) | Drop into a stock CM 14.1.1 app; Makefile + MSVC |
| [02 — Orchestrator and first test](docs/02_orchestrator_and_first_test.md) | Wizard, alignment, first TestRun |
| [03 — JSON mapping](docs/03_json_mapping.md) | `cosim_vehicle_mapping.json` + schema |
| [04 — Cosim_bridge](docs/04_cosim_bridge.md) | HIL host bridge + bring-your-own SUMO |

## Layout

```text
CMSumoCosim/
  include/  lib/  Src/
  CoSim/
    examples/CoSim/     # mapping, schema, SUMO sample
    examples/Data/      # optional TestRuns / roads / vehicles (convenience)
    Orchestrator/       # mapping + alignment wizards
    Cosim_bridge/       # Cosim_bridge.exe + matched TraCI DLLs
  docs/
  LICENSE               # MIT (original kit code)
  NOTICE                # third-party (SUMO, xerces, zlib, IPG sample data)
```

## Quick drop-in

| Package | Your project |
|---------|----------------|
| `include/`, `lib/` | same under project root |
| `Src/User_CMSumoCosim_patch.cpp` | `src/User.cpp` |
| `CoSim/examples/CoSim/*` | project `CoSim/` |
| `CoSim/Cosim_bridge/` | project `CoSim/Cosim_bridge/` (HIL) |

**HIL:** set mapping `"sumo_home"` (or `SUMO_HOME` / PATH), then:

```bat
CoSim\Cosim_bridge\Cosim_bridge.exe --mapping-json CoSim\cosim_vehicle_mapping.json
```

Keep the DLLs next to `Cosim_bridge.exe`. Use **your** local `sumo.exe` — do not replace the shipped TraCI DLLs.

## License

- **Original CMSumoCosim code:** [MIT](LICENSE)
- **Third-party / sample data:** see [NOTICE](NOTICE) (Eclipse SUMO TraCI DLLs under EPL; xerces; zlib; optional IPG-origin example Data for convenience)
- **CarMaker application:** not included — you need a valid IPG CarMaker license and install to run co-simulation
