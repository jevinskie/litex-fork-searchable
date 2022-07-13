// Copyright (c) 2022      Jevin Sweval <jevinsweval@gmail.com>

#pragma once

#ifdef __cplusplus
extern "C" {
#endif


#ifdef LITEX_VPI
#include <stdint.h>

extern int32_t vpi_printf(const char *fmt, ...)
#if defined(__MINGW32__)
    __attribute__((format (gnu_printf,1,2)));
#elif defined(__GNUC__)
    __attribute__((format (printf,1,2)));
#else
    ;
#endif

#define printf(fmt, ...) do { vpi_printf((fmt), ##__VA_ARGS__); } while (0)
#define fprintf(fh, fmt, ...) do { vpi_printf((fmt), ##__VA_ARGS__); } while (0)
#endif

#ifdef __cplusplus
}; // extern "C"
#endif
