#!/usr/bin/env python

"""
DCP Upload Service Example Validator

This validator will be called with a single argument, the file to be validated.

As an example we will test the file to see if its size is odd or even.
If size is even we will consider it a good file, print "valid" and exit with status 0.
If size is odd we will consider it to have failed validation, print "invalid" and exit with status 1.
"""

import os
import sys

if len(sys.argv) != 2:
    raise RuntimeError("expected one argument")

file_path = sys.argv[1]

stat_info = os.stat(file_path)

if stat_info.st_size % 2 == 0:
    print("valid")
    exit(0)
else:
    print("invalid")
    exit(1)
