#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#define XSTR(s) #s
#define STR(s) XSTR(s)

#define UNUSED(x) ((void)(x))

#include <stdint.h>

#include <event2/event.h>

extern uint64_t sim_time_ps;
extern struct event_base *base;

void litex_sim_init(void **out);
int litex_sim_initialize_all(void **sim, void *base);
int litex_sim_sort_session();

int litex_sim_got_finish(void);

#ifdef __cplusplus
} // extern "C"
#endif
