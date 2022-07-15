#undef NDEBUG
#include <cassert>
#include <cinttypes>
#include <cstring>

#include "error.h"
#include "modules.h"
#include "sim.h"
#include "sim_header.h"
#include "vpi.h"

#include <event2/event.h>
#include <vpi_user.h>

#ifdef _WIN32
#include <winsock2.h>
#pragma comment(lib, "ws2_32.lib")
#endif

#define XSTR(s) #s
#define STR(s) XSTR(s)

#define UNUSED(x) ((void)(x))

#ifndef _WIN32
#define unlikely(x) __builtin_expect(!!(x), 0)
#define likely(x) __builtin_expect(!!(x), 1)
#define UNUSED_FUNC __attribute__((unused))
#else
#define unlikely(x) (x)
#define likely(x) (x)
#define UNUSED_FUNC
#endif

extern "C" session_list_s *sesslist;
extern "C" void litex_vpi_signals_register_callbacks();
extern "C" void litex_vpi_signals_writeback();

static s_vpi_time nextsimtime{.type = vpiSimTime};
static struct event *ev;

UNUSED_FUNC static int signal_uint8_t_change_cb(struct t_cb_data *cbd) {
    *(uint8_t *)cbd->user_data = cbd->value->value.integer;
    return 0;
}

UNUSED_FUNC static int sigsnal_uint16_t_change_cb(struct t_cb_data *cbd) {
    *(uint16_t *)cbd->user_data = cbd->value->value.integer;
    return 0;
}

UNUSED_FUNC static int signal_uint32_t_change_cb(struct t_cb_data *cbd) {
    *(uint32_t *)cbd->user_data = cbd->value->value.integer;
    return 0;
}

#include "vpi_init_generated.cpp"

static void register_rw_sync_cb();

static int rw_sync_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    litex_vpi_signals_writeback();
    return 0;
}

static void register_rw_sync_cb() {
    s_vpi_time rwst{.type = vpiSuppressTime};
    s_cb_data rws_cbd{.reason = cbReadWriteSynch, .cb_rtn = rw_sync_cb, .time = &rwst};
    auto rws_cb = vpi_register_cb(&rws_cbd);
    assert(rws_cb && vpi_free_object(rws_cb));
}

static void tick() {
    // printf("t: %" PRIu64 "\n", sim_time_ps);
    assert(event_base_loop(base, EVLOOP_NONBLOCK) >= 0);

    session_list_s *s{};

    for (s = sesslist; s; s = s->next) {
        if (s->tickfirst)
            s->module->tick(s->session, sim_time_ps);
    }

    for (s = sesslist; s; s = s->next) {
        if (!s->tickfirst)
            s->module->tick(s->session, sim_time_ps);
    }

    register_rw_sync_cb();
}

static void register_next_time_cb();

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

void litex_sim_init(void **out) {
    UNUSED(out);
    litex_vpi_signals_register_callbacks();
}

static int end_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    for (auto *s = sesslist; s; s = s->next) {
        if (s->module->close) {
            s->module->close(s);
        }
    }
    event_base_loopbreak(base);
    return 0;
}

static int start_of_sim_cb(t_cb_data *cbd) {
    UNUSED(cbd);
    int ret = RC_ERROR;

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
