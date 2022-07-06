#undef NDEBUG
#include <cassert>
#include <cinttypes>

#include "error.h"
#include "vpi.h"
#include <vpi_user.h>

#ifdef _WIN32
#include <winsock2.h>
#pragma comment(lib, "ws2_32.lib")
#endif

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

extern "C" void litex_vpi_register_signal_callbacks();

static s_vpi_time nextsimtime{.type = vpiSimTime};
static bool finished;

static int end_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    finished = true;
    return 0;
}

static void register_next_time_cb();

static void tick() {
    assert(event_base_loop(base, EVLOOP_NONBLOCK) >= 0);
}

static int next_time_cb(t_cb_data *cbd) {
    sim_time_ps = ((uint64_t)cbd->time->high << 32) | cbd->time->low;
    tick();
    register_next_time_cb();
    return 0;
}

static void register_next_time_cb() {
    s_cb_data nt_cbd{.reason = cbNextSimTime, .cb_rtn = next_time_cb, .time = &nextsimtime};
    auto nt_cb = vpi_register_cb(&nt_cbd);
    assert(nt_cb && vpi_free_object(nt_cb));
}

static void dummy_cb(evutil_socket_t sock, short which, void *arg) {
    // eprintf("dummy_cb\n");
}

void litex_sim_init(void **out) {
    UNUSED(out);
    // dummy
    // eprintf("litex_sim_init\n");
    litex_vpi_register_signal_callbacks();
}

static int start_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    int ret = RC_ERROR;
    static struct event *ev;

    printf("hello world\n");
#ifdef _WIN32
    WSADATA wsa_data;
    WSAStartup(0x0201, &wsa_data);
#endif

    base = event_base_new();
    if (!base) {
        eprintf("Can't allocate base\n");
    }

    void *dummy_vsim;
    if (RC_OK != (ret = litex_sim_initialize_all(&dummy_vsim, base))) {
        eprintf("Can't initialize sim modules or pads\n");
    }

    if (RC_OK != (ret = litex_sim_sort_session())) {
        eprintf("Can't sort session lists\n");
    }

    struct timeval tv {
        .tv_sec = 0, .tv_usec = 0
    };
    ev = event_new(base, -1, EV_PERSIST, dummy_cb, nullptr);
    event_add(ev, &tv);

    // eprintf("reg_cb\n");

    // tick for time 0
    tick();
    register_next_time_cb();

    s_cb_data eos_cbd{.reason = cbEndOfSimulation, .cb_rtn = end_of_sim_cb};
    auto eos_cb = vpi_register_cb(&eos_cbd);
    assert(eos_cb && vpi_free_object(eos_cb));

    return 0;
}

static int end_of_compile_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    s_cb_data sos_cbd{.reason = cbStartOfSimulation, .cb_rtn = start_of_sim_cb};
    auto sos_cb = vpi_register_cb(&sos_cbd);
    assert(sos_cb && vpi_free_object(sos_cb));
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
