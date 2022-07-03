#undef NDEBUG
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <vpi_user.h>

#ifndef _WIN32
#define ALIGNED(x) __attribute__((aligned((x))))
#else
#define ALIGNED(x) __declspec(align((x)))
#endif

int signal_change_cb(struct t_cb_data *cbd) {

}

#include "vpi_init_generated.cpp"

extern "C" void litex_sim_init(void **out) {

}

