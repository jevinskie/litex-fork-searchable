#undef NDEBUG
#include <cassert>

#include "vpi.h"
#include <vpi_user.h>
// #include "Vsim_fake.h"

#define XSTR(s) #s
#define STR(s) XSTR(s)

#define UNUSED(x) ((void)(x))

extern "C" int litex_sim_main(int argc, const char *argv[]);

struct Vsim {
    uint8_t foo;
    void eval(){
        printf(".");
    }
};

uint64_t main_time = 0;
Vsim *g_sim        = nullptr;
bool finished;

void litex_sim_eval(void *vsim, uint64_t time_ps) {
    Vsim *sim = (Vsim *)vsim;
    sim->eval();
    main_time = time_ps;
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

static int end_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    finished = true;
    return 0;
}

static int end_of_compile_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    printf("end of compile\n");
    s_cb_data eos_cbd{.reason = cbEndOfSimulation, .cb_rtn = end_of_sim_cb};
    assert(vpi_register_cb(&eos_cbd));
    const char *argv[] = {STR(TOPLEVEL), NULL};
    litex_sim_main(1, argv);
    return 0;
}

static void litex_register() {
    s_cb_data cbd{.reason = cbEndOfCompile, .cb_rtn = end_of_compile_cb};
    vpi_register_cb(&cbd);
}

void (*vlog_startup_routines[])() = {
    litex_register,
    NULL,
};
