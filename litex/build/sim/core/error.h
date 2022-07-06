/* Copyright (C) 2017 LambdaConcept */

#pragma once

#include <stdio.h>

#ifdef USE_VPI
#include <vpi_user.h>
#endif

#define RC_OK 0
#define RC_ERROR -1
#define RC_INVARG -2
#define RC_NOENMEM -3
#define RC_JSERROR -4
#define RC_JSMISSINGKEY -5

#ifndef USE_VPI
#define eprintf(format, ...) fprintf (stderr, "%s:%d "format, __FILE__, __LINE__,  ##__VA_ARGS__)
#else
#define eprintf(fmt, ...)                                                                          \
    do {                                                                                           \
        vpi_printf("ERROR: %s:%d " fmt, __FILE__, __LINE__, ##__VA_ARGS__);                   \
        vpi_control(vpiFinish, 1);                                                                 \
    } while (0)
#endif