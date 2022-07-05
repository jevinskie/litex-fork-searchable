#undef NDEBUG
#include <cassert>

#include "vpi.h"
#include <vpi_user.h>
// #include "Vsim_fake.h"

#define XSTR(s) #s
#define STR(s) XSTR(s)

#define UNUSED(x) ((void)(x))

static s_vpi_time nextsimtime{.type = vpiSimTime};

extern "C" int litex_sim_main(int argc, const char *argv[]);

static uint64_t main_time;
static bool finished;

void litex_sim_eval(void *vsim, uint64_t time_ps) {
    UNUSED(vsim);
    UNUSED(time_ps);
}

void litex_sim_init_cmdargs(int argc, const char *argv[]) {
    UNUSED(argc);
    UNUSED(argv);
}

void litex_sim_init_tracer(void *vsim, long start, long end) {
    UNUSED(vsim);
    UNUSED(start);
    UNUSED(end);
}

void litex_sim_tracer_dump() {}

int litex_sim_got_finish() {
    return finished;
}

#if VM_COVERAGE
void litex_sim_coverage_dump() {
    assert(!"VPI coverage is not supported.");
}
#endif

void litex_sim_dump() {}

static int end_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    finished = true;
    return 0;
}

static void register_next_time_cb();

static int next_time_cb(t_cb_data *cbd) {
    main_time = ((uint64_t)cbd->time->high << 32) | cbd->time->low;
    register_next_time_cb();
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
    // VPI doesn't callback for time 0 so do it ourself
    s_vpi_time t0{};
    s_cb_data cbt0{.time = &t0};
    next_time_cb(&cbt0);

    s_cb_data eos_cbd{.reason = cbEndOfSimulation, .cb_rtn = end_of_sim_cb};
    auto eos_cb = vpi_register_cb(&eos_cbd);
    assert(eos_cb && vpi_free_object(eos_cb));
    
    const char *argv[] = {STR(TOPLEVEL), nullptr};
    litex_sim_main(1, argv);
    return 0;
}

static void litex_register() {
    s_cb_data cbd{.reason = cbEndOfCompile, .cb_rtn = end_of_compile_cb};
    vpi_register_cb(&cbd);
}

void (*vlog_startup_routines[])() = {
    litex_register,
    nullptr,
};
