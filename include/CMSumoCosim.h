/* CMSumoCosim.h — public CarMaker↔SUMO co-simulation API (CM 14.1.1)
 *
 * Two arch libraries, one header:
 *   lib/CMSumoCosim_win64.a  — in-process TraCI/libsumo
 *   lib/CMSumoCosim_xeno.a   — UDP RT bridge (native_cosim on host)
 *
 * Link: LD_LIBS += ../lib/CMSumoCosim_$(ARCH).a
 * Patch: call from User_* hooks (see templates/User_hooks.md).
 */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/** Non-RT: load/reload CoSim/cosim_vehicle_mapping.json (mtime-aware). */
int  CMSumoCosim_TestRun_Start(void);

/** RT: reset pool, hide slots, then init_SUMO_sim (office) or open RT sockets (XENO). */
int  CMSumoCosim_TestRun_Start_Finalize(void);

/** Per-cycle traffic / TraCI / RT Hermite dispatch (call from User_Traffic_Calc). */
int  CMSumoCosim_Traffic_Calc(double dt);

/** Tear down in-process SUMO if this session started it. */
int  CMSumoCosim_TestRun_End_First(void);

/** Process end: close RT sockets + leftover SUMO. */
int  CMSumoCosim_End(void);

/** Final cleanup (same as End for socket/SUMO ownership). */
void CMSumoCosim_Cleanup(void);

#ifdef __cplusplus
}
#endif
