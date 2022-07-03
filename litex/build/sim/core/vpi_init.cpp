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

enum tagged_ptr_kind {
    TAG_U8 = 0,
    TAG_U16 = 1,
    TAG_U32 = 2,
};

constexpr uintptr_t tagged_ptr_mask = 3;

void *tag_ptr(void *ptr, tagged_ptr_kind kind) {
    return (void *)((uintptr_t)ptr | (uintptr_t)kind);
}

int signal_change_cb(struct t_cb_data *cbd) {
    const auto tagged_val_ptr = (uintptr_t)cbd->user_data;
    const auto kind = (tagged_ptr_kind)(tagged_val_ptr & tagged_ptr_mask);
    const auto val = (uint32_t)cbd->value->value.integer;
    const auto ptr = (void *)(tagged_val_ptr & ~tagged_ptr_mask);
    switch (kind) {
    case TAG_U8:
        *(uint8_t *)ptr = val;
        break;
    case TAG_U16:
        *(uint16_t *)ptr = val;
        break;
    case TAG_U32:
        *(uint32_t *)ptr = val;
        break;
    default:
        assert(!"bad pointer tag");
        break;
    }
    return 0;
}

#include "vpi_init_generated.cpp"

extern "C" void litex_sim_init(void **out) {

}

