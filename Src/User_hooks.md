# User patch hooks — CMSumoCosim vs stock PROJECTNAME

Start from CarMaker 14.1.1 stock `User.c`, rename to **`User.cpp`**, and/or replace its content with `User_CMSumoCosim_patch.cpp`.

Full install (Makefile + **vcxproj**) is in `docs/Install_CM_14.1.1.md`.

## Include

```cpp
#include "User.h"
#include "CMSumoCosim.h"
```

## Calls

```cpp
int User_TestRun_Start_atEnd(void)
{
#if defined(XENO)
    IOConf_DeclQuants();
#endif
    (void)CMSumoCosim_TestRun_Start();
    return 0;
}

int User_TestRun_Start_Finalize(void)
{
    if (CMSumoCosim_TestRun_Start_Finalize() != 0)
        return -1;
    return 0;
}

int User_Traffic_Calc(double dt)
{
    return CMSumoCosim_Traffic_Calc(dt);
}

int User_TestRun_End_First(void)
{
    return CMSumoCosim_TestRun_End_First();
}

int User_End(void)
{
    return CMSumoCosim_End();
}

void User_Cleanup(void)
{
    CMSumoCosim_Cleanup();
}
```

## Build reminders

| Target | Tool | Library |
|--------|------|---------|
| Office win64 | **MSVC** (`CarMaker.vcxproj`) | `../lib/CMSumoCosim_win64.a` + Sumo `libsumocpp` / `libtracicpp` |
| HIL xeno | **cmmake** `CM_TARGET=xeno` | `../lib/CMSumoCosim_xeno.a` |

Makefile must have `INC_CFLAGS += -I../include` and `LD_LIBS += ../lib/CMSumoCosim_$(ARCH).a`.  
MSVC must add the same include/lib entries in **vcxproj/props** (not Makefile-only).

## Out of scope

Do not add VILaddon, UserCAN, Vehico, or OxTS for a CoSim-only consumer.
