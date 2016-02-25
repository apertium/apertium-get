#!/bin/bash

set -e -u


cd "$(dirname "$0")"

canonpath () {
    # OS X doesn't have realpath :-/
    realpath "$1" 2>/dev/null || greadlink -f "$1" 2>/dev/null || ( cd "$(dirname "$1")" && echo "$(pwd)"/"$(basename "$1")")
}
prog=$(canonpath ../apertium-get)

tmp=$(mktemp -d -t apertium-get.XXXXXXXXXXX)
trap 'rm -rf "${tmp}"' EXIT


# TESTS:
echo "Show help …"
diff <("${prog}" -? 2>&1) unarg.expected

echo "List trunk …"
diff <("${prog}" -l trunk) trunk.expected

echo "Full listing should be big …"
[[ $("${prog}" -l | wc -l) -ge 200 ]]

echo "Try to set up nno-nob …"
(
    cd "${tmp}"
    "${prog}" -x foo -x bar nno-nob 2>&1
    cd apertium-nno-nob
    make test >&2
) > nno-nob.log || ( cat nno-nob.log; exit 1 )

echo "Try to set up fr-es …"
(
    cd "${tmp}"
    "${prog}" fr-es 2>&1
    cd apertium-fr-es
    make test >&2
) > fr-es.log || ( cat fr-es.log; exit 1 )

echo "Try to set up sme-nob …"
(
    cd "${tmp}"
    "${prog}" sme-nob 2>&1
    cd apertium-sme-nob
    make test >&2
) > sme-nob.log || ( cat sme-nob.log exit 1 )
