#!/bin/bash

[[ "${BASH_SOURCE[0]}" != "${0}" ]] || set -e -u

### Globals:

declare -r gitroot=https://raw.githubusercontent.com/apertium
declare -ar pmodules=(trunk staging nursery incubator)
declare -ar lmodules=(languages incubator)

declare -r svnroot_giella=https://victorio.uit.no/langtech/trunk


### Functions:
discover_url_apertium () {
    local -r dir=$1
    local url=
    local -a modules
    if [[ ${dir} = *-*-* ]]; then
        modules=( "${pmodules[@]}" )
    else
        modules=( "${lmodules[@]}" )
    fi
    for module in "${modules[@]}"; do
        submodules=$(curl -Ss --fail "${gitroot}/apertium-${module}/master/.gitmodules")
        # url="${svnroot}${module}/${dir}"
        if url=$(grep "[[:space:]]*url = .*/${dir}.git$" <<<"${submodules}"); then
            url=${url#*url = }
            # TODO: Option to use ssh urls?
            url=${url/git@github.com:/https:\/\/github.com\/}
            echo "Assuming git url of ${dir} is ${url}" >&2
            echo "${url}"
            return 0
        fi
    done
    echo "WARNING: Couldn't find git url of ${dir}" >&2
    if ! msg=$(curl -Ss --fail "${gitroot}/apertium-languages/master/.gitmodules"); then
        printf "\n%s\n\n" "${msg}" >&2
        echo "You may want to see http://wiki.apertium.org/wiki/Using_SVN#Host_not_found_when_using_proxy" >&2
        echo "or make sure you have a working internet connection." >&2
    fi
    return 1
}
discover_url_giella () {
    local -r dir=$1
    local -r url="${svnroot_giella}/${dir}"
    echo "Assuming SVN url of ${dir} is ${url}" >&2
    echo "${url}"
}

dir_of_dep () {
    if [[ $1 = giella-* ]]; then
        echo "langs/${1##giella-}"
    else
        echo "$1"
    fi
}
bins_of_dep () {
    if [[ $1 = giella-* ]]; then
        echo "langs/${1##giella-}/tools/mt/apertium"
    else
        echo "$1"
    fi
}

make_dep () {
    local -r dep=$1
    local -r dir=$(dir_of_dep "${dep}")
    # Let cwd be GTHOME from here on in; langs should exist under this dir:
    GTHOME=$(pwd)
    GTCORE=$GTHOME/gtcore
    export GTHOME
    export GTCORE
    (
        cd "${dir}"
        pwd
        ./autogen.sh
        if [[ ${dep} = giella-* ]]; then
            ./configure --enable-apertium --with-hfst --enable-syntax
            V=1 make                    # giella so memory hungry, -j1
        elif [[ ${dep} = gtcore ]]; then
            ./configure
            make -j3
        else
            make -j3
        fi
    )
}

is_dep_updated () {
    local -r dep=$1
    local -r dir=$(dir_of_dep "${dep}")
    if [[ -d ${dir} ]]; then
        if [[ -d "${dir}/.git" ]]; then
            if [[ -z "$(cd "${dir}" && git fetch --dry-run)" ]]; then
                echo yes
                return 0
            else
                echo no
                return 0
            fi
        fi
        if [[ -z $(svn status -qu "${dir}") ]]; then
            echo yes
            return 0
        fi
    fi
    echo no
}

get_dep () {
    local -r depth=$1
    local -r dep=$2
    local -r dir=$(dir_of_dep "${dep}")
    local url=
    if [[ -d ${dir} ]]; then
        (
            cd "${dir}"
            printf "Updating existing %s (%s)\n" "${dir}" "$(pwd)"
            if [[ -d .git ]]; then
                git pull
            else
                svn up
            fi
        )
    else
        if [[ ${dep} = giella-* || ${dep} = gtcore ]]; then
            url=$(discover_url_giella "${dir}") && svn checkout "${url}" "${dir}"
        else
            url=$(discover_url_apertium "${dir}") && if [[ $depth -gt 0 ]]; then
                git clone --depth "${depth}" "${url}" "${dir}"
            else
                git clone "${url}" "${dir}"
            fi
        fi
    fi
}

in_array () {
    local e
    for e in "${@:2}"; do
        [[ "$e" == "$1" ]] && return 0
    done
    return 1
}

get_pair () {
    local -r depth=$1
    local -r keep_going=$2
    local -r skip_if_up_to_date=$3
    local -r pair=apertium-${4##apertium-}
    # shellcheck disable=SC2124
    local -r skip="${@:5}" # intentionally assigning array to string

    if [[ ${skip_if_up_to_date} == true && $(is_dep_updated "${pair}") == "yes" ]]; then
        printf "Existing pair %s is already up to date. Skipping build step.\\n" "${pair}"
        return 0
    fi

    get_dep "${depth}" "${pair}"
    # Mac has ancient bash, so no declare -A for us
    local -a deps=()
    local -a depn=()
    while read -r n dep; do
        local orglang
        orglang=$(split_org_langs "${dep}")
        local lang=${orglang##* }
        # shellcheck disable=SC2068
        if in_array "${lang}" ${skip[@]}; then # intentionally unquoted skip
            echo
            echo "Skipping data ${dep} as instructed."
            echo
        else
            deps+=( "${dep}" )
            depn+=( "${n}" )
        fi
    done < <(awk -F'[][[:space:]]+' '/^ *AP_CHECK_LING\(/ && $2 && $4 {print $2, $4}' "${pair}"/configure.ac)

    if [[ ${#deps[@]} -ne 0 ]]; then
        for dep in "${deps[@]}"; do
            if ! get_data "${depth}" "${skip_if_up_to_date}" "${keep_going}" "${dep}"; then
                echo
                echo "WARNING: Couldn't get dependency ${dep}; pair ${pair} might not get set up correctly."
                echo
                if ${keep_going}; then
                    echo "WARNING: Continuing on as if nothing happened ..."
                    echo
                    sleep 1
                else
                    exit 1
                fi
            fi
        done
    fi
    cd "${pair}"
    autogen="./autogen.sh "
    for i in "${!depn[@]}"; do
        binsdir=$(bins_of_dep "${deps[i]}")
        autogen="${autogen} --with-lang${depn[i]}=../${binsdir}"
    done
    ${autogen}
    make -j3
    make test || echo "make test failed, but that's probably fine."

    cat <<EOF

All done!

You can now "cd ${pair}" or one of the dependencies, edit some files
and type "make -j3 langs" to compile again.

EOF
}

split_org_langs () {
    local -r org=$( if [[ $1 = giella-* ]]; then echo giella; else echo apertium; fi )
    local -r langs=${1#${org}-}
    echo "${org} ${langs}"
}

maybe_symlink_GTHOME () {
    if [[ -d $1 ]]; then
        echo
        echo "Found $1 here, using that."
        echo
    elif [[ -z ${GTHOME+x} ]]; then
        echo
        echo "GTHOME is unset; will have to build $1 without it."
        echo
    elif [[ -d $GTHOME/$1 ]]; then
        echo
        echo "Found $1 in your \$GTHOME, symlinking to that to avoid recompilation."
        echo
        test -d langs || mkdir langs
        ln -sf "$GTHOME/$1" "$1"
    else
        echo
        echo "GTHOME is set but there is no $GTHOME/$1; will have to build $1 from scratch."
        echo
    fi
}

get_data () {
    local -r depth=$1
    local -r keep_going=$2
    local -r skip_if_up_to_date=$3
    local -r orglangs=$(split_org_langs "$4")
    local -r org=${orglangs%% *}
    local -r langs=${orglangs##* }

    if [[ ${langs} = *-* ]]; then
        get_pair "$@"
    else
        local -r mdep=${org}-${langs}
        if [[ $org = giella ]]; then
            maybe_symlink_GTHOME "langs/${langs}"
            maybe_symlink_GTHOME gtcore
            get_dep "${depth}" gtcore
            make_dep gtcore
        fi

        if [[ ${skip_if_up_to_date} == true && $(is_dep_updated "${mdep}") == "yes" ]]; then
            printf "Dependency %s is up-to-date, skipping update and build.\\n" "$3"
        else
            if get_dep "${depth}" "${mdep}"; then
                make_dep "${mdep}"
            else
                return 1
            fi
        fi
    fi
}

show_help () {
    cat <<EOF
USAGE
       ${0##*/} PAIR
       ${0##*/} -l [MODULE...]

DESCRIPTION
       Run with just one argument, it will download and set up the
       Apertium development data for the specified language pair.

       With the -l option, it will list available language pairs. Give
       one or more MODULE arguments to list only pairs in that SVN
       module (one of "trunk", "staging", "nursery", "incubator").
       The same behavior can be invoked for language modules using -m.

OPTIONS
       -h          display this help and exit
       -l          list available packages instead of setting up data
       -m          list available language modules instead of setting up
                   data
       -k          keep going even if a dependency fails
       -s          skip the build step for up-to-date dependencies/pairs
       -x DEP      skip data dependency DEP (useful if DEP is installed
                   through a package manager); may be specified multiple
                   times
       -d DEPTH    specify a --depth to 'git clone'

EXAMPLES
       ${0##*/} nno-nob

       Download and set up apertium-nno-nob, along with its nno and
       nob dependencies.

       sudo apt-get install giella-sme
       ${0##*/} -x sme sme-nob

       Install giella-sme through apt-get, then install download and set
       up apertium-sme-nob, along with the nob dependency (but not sme).

       ${0##*/} -l trunk

       List available language pairs in SVN trunk.

       ${0##*/} -l | grep kaz

       List available language pairs involving Kazakh.
EOF
}

is_in () {
    local -r pattern="$1"
    local element
    shift

    for element; do
        [[ ${element} = "${pattern}" ]] && return 0
    done
    return 1
}


list_modules () {
    curl -Ss --fail "${gitroot}/apertium-${module}/master/.gitmodules" \
        | grep "[[:space:]]*url = .*.git$"                             \
        | sed 's%.*url = .*/%%'                                        \
        | sed 's/[.]git$//'                                            \
        | sed 's/^apertium-//'
    echo
}

list_pairs () {
    local -a modules=("$@")
    local module

    # Defaulting to all modules:
    if [[ ${#modules[@]} -eq 0 ]]; then
        modules=( "${pmodules[@]}" )
    fi
    # Sanity-check input:
    for module in "${modules[@]}"; do
        if ! is_in "${module}" "${pmodules[@]}"; then
            echo "ERROR: '${module}' not recognised as a language pair module"'!' >&2
            echo >&2
            show_help >&2
            exit 1
        fi
    done

    for module in "${modules[@]}"; do
        echo "# Pairs in ${module}:"
        list_modules "${module}" |grep -e '-'
        echo
    done
}

list_language_modules() {
    local -a modules=("$@")
    local module

    # Defaulting to all modules:
    if [[ ${#modules[@]} -eq 0 ]]; then
        modules=( "${lmodules[@]}" )
    fi
    # Sanity-check input:
    for module in "${modules[@]}"; do
        if ! is_in "${module}" "${lmodules[@]}"; then
            echo "ERROR: '${module}' not recognised as an language module module"'!' >&2
            echo >&2
            show_help >&2
            exit 1
        fi
    done

    for module in "${modules[@]}"; do
        echo "# Language modules in ${module}:"
        list_modules "${module}" | grep -ve '-'
    done
}

sanity_check () {
    if ! command -V git >/dev/null; then
        cat >&2 <<EOF

You need to install git first!

If you use apt-get, it's typically:

  sudo apt-get install git

If you use rpm/dnf, it's typically:

  sudo dnf install git

EOF
    fi
}

main () {
    sanity_check
    local do_list_pairs=false
    local keep_going=false
    local do_list_language_modules=false
    local skip_if_up_to_date=false
    local -a skip=()
    local depth=0
    while getopts ":hklmsx:d:" opt; do
        case "$opt" in
            h)
                show_help
                exit 0
                ;;
            x)
                skip+=( "${OPTARG}" )
                ;;
            d)
                depth="${OPTARG}"
                ;;
            l)
                do_list_pairs=true
                ;;
            m)
                do_list_language_modules=true
                ;;
            k)
                keep_going=true
                ;;
            s)
                skip_if_up_to_date=true
                ;;
            \?)
                echo "ERROR: Invalid option: -$OPTARG" >&2
                echo >&2
                show_help >&2
                exit 1
                ;;
        esac
    done
    shift "$((OPTIND-1))"

    if ${do_list_pairs}; then
        list_pairs "$@"
    elif ${do_list_language_modules}; then
        list_language_modules "$@"
    else
        if [[ $# -lt 1 ]]; then
            echo "ERROR: No language pair specified." >&2
            echo >&2
            show_help >&2
            exit 1
        fi
        for d in "$@"; do
            get_data "${depth}" "${keep_going}" "${skip_if_up_to_date}" "$d" "${skip[@]:-}"
        done
    fi
}

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    echo "${BASH_SOURCE[0]} is being sourced; chmod +x and use ./${BASH_SOURCE[0]} to actually run." >&2
else
    main "$@"
fi
