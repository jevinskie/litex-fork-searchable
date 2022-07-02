/* Copyright (C) 2017 LambdaConcept */

#pragma once

#define RC_OK 0
#define RC_ERROR -1
#define RC_INVARG -2
#define RC_NOENMEM -3
#define RC_JSERROR -4
#define RC_JSMISSINGKEY -5

#define eprintf(format, ...) fprintf (stderr, "%s:%d "format, __FILE__, __LINE__,  ##__VA_ARGS__)
