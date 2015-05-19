#!/bin/bash

set -e -u


cd "$(dirname "$0")"
prog=$(realpath ../apertium-get)

tmp=$(mktemp -d -t apertium-get.XXXXXXXXXXX)
trap 'rm -rf "${tmp}"' EXIT


# TESTS:
echo "Show help …"
diff <("${prog}" -? 2>&1) unarg.expected

echo "List incubator …"
diff <("${prog}" -l incubator) incubator.expected

echo "Full listing should be big …"
[[ $("${prog}" -l | wc -l) -ge 200 ]]

echo "Try to install nno-nob …"
(
    cd "${tmp}"
    "${prog}" nno-nob 2>&1
    cd apertium-nno-nob
    make test >&2
) > nno-nob.log

echo "Try to install en-es …"
(
    cd "${tmp}"
    "${prog}" en-es 2>&1
    cd apertium-en-es
    make test >&2
) > en-es.log
