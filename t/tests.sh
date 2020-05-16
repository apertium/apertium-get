#!/bin/bash

set -e -u


cd "$(dirname "$0")"

canonpath () {
    # OS X doesn't have realpath :-/
    realpath "$1" 2>/dev/null || greadlink -f "$1" 2>/dev/null || ( cd "$(dirname "$1")" && echo "$(pwd)"/"$(basename "$1")")
}
prog=$(canonpath ../apertium-get.py)

tmp=$(mktemp -d -t apertium-get.XXXXXXXXXXX)
trap 'rm -rf "${tmp}"' EXIT


# TESTS:
echo "Show help …"
diff <("${prog}" -h 2>&1) unarg.expected

echo "List trunk …"
diff <("${prog}" -l trunk) trunk.expected

echo "Full pair listing should be big …"
[[ $("${prog}" -l | wc -l) -ge 200 ]]

echo "Full module listing should be fairly big …"
[[ $("${prog}" -m | wc -l) -ge 100 ]]

echo "Try to set up nno-nob with --depth 1 …"
(
    cd "${tmp}"
    "${prog}" -x foo -x bar -d 1 nno-nob 2>&1
    cd apertium-nno-nob
    make test >&2
) > nno-nob.log || ( cat nno-nob.log; exit 1 )

echo "Try to set up nno-nob again (skipping build) …"
(
    cd "${tmp}"
    "${prog}" -s nno-nob 2>&1 | grep -i skipping
) > nno-nob.2.log || ( cat nno-nob.2.log; exit 1 )

echo "Try to set up fr-es …"
(
    cd "${tmp}"
    "${prog}" fr-es 2>&1
    cd apertium-fr-es
    make test >&2
) > fr-es.log || ( cat fr-es.log; exit 1 )

echo "Try to set up ibo …"
(
    cd "${tmp}"
    "${prog}" ibo 2>&1
) > ibo.log || ( cat ibo.log; exit 1 )
