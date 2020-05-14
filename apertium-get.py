#!/usr/bin/python3

import requests, argparse, subprocess, os, re, sys

### Globals:

gitroot  = 'https://raw.githubusercontent.com/apertium'
pmodules = ['trunk', 'staging', 'nursery', 'incubator']
lmodules = ['languages', 'incubator']

svnroot_giella = 'https://victorio.uit.no/langtech/trunk'

pair_urls = {}
lang_urls = {}
giella_urls = {}
module_contents = {}

ap_check_ling = re.compile(r'AP_CHECK_LING\(\[(\d)\],\s+\[([\w-]+)\]\)', re.MULTILINE)
# original pattern:
# (awk -F'[][[:space:]]+' '/^ *AP_CHECK_LING\(/ && $2 && $4 {print $2, $4}' "${pair}"/configure.ac)

def get_output(command, dirname=None):
    return subprocess.check_output(command, cwd=dirname, stderr=subprocess.STDOUT,
                                   universal_newlines=True)
def run_command(command, dirname=None, env=None):
    subprocess.check_call(command, cwd=dirname, stdout=None, stderr=None, env=env)

def get_urls():
    global pair_urls
    global lang_urls
    global giella_urls
    global module_contents

    for module in list(set(pmodules + lmodules)):
        module_contents[module] = []
        req = requests.get('%s/apertium-%s/master/.gitmodules' % (gitroot, module))
        if req.status_code != 200:
            #error?
            continue
        for ln in req.text.splitlines():
            if ln.startswith('\turl = '):
                url = ln.split()[-1]
                code = url.split('apertium-')[-1][:-4]
                # e.g. 'git@github.com:apertium/apertium-fin.git' -> 'fin'
                if '-' in code:
                    pair_urls[code] = url
                else:
                    lang_urls[code] = url
                module_contents[module].append(code)
    req = requests.get(svnroot_giella + '/langs/')
    if req.status_code != 200:
        #error?
        return
    for ln in req.text.splitlines():
        if '<li><a' in ln and '..' not in ln:
            code = ln.split('"')[1][:-1]
            # e.g. '<li><a href="vot/">vot/</a></li>' -> 'vot'
            url = svnroot_giella + '/langs/' + code
            giella_urls[code] = url

def dir_of_dep(dep):
    if dep.startswith('giella-'):
        return 'langs/' + dep[7:]
    else:
        return dep

def bins_of_dep(dep):
    if dep.startswith('giella-'):
        return 'langs/%s/tools/mt/apertium' % dep[7:]
    else:
        return dep

def make_dep(dep):
    dirname = dir_of_dep(dep)
    env = os.environ.copy()
    env['GTHOME'] = os.getcwd()
    env['GTCORE'] = os.getcwd() + '/gtcore'
    # Let cwd be GTHOME from here on in; langs should exist under this dir:
    print(dirname)
    run_command(['./autogen.sh'], dirname, env)
    if dep.startswith('giella-'):
        run_command(['./configure', '--enable-apertium', '--with-hfst', '--enable-syntax'], dirname, env)
        env['V'] = '1'
        run_command(['make'], dirname, env)
    elif dep == 'gtcore':
        run_command(['./configure'], dirname, env)
        run_command(['make', '-j3'], dirname, env)
    else:
        run_command(['make', '-j3'], dirname, env)

def is_dep_updated(dep):
    dirname = dir_of_dep(dep)
    if os.path.isdir(dirname):
        if os.path.isdir(dirname + '/.git'):
            return get_output(['git', 'fetch', '--dry-run'], dirname) == ''
        return get_output(['svn', 'status', '-qu', dirname]) == ''
    return False

def get_dep(depth, dep):
    dirname = dir_of_dep(dep)
    if os.path.isdir(dirname):
        print('Updating existing %s (%s)' % (dirname, os.getcwd()))
        cmd = ['svn', 'up']
        if os.path.isdir(dirname + '/.git'):
            cmd = ['git', 'pull']
        run_command(cmd, dirname)
    else:
        if dep == 'gtcore':
            run_command(['svn', 'checkout', svnroot_giella + '/gtcore', dirname])
        if dep.startswith('giella-'):
            url = giella_urls[dep.split('-', 1)[1]]
            run_command(['svn', 'checkout', url, dirname])
        else:
            name = dirname.split('-', 1)[1]
            url = pair_urls[name] if '-' in name else lang_urls[name]
            cmd = ['git', 'clone']
            if depth > 0:
                cmd += ['--depth', str(depth)]
            run_command(cmd + [url, dirname])

def get_pair(depth, keep_going, skip_if_up_to_date, pair, skip):
    if skip_if_up_to_date and is_dep_updated(pair):
        print('Existing pair %s is already up to date. Skipping build step.' % pair)
        return

    get_dep(depth, pair)
    deps = []
    conf = open(pair + '/configure.ac')
    dep_list = ap_check_ling.findall(conf.read())
    conf.close()
    for n, dep in dep_list:
        org, lang = dep.split('-', 1)
        if lang in skip:
            print('\nSkipping data %s as instructed.\n' % lang)
        else:
            deps.append((dep, n))

    cmd = ['./autogen.sh']
    for dep, n in deps:
        try:
            get_data(depth, skip_if_up_to_date, keep_going, dep, skip)
        except subprocess.CalledProcessError:
            print("\nWARNING: Couldn't get dependency %s; pair %s might not get set up correctly.\n" % (dep, pair))
            if keep_going:
                print('WARNING: Continuing on as if nothing happened ...\n')
            else:
                sys.exit(1)
        binsdir = bins_of_dep(dep)
        cmd.append('--with-lang%s=../%s' % (n, binsdir))

    run_command(cmd, dirname=pair)
    run_command(['make', '-j3'], dirname=pair)
    try:
        subprocess.check_call(['make', 'test'], cwd=pair, stdout=None, stderr=None)
    except subprocess.CalledProcessError:
        print("make test failed, but that's probably fine.")

    print('''

All done!

You can now "cd ${pair}" or one of the dependencies, edit some files
and type "make -j3 langs" to compile again.

''')

def maybe_symlink_GTHOME(dirname):
    if os.path.isdir(dirname):
        print('\nFound %s here, using that.\n' % dirname)
    elif 'GTHOME' not in os.environ:
        print('\nGTHOME unset; will have to build %s without it.\n' % dirname)
    elif os.path.isdir(os.environ['GTHOME'] + '/' + dirname):
        print('Found %s in your $GTHOME, symlinking to that to avoid recompilation.\n' % dirname)
        if not os.path.isdir('langs'):
            os.mkdir('langs')
        os.symlink(os.environ['GTHOME'] + '/' + dirname, dirname, target_is_directory=True)
    else:
        print('\nGTHOME is set but there is no %s/%s; will have to build %s from scratch.\n' % (os.environ['GTHOME'], dirname, dirname))

def get_data(depth, keep_going, skip_if_up_to_date, dep, skip):
    org, lang = dep.split('-', 1)

    if '-' in lang:
        get_pair(depth, keep_going, skip_if_up_to_date, dep, skip)
    else:
        if org == 'giella':
            maybe_symlink_GTHOME('langs/' + lang)
            maybe_symlink_GTHOME('gtcore')
            get_dep(depth, 'gtcore')
            make_dep('gtcore')
        if skip_if_up_to_date and is_dep_updated(dep):
            print('Dependency %s is up-to-date, skipping update and build.\\n' % dep)
        else:
            try:
                get_dep(depth, dep)
                make_dep(dep)
            except subprocess.CalledProcessError:
                print('\nUnable to build %s\n' % dep)
                if not keep_going:
                    sys.exit(1)

def list_pairs(modules):
    for module in (modules or pmodules):
        print('# Pairs in %s:' % module)
        print('\n'.join(pr for pr in sorted(module_contents[module]) if '-' in pr))

def list_language_modules(modules):
    for module in (modules or lmodules):
        print('# Language modules in %s:' % module)
        print('\n'.join(lg for lg in sorted(module_contents[module]) if '-' not in lg))

def check_for_git():
    try:
        subprocess.run(['git', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        print('''

You need to install git first!

If you use apt-get, it's typically:

  sudo apt-get install git

If you use rpm/dnf, it's typically:

  sudo dnf install git

''')
        sys.exit(1)

def get_dep_name(name):
    if name.startswith('giella-'):
        lang = name.split('-', 1)[1]
        if lang in giella_urls:
            return name
        else:
            return None
    elif name.startswith('apertium-'):
        return get_dep_name(name.split('-', 1)[1])
    elif '-' in name:
        if name in pair_urls:
            return 'apertium-' + name
        alt = '-'.join(reversed(name.split('-')))
        if alt in pair_urls:
            print('\nWARNING: apertium-%s does not exist, using apertium-%s instead\n' % (name, alt))
            return 'apertium-' + alt
        else:
            return None
    else:
        if name in lang_urls:
            return 'apertium-' + name
        else:
            return None

def main():
    check_for_git()
    parser = argparse.ArgumentParser(description='Download and build Apertium pairs and language data.',
        epilog='''EXAMPLES
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

       List available language pairs involving Kazakh.''', formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-l', '--list', nargs='*', choices=pmodules, help='list available pairs in MODULES instead of setting up data. If no modules are specified, all pairs will be listed.', metavar='MODULES')
    parser.add_argument('-m', '--modules', nargs='*', choices=lmodules, help='list available pairs in MODULES instead of setting up data. If no modules are specified, all pairs will be listed.', metavar='MODULES')
    parser.add_argument('-k', '--keep-going', action='store_true', help='keep going even if a dependency fails.')
    parser.add_argument('-s', '--skip-update', action='store_true', help="don't rebuild up-to-date dependencies/pairs")
    parser.add_argument('-x', '--skip', action='append', nargs=1, help='skip data dependency DEP (useful if DEP is installed through a package manager); may be specified multiple times')
    parser.add_argument('-d', '--depth', nargs=1, type=int, default=0, help="specify a --depth to 'git clone'")
    parser.add_argument('pairs', nargs='*', help='pairs or modules to install')
    args = parser.parse_args()

    get_urls()

    if args.list != None:
        list_pairs(args.list)
    elif args.modules != None:
        list_language_modules(args.modules)
    else:
        if len(args.pairs) == 0:
            print('ERROR: No language pair specified.\n')
            parser.print_help()
            parser.exit(1)
        for arg in args.pairs:
            dep = get_dep_name(arg)
            if dep and '-' not in arg and get_dep_name('giella-' + arg):
                print('\nWARNING: Both apertium-%s and giella-%s are available, defaulting to apertium-%s\n' % (arg, arg, arg))
            if not dep and '-' not in arg:
                dep = get_dep_name('giella-' + arg)
            if not dep:
                loc = 'SVN' if arg.startswith('giella-') else 'git'
                print("\nWARNING: Couldn't find %s url for %s\n" % (loc, arg))
                if args.keep_going:
                    continue
                else:
                    parser.exit(1)
            get_data(args.depth, args.keep_going, args.skip_update, dep, args.skip or [])

if __name__ == '__main__':
    main()
