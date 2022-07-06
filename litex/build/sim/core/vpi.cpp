#undef NDEBUG
#include <cassert>
#include <cinttypes>

#include "vpi.h"
#include <vpi_user.h>
// #include "Vsim_fake.h"

#define XSTR(s) #s
#define STR(s) XSTR(s)

#define UNUSED(x) ((void)(x))

#ifndef _WIN32
#define unlikely(expr) __builtin_expect(!!(expr), 0)
#define likely(expr) __builtin_expect(!!(expr), 1)
#else
#define unlikely(expr) (expr)
#define likely(expr) (expr)
#endif

static s_vpi_time nextsimtime{.type = vpiSimTime};
static bool finished;

static int end_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    finished = true;
    return 0;
}

static void register_next_time_cb();

static int next_time_cb(t_cb_data *cbd) {
    sim_time_ps = ((uint64_t)cbd->time->high << 32) | cbd->time->low;
    // printf("time: %" PRIu64 "\n", sim_time_ps);
    // assert(event_base_loop(base, EVLOOP_NONBLOCK) >= 0);
    // litex_sim_event_cb(0, 0, nullptr);
    if (likely(sim_time_ps)) {
        register_next_time_cb();
    }
    return 0;
}

static void register_next_time_cb() {
    s_cb_data nt_cbd{.reason = cbNextSimTime, .cb_rtn = next_time_cb, .time = &nextsimtime};
    auto nt_cb = vpi_register_cb(&nt_cbd);
    assert(nt_cb && vpi_free_object(nt_cb));
}

static int end_of_compile_cb(t_cb_data *cbd) {
    UNUSED(cbd);

    register_next_time_cb();

    // VPI doesn't call NextSimTime for time 0 so do it ourselves
    s_vpi_time t0{.type = vpiSimTime};
    s_cb_data t0_cbd{.reason = cbNextSimTime, .time = &t0};
    next_time_cb(&t0_cbd);

    s_cb_data eos_cbd{.reason = cbEndOfSimulation, .cb_rtn = end_of_sim_cb};
    auto eos_cb = vpi_register_cb(&eos_cbd);
    assert(eos_cb && vpi_free_object(eos_cb));



    return 0;
}

static void litex_register() {
    printf("litex_register\n");
    s_cb_data cbd{.reason = cbEndOfCompile, .cb_rtn = end_of_compile_cb};
    vpi_register_cb(&cbd);
}

void (*vlog_startup_routines[])() = {
    litex_register,
    nullptr,
};
