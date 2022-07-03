#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

void litex_sim_init_cmdargs(int argc, const char *argv[]);
void litex_sim_eval(void *vsim, uint64_t time_ps);
void litex_sim_init_tracer(void *vsim, long start, long end);
void litex_sim_tracer_dump(void);
int litex_sim_got_finish(void);
#if VM_COVERAGE
void litex_sim_coverage_dump(void);
#endif

#ifdef __cplusplus
} // extern "C"
#endif
