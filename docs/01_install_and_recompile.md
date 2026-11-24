# 01 — Install and recompile

Add CMSumoCosim to a **stock CarMaker 14.1.1** application (for example IPG `PROJECTNAME`). Office (win64 TraCI) and HIL (xeno UDP) share the same header and User patch snippet; only the static library and toolchain differ.

Internal note: This package does **not** include ViL, UserCAN, or Vehico.

---

## Prerequisites

| Item | Notes |
|------|--------|
| CarMaker **14.1.1** | e.g. `C:/IPG/carmaker/win64-14.1.1` |
| Stock CM app | Project with `src/` (and usually `Data/`) |
| Eclipse SUMO (office) | Headers + `libsumocpp.lib` / `libtracicpp.lib` |
| This kit | End-user folder `CMSumoCosim` (or maintainer `CMSumoCosim_14.1.1`) |

For HIL you also need Cosim_bridge and your local SUMO on the office PC — see [04 — Cosim_bridge](04_cosim_bridge.md).

---

## Package layout (end-user `CMSumoCosim`)

```text
CMSumoCosim/
  include/CMSumoCosim.h
  lib/CMSumoCosim_win64.a      # MSVC office
  lib/CMSumoCosim_xeno.a       # cmmake HIL
  Src/                         # User patch + Makefile / vcxproj examples
  CoSim/
    examples/
      CoSim/                   # drop-in: mapping, schema, SUMO sample, alignment.CSV
      Data/                    # optional sample TestRuns / roads / vehicles
    Orchestrator/              # wizards
    Cosim_bridge/              # Cosim_bridge.exe + matched TraCI DLLs
    Pipeline/                  # optional DoE / batch studies
  docs/                        # these chapters
```

(Maintainer kits additionally keep `CoSim/native_cosim/` with the full rebuild tree — not required for end users.)

---

## Preparation

1. Create the SUMO simulation scenario.
2. In CarMaker Office, create a new project including the source code of the executable (check “Sources / Build Environment”).

---

## Step 1 — Copy files into your project

Assume project root `MyProject/` with `MyProject/src/CarMaker.sln`.

| From kit | To project |
|----------|------------|
| `include/CMSumoCosim.h` | `MyProject/include/CMSumoCosim.h` |
| `lib/CMSumoCosim_win64.a` | `MyProject/lib/CMSumoCosim_win64.a` |
| `lib/CMSumoCosim_xeno.a` | `MyProject/lib/CMSumoCosim_xeno.a` |
| `CoSim/examples/CoSim/*` | `MyProject/CoSim/` (mapping + schema + `SUMO/` + `alignment.CSV`, …) |
| Optional `CoSim/examples/Data/*` | merge into `MyProject/Data/` (TestRuns, roads, …) |
| Optional `CoSim/Orchestrator/` | `MyProject/CoSim/Orchestrator/` |
| Optional `CoSim/Cosim_bridge/` | `MyProject/CoSim/Cosim_bridge/` (HIL host bridge) |

```bat
mkdir MyProject\include
mkdir MyProject\lib
mkdir MyProject\CoSim
mkdir MyProject\bin
xcopy /E /I CMSumoCosim\CoSim\examples\CoSim MyProject\CoSim
xcopy /E /I CMSumoCosim\CoSim\Cosim_bridge MyProject\CoSim\Cosim_bridge
```

### Folder name must be exactly `CoSim`

The application looks for `CoSim/cosim_vehicle_mapping.json`. Windows Office often ignores case (`Cosim` may appear to work). **Linux HIL (`rt`) is case-sensitive** — wrong casing means the mapping never loads, even with a good binary.

### Create `bin/` before Install

Visual Studio **CarMakerInstall** / `transferapp` / `make install` copy the app into `../bin`. If `MyProject/bin` is missing you get:

`Failed to read attributes of CarMaker.win64.exe: No such file or directory`

You can also build only the **CarMaker** project and skip Install.

---

## Step 2 — User patch  

Stock apps ship `src/User.c`. CoSim needs C++ and the kit API.

### Fast path

1. Remove or rename `src/User.c` (do not compile both).
2. Copy `Src/User_CMSumoCosim_patch.cpp` → `src/User.cpp`.
3. Keep stock `User.h` / `IOVec.h` unless you already customized them.

### Manual path

Rename `User.c` → `User.cpp`, add `#include "CMSumoCosim.h"`, and call:

| Hook | Call |
|------|------|
| `User_TestRun_Start_atEnd` | Keep XENO `IOConf_DeclQuants()` if present; then `(void)CMSumoCosim_TestRun_Start();` |
| `User_TestRun_Start_Finalize` | `if (CMSumoCosim_TestRun_Start_Finalize() != 0) return -1;` |
| `User_Traffic_Calc` | `return CMSumoCosim_Traffic_Calc(dt);` |
| `User_TestRun_End_First` | `return CMSumoCosim_TestRun_End_First();` |
| `User_End` | `return CMSumoCosim_End();` |
| `User_Cleanup` | `CMSumoCosim_Cleanup();` |

Details: [`Src/User_hooks.md`](../Src/User_hooks.md).  
`IO.c` / `IO.cpp` stay stock.

---

## Step 3 — Makefile (HIL / cmmake)

Stock `PROJECTNAME` Makefiles are not enough.

### Select toolchain with `CM_TARGET`

Wrong (ignores `CM_TARGET=xeno`):

```make
include C:/IPG/carmaker/win64-14.1.1/include/MakeDefs.win64
```

Right:

```make
CM_ROOT   ?= C:/IPG/carmaker/win64-14.1.1
CM_TARGET ?= win64
include $(CM_ROOT)/include/MakeDefs.$(CM_TARGET)
```

### Include path, library, C++ link

```make
INC_CFLAGS +=		-I../include -I../lib/$(ARCH) -I../lib

LD_LIBS =		$(CAR_LIB) \
			$(CARMAKER_LIB) $(DRIVER_LIB) $(ROAD_LIB) $(TIRE_LIB) $(MIO_LIB)
LD_LIBS +=		../lib/CMSumoCosim_$(ARCH).a

APP_LINKER = $(CXX)
APP_LD_OS  = $(LDXX_LIBS_OS)

OBJS =			CM_Main.o CM_Vehicle.o User.o IO.o
```

Link with `$(APP_LINKER)` and `$(APP_LD_OS)`, not plain `$(CC)` only.  

Full example: [`Src/Makefile.example`](../Src/Makefile.example).

### Build HIL

```bat
cd MyProject\src
cmmake clean
cmmake CM_TARGET=xeno
```

If needed: `C:\IPG\carmaker\win64-14.1.1\bin\cmmake.exe CM_TARGET=xeno`.

**Always `clean` when switching** between win64 and xeno objects.

| Symptom | Fix |
|---------|-----|
| `CMSumoCosim.h: No such file` | `-I../include` and header under `include/` |
| Still using win64 defs with `CM_TARGET=xeno` | Use `MakeDefs.$(CM_TARGET)`, not hardcoded `.win64` |
| Undefined `CMSumoCosim_*` | `LD_LIBS += ../lib/CMSumoCosim_$(ARCH).a` |
| `NUL character` / `missing separator` in Makefile | File saved as UTF-16 — save as UTF-8 |
| `No rule to make target 'CM_Main.o'` | `CM_Main.cpp` / `.c` missing from `src/` |

---

## Step 4 — Visual Studio office build

Office TraCI **must** use **MSVC**. Eclipse Sumo ships MSVC `.lib` files.

Checklist (Debug **and** Release | x64):

1. ClCompile **`User.cpp`** (not `User.c`). Do not compile kit `Core`/`SUMOsim` sources into the app.
2. Include dirs: `../include` and `C:/Program Files (x86)/Eclipse/Sumo/include` (adjust if needed).
3. Library dirs: Sumo `bin` and `../lib`.
4. Dependencies: `libtracicpp.lib;libsumocpp.lib;../lib/CMSumoCosim_win64.a`
5. Import `MSVS_Defs.props` from **14.1.1** (also fix `CarMakerInstall.vcxproj` if it still points `.c` files instead of the modified ones.\).

Copy-paste notes: [`Src/CarMaker.vcxproj.snippet.md`](../Src/CarMaker.vcxproj.snippet.md).

Rebuild **Release | x64** → `src/CarMaker.win64.exe`. After Install, also refresh `bin/CarMaker.win64.exe` so the GUI does not keep an older binary.

| Symptom | Fix |
|---------|-----|
| Cannot open `CMSumoCosim.h` | Add `../include` |
| Unresolved `CMSumoCosim_*` | Link `../lib/CMSumoCosim_win64.a` |
| Unresolved libsumo/libtraci | Sumo lib path + `libsumocpp` / `libtracicpp` |
| Install / transferapp fails | Create `MyProject/bin` |

---

## Step 5 — Minimal runtime check

1. Mapping at **`MyProject/CoSim/cosim_vehicle_mapping.json`** with schema beside it (copy from kit `CoSim/examples/CoSim/`).
2. `"cosim_enable": true` and a valid `"sumo_sumocfg_path"` (point at your project SUMO, not a leftover kit path).
3. Office: `"rt_host_rx_enable"` can remain `false`. HIL: enable RT keys and match [Cosim_bridge](04_cosim_bridge.md) ports.
4. TestRun traffic object names must match `traffic_slots[].ipg_name`.

More detail: [02 — first test](02_orchestrator_and_first_test.md), [03 — JSON mapping](03_json_mapping.md).

Optional override: environment variable `COSIM_VEHICLE_MAPPING_JSON` = full path to the JSON.

---

## Quick recipe

```bat
REM 1) Copy include/, lib/
REM 2) xcopy kit CoSim\examples\CoSim -> MyProject\CoSim
REM 3) mkdir MyProject\bin
REM 4) Src\User_CMSumoCosim_patch.cpp -> src\User.cpp
REM 5) Patch Makefile from Src\Makefile.example
REM 6) Patch CarMaker.vcxproj / props (Sumo + CMSumoCosim_win64.a + ../include)
REM 7) Office:
msbuild CarMaker.sln /t:CarMaker /p:Configuration=Release /p:Platform=x64
REM 8) HIL:
cmmake clean
cmmake CM_TARGET=xeno
```
