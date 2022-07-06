#undef NDEBUG
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <vpi_user.h>

#include "vpi.h"
#include "sim_header.h"

int signal_uint8_t_change_cb(struct t_cb_data *cbd) {
    *(uint8_t *)cbd->user_data = cbd->value->value.integer;
    return 0;
}

int signal_uint16_t_change_cb(struct t_cb_data *cbd) {
    *(uint16_t *)cbd->user_data = cbd->value->value.integer;
    return 0;
}

int signal_uint32_t_change_cb(struct t_cb_data *cbd) {
    *(uint32_t *)cbd->user_data = cbd->value->value.integer;
    return 0;
}


#include "vpi_init_generated.cpp"
