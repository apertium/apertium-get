#!/bin/bash
help2man -N -n 'apertium-get' --version-string "$1" ./apertium-get.py | perl -wpne 's/\.py//ig;' > apertium-get.1
