#!/usr/bin/env python3

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
from enum import Enum, auto

### Globals:

PMODULES = ["trunk", "staging", "nursery", "incubator"]
LMODULES = ["languages", "incubator"]

GIT_SSH = "git@github.com:"
GIT_HTTPS = "https://github.com/"

APERTIUM_GIT = "apertium/apertium-%s.git"
GIELLA_GIT = "giellalt/lang-%s.git"
GIELLA_CORE_GIT = "giellalt/giella-core.git"
GIELLA_SHARED_GIT = "giellalt/giella-shared.git"


class Status(Enum):
    NOT_STARTED = 0
    CLONED = 1
    PULLED = 2
    DONE = 3
    SKIPPED = 4
    FAILED = 5


dep_paths = {}
# e.g. 'apertium-eng' -> '~/apertium-eng'

dep_status = {}
# e.g. 'apertium-spa' -> Status.CLONED

dep_reqs = {}
# e.g. 'apertium-tur-uzb' -> [(1, 'apertium-tur'), (2, 'apertium-uzb')]

AP_CHECK_LING = re.compile(r"AP_CHECK_LING\(\[(\d)\],\s+\[([\w-]+)\]", re.MULTILINE)
# original pattern:
# (awk -F'[][[:space:]]+' '/^ *AP_CHECK_LING\(/ && $2 && $4 {print $2, $4}' "${pair}"/configure.ac)


def get_output(command, **kwargs):
    return check_output(command, stderr=STDOUT, universal_newlines=True, **kwargs)


def run_command(command, **kwargs):
    check_call(command, stdout=None, stderr=None, **kwargs)


def possible_paths(dep):
    if dep.startswith("lang-"):
        lang = dep.split("-")[1]
        return ["giella-" + lang, "lang-" + lang]
    if len(dep.split("-")) == 3:
        _, l1, l2 = dep.split("-")
        return ["apertium-%s-%s" % (l1, l2), "apertium-%s-%s" % (l2, l1)]
    return [dep]


def find_or_clone(dep, depth, use_ssh):
    for name in possible_paths(dep):
        pth = os.getcwd() + "/" + name
        if os.path.isdir(pth + "/.git"):
            dep_paths[dep] = pth
            dep_status[dep] = Status.CLONED
            return
    dirname = None
    alt_url = None
    code = dep.split("-", 1)[1]
    cmd = ["git", "clone"]
    if depth > 0:
        cmd += ["--depth", str(depth)]

    url = GIT_SSH if use_ssh else GIT_HTTPS
    if dep == "giella-core":
        url += GIELLA_CORE_GIT
    elif dep == "giella-shared":
        url += GIELLA_SHARED_GIT
    elif dep.startswith("lang-"):
        dirname = "giella-" + code
        url += GIELLA_GIT % code
    elif "-" in code:
        alt_code = "-".join(reversed(code.split("-")))
        alt_url = url + (APERTIUM_GIT % alt_code)
        url += APERTIUM_GIT % code
    else:
        url += APERTIUM_GIT % code
    cmd.append(url)

    if dirname:
        cmd.append(dirname)
    try:
        run_command(cmd)
        dep_paths[dep] = dirname or (
            os.getcwd() + "/" + url.split("/")[-1].split(".")[0]
        )
        dep_status[dep] = Status.PULLED
    except CalledProcessError:
        if alt_url:
            name = alt_url.split("/")[-1].split(".")[0]
            run_command(cmd[:-1] + [alt_url])
            print("\nWARNING: %s is actually named %s\n" % (dep, name))
            dep_paths[dep] = os.getcwd() + "/" + name
            dep_status[dep] = Status.PULLED
        else:
            raise


def get_deps(pair):
    global dep_status
    global dep_paths
    global dep_reqs
    with open(dep_paths[pair] + "/configure.ac") as conf:
        dep_list = AP_CHECK_LING.findall(conf.read())
        dep_reqs[pair] = []
        for n, dep in dep_list:
            if dep not in dep_status:
                dep_status[dep] = Status.NOT_STARTED
            elif dep_status[dep] == Status.SKIPPED:
                print("\nSkipping data %s as instructed.\n" % dep)
                continue
            dep_reqs[pair].append((dep, n))


def update(dep, skip_update):
    dirname = dep_paths[dep]
    if skip_update:
        if get_output(["git", "fetch", "--dry-run"], cwd=dirname) == "":
            dep_status[dep] = Status.DONE
            print("\n%s is up to date - skipping\n" % dep)
            return
    run_command(["git", "pull"], cwd=dirname)
    dep_status[dep] = Status.PULLED


def build(dep):
    dirname = dep_paths[dep]
    env = None
    if dep.startswith("lang-"):
        env = os.environ.copy()
        if "GIELLA_CORE" not in env:
            env["GIELLA_CORE"] = dep_paths.get("giella-core", "")
        if "GIELLA_SHARED" not in env:
            env["GIELLA_SHARED"] = dep_paths.get("giella-shared", "")

    run_command(["autoreconf", "-fvi"], cwd=dirname, env=env)

    cmd = ["./configure"]
    if dep.startswith("lang-"):
        cmd += ["--enable-apertium", "--with-hfst", "--enable-syntax"]
    for name, idx in dep_reqs[dep]:
        pth = dep_paths[name]
        if name.startswith("lang-"):
            pth += "/tools/mt/apertium"
        cmd.append("--with-lang%s=%s" % (idx, pth))
    run_command(cmd, cwd=dirname, env=env)

    run_command(["make", "-j3"], cwd=dirname, env=env)

    dep_status[dep] = Status.DONE


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
    return [dep for dep in dep_status if dep_status[dep] == status]


def error_on_dep(dep, keep_going):
    global dep_status
    if keep_going:
        dep_status[dep] = Status.FAILED
        print("\nContinuing...\n")
        if dep.startswith("giella-"):
            print("WARNING: Giella language modules may fail to build correctly\n")
        elif len(dep.split("-")) == 2:
            print(
                "WARNING: pairs dependent on this module may fail to build correctly\n"
            )
    else:
        sys.exit(1)


def try_to_clone(dep, depth, keep_going, use_ssh):
    try:
        find_or_clone(dep, depth, use_ssh)
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
        choices=PMODULES,
        help="list available pairs in MODULES instead of setting up data. If no modules are specified, all pairs will be listed.",
        metavar="MODULES",
    )
    parser.add_argument(
        "-m",
        "--modules",
        nargs="*",
        choices=LMODULES,
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
    parser.add_argument(
        "-S",
        "--ssh",
        action="store_true",
        help="use ssh urls in git clone rather than https",
    )
    parser.add_argument("pairs", nargs="*", help="pairs or modules to install")
    args = parser.parse_args()

    if args.list != None:
        for module in args.list or PMODULES:
            list_pairs(module, True)
    elif args.modules != None:
        for module in args.modules or LMODULES:
            list_pairs(module, False)
    else:
        if len(args.pairs) == 0:
            parser.error("No language pair specified.\n")
        for arg in args.pairs:
            dep_status[normalize_name(arg)] = Status.NOT_STARTED
        for skip in args.skip or []:
            dep_status[normalize_name(skip)] = Status.SKIPPED

        # download requested repos
        for dep in get_all_status(Status.NOT_STARTED):
            try_to_clone(dep, args.depth, args.keep_going, args.ssh)

        # download dependencies
        for dep in get_all_status(Status.NOT_STARTED):
            try_to_clone(dep, args.depth, args.keep_going, args.ssh)

        # download giella-core and giella-shared if we need them
        for dep in dep_status:
            if dep.startswith("lang-"):
                if "GIELLA_CORE" not in os.environ:
                    try_to_clone("giella-core", args.depth, args.keep_going, args.ssh)
                if "GIELLA_SHARED" not in os.environ:
                    try_to_clone("giella-shared", args.depth, args.keep_going, args.ssh)
                break

        # update repos that were already downloaded
        for dep in get_all_status(Status.CLONED):
            try:
                update(dep, args.skip_update)
            except CalledProcessError:
                print("\nUnable to update directory of %s.\n" % dep)
                error_on_dep(dep, args.keep_going)

        # build everything
        if dep_status.get("giella-core") == Status.PULLED:
            try_to_build("giella-core", args.keep_going)
        if dep_status.get("giella-shared") == Status.PULLED:
            try_to_build("giella-shared", args.keep_going)
        for dep in get_all_status(Status.PULLED):
            if len(dep.split("-")) == 2:
                try_to_build(dep, args.keep_going)
        for dep in get_all_status(Status.PULLED):
            try_to_build(dep, args.keep_going)


if __name__ == "__main__":
    main()
