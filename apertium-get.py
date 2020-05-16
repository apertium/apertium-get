#!/usr/bin/python3

import argparse
import os
import re
import sys
import urllib.request
from subprocess import (
    run,
    check_call,
    check_output,
    STDOUT,
    DEVNULL,
    CalledProcessError,
)

### Globals:

pmodules = ["trunk", "staging", "nursery", "incubator"]
lmodules = ["languages", "incubator"]

git_ssh = "git@github.com:"
git_https = "https://github.com/"

apertium_git = "apertium/apertium-%s.git"
giella_git = "giellalt/lang-%s.git"
giella_core_git = "giellalt/giella-core.git"
giella_shared_git = "giellalt/giella-shared.git"

NOT_STARTED = 0
CLONED = 1
PULLED = 2
DONE = 3
SKIPPED = 4
FAILED = 5

DEP_PATHS = {}
# e.g. 'apertium-eng' -> '~/apertium-eng'

DEP_STATUS = {}
# e.g. 'apertium-spa' -> CLONED

DEP_REQS = {}
# e.g. 'apertium-tur-uzb' -> [(1, 'apertium-tur'), (2, 'apertium-uzb')]

ap_check_ling = re.compile(r"AP_CHECK_LING\(\[(\d)\],\s+\[([\w-]+)\]", re.MULTILINE)
# original pattern:
# (awk -F'[][[:space:]]+' '/^ *AP_CHECK_LING\(/ && $2 && $4 {print $2, $4}' "${pair}"/configure.ac)


def get_output(command, dirname=None):
    return check_output(command, cwd=dirname, stderr=STDOUT, universal_newlines=True)


def run_command(command, dirname=None, env=None):
    check_call(command, cwd=dirname, stdout=None, stderr=None, env=env)


def possible_paths(dep):
    if dep.startswith("lang-"):
        lang = dep.split("-")[1]
        return ["giella-" + lang, "lang-" + lang]
    if len(dep.split("-")) == 3:
        ap, l1, l2 = dep.split("-")
        return ["apertium-%s-%s" % (l1, l2), "apertium-%s-%s" % (l2, l1)]
    return [dep]


def find_or_clone(dep, depth, use_https=False):
    for name in possible_paths(dep):
        pth = os.getcwd() + "/" + name
        if os.path.isdir(pth + "/.git"):
            DEP_PATHS[dep] = pth
            DEP_STATUS[dep] = CLONED
            return
    dirname = None
    alt_url = None
    code = dep.split("-", 1)[1]
    cmd = ["git", "clone"]
    if depth > 0:
        cmd += ["--depth", str(depth)]

    url = git_https if use_https else git_ssh
    if dep == "giella-core":
        url += giella_core_git
    elif dep == "giella-shared":
        url += giella_shared_git
    elif dep.startswith("lang-"):
        dirname = "giella-" + code
        url += giella_git % code
    elif "-" in code:
        alt_code = "-".join(reversed(code.split("-")))
        alt_url = url + (apertium_git % alt_code)
        url += apertium_git % code
    else:
        url += apertium_git % code
    cmd.append(url)

    if dirname:
        cmd.append(dirname)
    try:
        run_command(cmd)
        DEP_PATHS[dep] = dirname or (
            os.getcwd() + "/" + url.split("/")[-1].split(".")[0]
        )
        DEP_STATUS[dep] = PULLED
    except CalledProcessError:
        if alt_url:
            name = alt_url.split("/")[-1].split(".")[0]
            run_command(cmd[:-1] + [alt_url])
            print("\nWARNING: %s is actually named %s\n" % (dep, name))
            DEP_PATHS[dep] = os.getcwd() + "/" + name
            DEP_STATUS[dep] = PULLED
        else:
            raise


def get_deps(pair):
    global DEP_STATUS
    global DEP_PATHS
    global DEP_REQS
    conf = open(DEP_PATHS[pair] + "/configure.ac")
    dep_list = ap_check_ling.findall(conf.read())
    conf.close()
    DEP_REQS[pair] = []
    for n, dep in dep_list:
        if dep not in DEP_STATUS:
            DEP_STATUS[dep] = NOT_STARTED
        elif DEP_STATUS[dep] == SKIPPED:
            print("\nSkipping data %s as instructed.\n" % dep)
            continue
        DEP_REQS[pair].append((dep, n))


def update(dep, skip_update):
    dirname = DEP_PATHS[dep]
    if skip_update:
        if get_output(["git", "fetch", "--dry-run"], dirname) == "":
            DEP_STATUS[dep] = DONE
            return
    run_command(["git", "pull"], dirname)
    DEP_STATUS[dep] = PULLED


def build(dep):
    dirname = DEP_PATHS[dep]
    env = None
    if dep.startswith("lang-"):
        env = os.environ.copy()
        if "GIELLA_CORE" not in env:
            env["GIELLA_CORE"] = DEP_PATHS.get("giella-core", "")
        if "GIELLA_SHARED" not in env:
            env["GIELLA_SHARED"] = DEP_PATHS.get("giella-shared", "")

    run_command(["autoreconf", "-fvi"], dirname=dirname, env=env)

    cmd = ["./configure"]
    if dep.startswith("lang-"):
        cmd += ["--enable-apertium", "--with-hfst", "--enable-syntax"]
    for name, idx in DEP_REQS[dep]:
        pth = DEP_PATHS[name]
        if name.startswith("lang-"):
            pth += "/tools/mt/apertium"
        cmd.append("--with-lang%s=%s" % (idx, pth))
    run_command(cmd, dirname=dirname, env=env)

    run_command(["make", "-j3"], dirname=dirname, env=env)

    DEP_STATUS[dep] = DONE


def list_pairs(module, getting_pairs):
    print("# %s in %s:" % (("Pairs" if getting_pairs else "Language modules"), module))
    submodule_url = (
        "https://raw.githubusercontent.com/apertium/apertium-%s/master/.gitmodules"
    )
    req = urllib.request.urlopen(submodule_url % module)
    for ln in req.read().decode("utf-8").splitlines():
        if ln.startswith("\turl = "):
            url = ln.split()[-1]
            code = url.split("apertium-")[-1][:-4]
            # e.g. 'git@github.com:apertium/apertium-fin.git' -> 'fin'
            if ("-" in code) == getting_pairs:
                print(code)


def normalize_name(name):
    if (
        name.startswith("apertium-")
        or name.startswith("lang-")
        or name in ["giella-core", "giella-shared"]
    ):
        return name
    elif name.startswith("giella-"):
        return "lang-" + name.split("-")[1]
    else:
        return "apertium-" + name


def get_all_status(status):
    return [dep for dep in DEP_STATUS if DEP_STATUS[dep] == status]


def error_on_dep(dep, keep_going):
    global DEP_STATUS
    if keep_going:
        DEP_STATUS[dep] = FAILED
        print("\nContinuing...\n")
        if dep.startswith("giella-"):
            print("WARNING: Giella language modules may fail to build correctly\n")
        elif len(dep.split("-")) == 2:
            print(
                "WARNING: pairs dependent on this module may fail to build correctly\n"
            )
    else:
        sys.exit(1)


def try_to_clone(dep, depth, keep_going):
    try:
        find_or_clone(dep, depth)
        get_deps(dep)
    except CalledProcessError:
        print("\nUnable to clone %s.\n" % dep)
        error_on_dep(dep, keep_going)


def try_to_build(dep, keep_going):
    try:
        build(dep)
    except CalledProcessError:
        print("\nUnable to build %s.\n" % dep)
        error_on_dep(dep, keep_going)


def check_for_git():
    try:
        run(["git", "--version"], stdout=DEVNULL, stderr=DEVNULL)
    except CalledProcessError:
        print(
            """

You need to install git first!

If you use apt-get, it's typically:

  sudo apt-get install git

If you use rpm/dnf, it's typically:

  sudo dnf install git

"""
        )
        sys.exit(1)


def main():
    check_for_git()
    parser = argparse.ArgumentParser(
        description="Download and build Apertium pairs and language data.",
        epilog="""EXAMPLES
       apertium-get nno-nob

       Download and set up apertium-nno-nob, along with its nno and
       nob dependencies.

       sudo apt-get install giella-sme
       apertium-get -x sme sme-nob

       Install giella-sme through apt-get, then install download and set
       up apertium-sme-nob, along with the nob dependency (but not sme).

       apertium-get -l trunk

       List available language pairs in SVN trunk.

       apertium-get -l | grep kaz

       List available language pairs involving Kazakh.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-l",
        "--list",
        nargs="*",
        choices=pmodules,
        help="list available pairs in MODULES instead of setting up data. If no modules are specified, all pairs will be listed.",
        metavar="MODULES",
    )
    parser.add_argument(
        "-m",
        "--modules",
        nargs="*",
        choices=lmodules,
        help="list available pairs in MODULES instead of setting up data. If no modules are specified, all pairs will be listed.",
        metavar="MODULES",
    )
    parser.add_argument(
        "-k",
        "--keep-going",
        action="store_true",
        help="keep going even if a dependency fails.",
    )
    parser.add_argument(
        "-s",
        "--skip-update",
        action="store_true",
        help="don't rebuild up-to-date dependencies/pairs",
    )
    parser.add_argument(
        "-x",
        "--skip",
        action="append",
        help="skip data dependency DEP (useful if DEP is installed through a package manager); may be specified multiple times",
    )
    parser.add_argument(
        "-d", "--depth", type=int, default=0, help="specify a --depth to 'git clone'",
    )
    parser.add_argument("pairs", nargs="*", help="pairs or modules to install")
    args = parser.parse_args()

    if args.list != None:
        for module in args.list or pmodules:
            list_pairs(module, True)
    elif args.modules != None:
        for module in args.modules or lmodules:
            list_pairs(module, False)
    else:
        if len(args.pairs) == 0:
            parser.error("No language pair specified.\n")
        for arg in args.pairs:
            DEP_STATUS[normalize_name(arg)] = NOT_STARTED
        for skip in args.skip or []:
            DEP_STATUS[normalize_name(skip)] = SKIPPED

        # download requested repos
        for dep in get_all_status(NOT_STARTED):
            try_to_clone(dep, args.depth, args.keep_going)

        # download dependencies
        for dep in get_all_status(NOT_STARTED):
            try_to_clone(dep, args.depth, args.keep_going)

        # download giella-core and giella-shared if we need them
        for dep in DEP_STATUS:
            if dep.startswith("lang-"):
                if "GIELLA_CORE" not in os.environ:
                    try_to_clone("giella-core", args.depth, args.keep_going)
                if "GIELLA_SHARED" not in os.environ:
                    try_to_clone("giella-shared", args.depth, args.keep_going)
                break

        # update repos that were already downloaded
        for dep in get_all_status(CLONED):
            try:
                update(dep, args.skip_update)
            except CalledProcessError:
                print("\nUnable to update directory of %s.\n" % dep)
                error_on_dep(dep, args.keep_going)

        # build everything
        if DEP_STATUS.get("giella-core") == PULLED:
            try_to_build("giella-core", args.keep_going)
        if DEP_STATUS.get("giella-shared") == PULLED:
            try_to_build("giella-shared", args.keep_going)
        for dep in get_all_status(PULLED):
            if len(dep.split("-")) == 2:
                try_to_build(dep, args.keep_going)
        for dep in get_all_status(PULLED):
            try_to_build(dep, args.keep_going)


if __name__ == "__main__":
    main()
