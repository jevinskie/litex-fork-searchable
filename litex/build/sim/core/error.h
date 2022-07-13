/* Copyright (C) 2017 LambdaConcept */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#define RC_OK 0
#define RC_ERROR -1
#define RC_INVARG -2
#define RC_NOENMEM -3
#define RC_JSERROR -4
#define RC_JSMISSINGKEY -5

#ifndef LITEX_VPI
#include <stdio.h>

#define eprintf(format, ...) fprintf (stderr, "%s:%d "format, __FILE__, __LINE__,  ##__VA_ARGS__)
#else
#include <stdint.h>

extern int32_t vpi_printf(const char *fmt, ...)
#if defined(__MINGW32__)
    __attribute__((format(gnu_printf, 1, 2)));
#elif defined(__GNUC__)
    __attribute__((format(printf, 1, 2)));
#else
    ;
#endif
extern void vpi_control(int32_t operation, ...);
#define vpiFinish 67

#define eprintf(fmt, ...)                                                                          \
    do {                                                                                           \
        vpi_printf("ERROR: %s:%d " fmt, __FILE__, __LINE__, ##__VA_ARGS__);                        \
        vpi_control(vpiFinish, 1);                                                                 \
    } while (0)
#endif

#ifdef __cplusplus
}; // extern "C"
#endif
