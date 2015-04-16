#!/usr/bin/env python
from ConfigParser import SafeConfigParser
import subprocess
from subprocess import Popen, PIPE, CalledProcessError,check_call
from datetime import datetime
from multiprocessing import Pool

import tempfile
import argparse
import pkgutil
import json
import os
import sys
import re
import StringIO
import itertools
import pprint
import uuid
import time
import base64
import zlib

class _C:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

def expand_path(parser, path):
    """
    Expand then given path.

    Such as expanding the tilde in "~/bohrium", thereby providing
    the absolute path to the directory "bohrium" in the home folder.
    """

    path = os.path.expanduser(path)
    if os.path.isdir(path):
        return os.path.abspath(path)
    else:
        parser.error("The path %s does not exist!" % path)


def meta(src_dir, suite):
    """
    Extract various meta-information from the system,
    such as compiler-version, repos-version, hardware info etc.
    """

    try:
        p = Popen(              # Try grabbing the repos-revision
            ["git", "log", "--pretty=format:%H", "-n", "1"],
            stderr  = PIPE,
            stdout  = PIPE,
            cwd     = src_dir
        )
        rev, err = p.communicate()
    except OSError:
        rev = "Unknown"

    try:
        p = Popen(              # Try grabbing hw-info
            ["lshw", "-quiet", "-numeric"],
            stderr  = PIPE,
            stdout  = PIPE,
        )
        hw, err = p.communicate()
    except OSError:
        hw = "Unknown"

    try:
        p = Popen(              # Try grabbing hw-info
            ["hostname"],
            stderr  = PIPE,
            stdout  = PIPE,
        )
        hostname, err = p.communicate()
    except OSError:
        hostname = "Unknown"

    try:
        p = Popen(              # Try grabbing python version
            ["python", "-V"],
            stderr  = PIPE,
            stdout  = PIPE,
        )
        python_ver, err = p.communicate()
        python_ver  += err
    except OSError:
        python_ver = "Unknown"

    try:
        p = Popen(              # Try grabbing gcc version
            ["gcc", "-v"],
            stderr  = PIPE,
            stdout  = PIPE,
        )
        gcc_ver, err = p.communicate()
        gcc_ver += err
    except OSError:
        gcc_ver = "Unknown"

    try:
        p = Popen(              # Try grabbing clang version
            ["clang", "-v"],
            stderr  = PIPE,
            stdout  = PIPE,
        )
        clang_ver, err = p.communicate()
        clang_ver += err
    except OSError:
        clang_ver = "Unknown"

    info = {
        'suite':    suite,
        'rev':      rev if rev else 'Unknown',
        'hostname': hostname if hostname else 'Unknown',
        'started':  str(datetime.now()),
        'ended':    None,
        'hw':       {
            'cpu':  open('/proc/cpuinfo','r').read() if os.path.isfile('/proc/cpuinfo') else "Unknown",
            'list': hw if hw else 'Unknown',
        },
        'sw':   {
            'os':       open('/proc/version','r').read() if os.path.isfile('/proc/cpuinfo') else 'Probably MacOSX',
            'python':   python_ver if python_ver else 'Unknown',
            'gcc':      gcc_ver if gcc_ver else 'Unknown',
            'clang':    clang_ver if clang_ver else 'Unknown',
            'env':      os.environ.copy(),
        },
    }

    return info

def perf_counters():
    """Grabs all events pre-defined by 'perf'."""

    p = Popen(              # Try grabbing the repos-revision
        ["perf", "list"],
        stderr  = PIPE,
        stdout  = PIPE
    )
    out, err = p.communicate()

    events = []
    #for m in re.finditer('  ([\w-]+) [\w -]+\[.+\]', out):
    for m in re.finditer('  ([\w-]+) [\w -]+\[(?:Hardware|Software).+\]', out):
        events.append( m.group(1) )

    return ','.join(events)

def get_perf(filename):
    """Return the perf command"""

    out, err = Popen(
        ['which', 'perf'],
        stdout=PIPE,
        stderr=PIPE
    ).communicate()

    # Some distros have a wrapper script :(
    if not err and out:
        perf_cmd = out.strip()
        out, err = Popen(
            ['perf', 'list'],
            stderr=PIPE,
            stdout=PIPE,
        ).communicate()

    if err or not out:
        print _C.WARNING,"ERR: perf installation broken, disabling perf (%s): %s"%(err,out),_C.ENDC
        perf_cmd = ""
    else:
        perf_cmd += ' stat -x , -e %s -o %s '%(perf_counters(), filename)
    return perf_cmd


def get_time(filename):
    """Return the time command"""

    out, err = Popen(
        ['which', 'time'],
        stdout=PIPE,
        stderr=PIPE
    ).communicate()
    if err or not out:
        print _C.WARNING,"ERR: time installation broken, disabling time (%s): %s"%(err,out),_C.ENDC
        time_cmd = ""
    else:
        time_cmd = " %s -v -o %s "%(out.strip(),filename)
    return time_cmd

def encode_data(data):
    """return the encoded data as a string"""
    return base64.b64encode(zlib.compress(data, 9))

def decode_data(data):
    """return the decoded data as a string"""
    return zlib.decompress(base64.b64decode(data))

def write2json(json_file, obj):
    json_file.truncate(0)
    json_file.seek(0)
    json_file.write(json.dumps(obj, indent=4))
    json_file.flush()
    os.fsync(json_file)

def parse_elapsed_times(output):
    """Return list of elapsed times from the output"""

    times = []
    for t in re.finditer("elapsed-time:\s*(\d*\.?\d*)", output):
        times.append(float(t.group(1)))

    if len(times) == 0:
        times = [None]
    return times

def parse_and_add_timings(output,timings):
    """Return list of all timings from the output"""

    for t in re.finditer("\[Timing\]\s*(.*):\s(\d*\.?\d*)", output):
        k = t.group(1)
        t = float(t.group(2))
        if k in timings:
            timings[k].append(t)
        else:
            timings[k] = [t]

def execute_run(job):
    """Execute the run locally"""

    with open(job['filename'], 'w') as f:
        #First we have to write the batch script to a file
        f.write(job['script'])
        f.flush()
        os.fsync(f)
        try:# Then we execute the batch script
            p = Popen(['bash', f.name])
            p.wait()
        except KeyboardInterrupt:
            p.kill()
            raise

def slurm_run(job, nnodes=1, queue=None):
    """Submit the run to SLURM using 'nnodes' number of nodes"""
    with open(job['filename'], 'w') as f:
        f.write(job['script'])
        f.flush()
        os.fsync(f)
        print "Submitting %s on %d nodes"%(f.name, nnodes),
        cmd = ['sbatch']
        if queue:
            cmd += ['-p', queue]
        cmd += ['-N', '%d'%nnodes, f.name]
        try:
            p = Popen(cmd, stderr=PIPE, stdout=PIPE)
            out, err = p.communicate()
            job_id = int(out.split(' ')[-1] .rstrip())
            print "with SLURM ID %d"%job_id
        except:
            print _C.FAIL,"ERR: submitting SLURM job!",_C.ENDC
            job['status'] = 'failed'
            raise
        job['slurm_id'] = job_id

def slurm_run_finished(job):
    print "Checking job %d"%job['slurm_id']
    out = subprocess.check_output(['squeue'])
    if out.find(" %d "%job['slurm_id']) != -1:
        return False
    else:
        return True

def parse_run(run, job):
    """Parsing the pending run. NB: the run must be finished!"""
    for i in xrange(job['nrun']):
        base = "%s-%d"%(job['filename'], i)
        stdout = "%s.out"%base
        stderr = "%s.err"%base
        try:
            with open(stdout, 'r') as out:
                with open(stderr, 'r') as err:
                    out = out.read()
                    err = err.read()
                    run['stdout'].append(out)
                    run['stderr'].append(err)

                    #Lets parse and remove the data output file
                    if run['save_data_output']:
                        import numpy as np
                        outname = "%s.npz"%base
                        try:
                            with np.load(outname) as data:
                                try:
                                    res = data['res']
                                    run['data_output'].append(encode_data(data['res'].dumps()))
                                except KeyError:
                                    print _C.WARNING,"No 'res' array in data output of %s"\
                                                     %run['script_alias'],_C.ENDC
                            os.remove(outname)
                        except IOError:
                            print _C.WARNING,"Could not find the data output file '%s'"%outname,_C.ENDC

                    elapsed = parse_elapsed_times(out)[0]
                    print elapsed
                    run['elapsed'].append(elapsed)
                    if elapsed is None:
                        print _C.WARNING,"Could not find elapsed-time!", _C.ENDC
                        print _C.WARNING,"STDOUT: ",_C.ENDC
                        print _C.OKGREEN,"\t",out.replace('\n', '\n\t'),_C.ENDC
                        job['status'] = "failed"
                    else:
                        #We got the result, now the job is finished
                        job['status'] = "finished"
                    parse_and_add_timings(out,run['timings'])
                    if len(err) > 0:
                        print _C.WARNING,"STDERR: ",_C.ENDC
                        print _C.FAIL,"\t",err.replace('\n', '\n\t'),_C.ENDC
            os.remove(stdout)
            os.remove(stderr)
        except IOError:
            print _C.WARNING,"Could not find the stdout and/or the stderr file",_C.ENDC
        try:
            with open("%s.perf"%base, 'r') as perf:
                run['perf'].append(perf.read())
            os.remove("%s.perf"%base)
        except IOError:
            if run['use_perf']:
                print _C.WARNING,"Could not find the perf output file",_C.ENDC
        try:
            with open("%s.time"%base, 'r') as time:
                run['time'].append(time.read())
            os.remove("%s.time"%base)
        except IOError:
            if run['use_time']:
                print _C.WARNING,"Could not find the time output file",_C.ENDC
    try:
        os.remove(job['filename'])
    except OSError:
        print _C.WARNING,"Could not find the batch script: ",job['filename'],_C.ENDC

def add_pending_job(setup, nrun, partition):

    cwd = os.path.abspath(os.getcwd())
    basename = "bh-job-%s.sh"%uuid.uuid4()
    filename = os.path.join(cwd, basename)

    bridge_cmd = setup['bridge_cmd'].replace("{script}",  setup['script'])
    bridge_cmd = bridge_cmd.replace("{args}",  setup['script_args'])
    if setup['manager_cmd'] is not None and len(setup['manager_cmd']) > 0:
        bridge_cmd = setup['manager_cmd'].replace("{bridge}", bridge_cmd)

    job = "#!/bin/bash\n"
    for i in xrange(nrun):
        tmp_config_name = "/tmp/%s_%d.config.ini"%(basename, i)
        for env_key, env_value in setup['envs'].iteritems():      #Write environment variables
            job += 'export %s="${%s:-%s}"\n'%(env_key,env_key,env_value)

        for env_key, env_value in setup['envs_overwrite'].iteritems(): #Write forced environment variables
            job += 'export %s="%s"\n'%(env_key,env_value)

        job += 'export BH_CONFIG=%s\n'%tmp_config_name          #Always setting BH_CONFIG

        job += "\n#SBATCH -J '%s'\n"%setup['script_alias']      #Write Slurm parameters
        job += "#SBATCH -o /tmp/bh-slurm-%%j.out\n"
        job += "#SBATCH -e /tmp/bh-slurm-%%j.err\n"
        if partition is not None:
            job += "#SBATCH -p %s\n"%partition

        #We need to write the bohrium config file to an unique path
        job += 'echo "%s" > %s\n'%(setup['bh_config'], tmp_config_name)

        """
        job += "cd %s\n"%setup['cwd']                           #Change dir and execute cmd

        if setup['pre_clean']:
            job += "./misc/tools/bhutils.py clean\n"
        """

        outfile = "%s-%d"%(filename,i)
        cmd = ""
        if setup['use_time']:
            cmd += get_time("%s.time"%outfile)
        if setup['use_perf']:
            cmd += get_perf("%s.perf"%outfile)
        cmd += bridge_cmd

        if setup['save_data_output']:
            cmd += " --outputfn=%s"%outfile

        job += "%s "%cmd
        setup['cmd'] = cmd

        #Pipe the output to files
        job += '1> %s.out 2> %s.err\n'%(outfile,outfile)

        #Cleanup the config file
        job += "\nrm %s\n\n\n"%tmp_config_name

    setup['jobs'].append({'status': 'pending',
                          'filename': filename,
                          'nrun': nrun,
                          'script': job})

def prep_results(repos_root, suite_filename):
    """Extract meta-information from system and prepare the result-dict"""

    return {
        'meta': meta(repos_root, suite_filename),
        'runs': []
    }

def load_suite(filename):
    """Load the suite from file."""

    sys.path.append(os.path.abspath(os.path.dirname(filename)))
    return __import__(os.path.basename(filename)[:-3]).suites

def gen_jobs_bridge_format(result_file, config, args):
    """
    Generates benchmark jobs based on the "bridge/old" benchmark suite format.
    """

    results = prep_results(args.repos_root, args.suite_file.name)
    benchmarks = load_suite(args.suite_file.name)

    print "Benchmark suite '%s'; results are written to: %s" % (args.suite_file.name, result_file.name)
    i=0
    for benchmark in benchmarks:
        for script_alias, script, script_args in benchmark['scripts']:
            for bridge_alias, bridge_cmd, bridge_env in benchmark['bridges']:
                for manager_alias, manager, manager_cmd, manager_env in benchmark.get('managers', [('N/A',None,None,None)]):
                    for fuser_alias, fuser, fuser_env in benchmark.get('fusers', [('N/A', None, None)]):
                        for filtr_alias, filtr, filtr_env in benchmark.get('filters', [('N/A', None, None)]):
                            for engine_alias, engine, engine_env in benchmark.get('engines', [('N/A',None,None)]):

                                bh_config = StringIO.StringIO()
                                confparser = SafeConfigParser()     # Parser to modify the Bohrium configuration file.
                                confparser.read(config)             # Read current configuration
                                                                    # Set the current manager

                                manager = manager if manager else "node"
                                fuser = fuser if fuser else "topological"

                                has_filter = confparser.has_section(filtr)
                                if has_filter:
                                    confparser.set("bridge", "children", filtr)
                                    confparser.set(filtr, "children", manager)

                                # Check that fusers exists in configuration, set
                                # engine as child of fuser when they are available
                                # othervise set then as children of manager
                                has_fusers = confparser.has_section("greedy")
                                if has_fusers:
                                    confparser.set(
                                        manager,
                                        "children",
                                        fuser
                                    )
                                    if engine:          # Set the current engine
                                        confparser.set(fuser, "children", engine)
                                else:
                                    if engine:          # Set the current engine
                                        confparser.set(manager, "children", engine)

                                confparser.write(bh_config)         # And write it to a string buffer

                                envs = os.environ.copy()            # Populate environment variables
                                envs_overwrite = {}
                                if engine_env is not None:
                                    envs_overwrite.update(engine_env)
                                if manager_env is not None:
                                    envs_overwrite.update(manager_env)
                                if bridge_env is not None:
                                    envs_overwrite.update(bridge_env)

                                p = "Scheduling %s/%s on "%(bridge_alias,script)
                                if manager and manager != "node":
                                    p += "%s/"%manager_alias
                                print "%snode/%s"%(p,engine_alias)

                                run = {'script_alias':script_alias,
                                       'bridge_alias':bridge_alias,
                                       'engine_alias':engine_alias,
                                       'manager_alias':manager_alias,
                                       'script':script,
                                       'manager':manager,
                                       'engine':engine,
                                       'envs':envs,
                                       'envs_overwrite':envs_overwrite,
                                       'pre-hook': benchmark.get('pre-hook', None),
                                       'post-hook': benchmark.get('post-hook', None),
                                       'script' : script,
                                       'script_args' : script_args,
                                       'bridge_cmd' : bridge_cmd,
                                       'manager_cmd' : manager_cmd,
                                       'jobs':[],
                                       'bh_config':bh_config.getvalue(),
                                       'use_perf': args.with_perf,
                                       'use_time': args.with_time,
                                       'save_data_output': args.save_data,
                                       'pre_clean': args.pre_clean,
                                       'data_output': [],
                                       'use_slurm_default':benchmark.get('use_slurm_default', False),
                                       'elapsed': [],
                                       'timings': {},
                                       'time': [],
                                       'stdout': [],
                                       'stderr': [],
                                       'perf':[]}
                                njobs = 1
                                job_nrun = args.runs
                                if args.multi_jobs:
                                    njobs = args.runs
                                    job_nrun = 1
                                for _ in xrange(njobs):
                                    i += 1
                                    add_pending_job(run, job_nrun, args.partition)
                                results['runs'].append(run)
                                results['meta']['ended'] = str(datetime.now())

                                bh_config.close()
                                write2json(result_file, results)

class StackCombinator(object):
    """
    Construct a list of stack configurations.

    Creates all combinations of the different variations at each
    level in the stack. Starts with the outer-most.
    """

    def __init__(self, bohrium):
        """Count the number of variations at each level in the stack."""

        self.bohrium = bohrium

        combinations = {}
        for lvl, variations in enumerate(bohrium):
            combinations[lvl] = len(variations)

        self.combinations = combinations

    def sum(self):
        """Sum up the combinations are each level."""

        count = 0
        for lvl in self.combinations:
            count += self.combinations[lvl]
        return count

    def get(self):
        """Get a combination of component variations."""

        combination = []
        for lvl in xrange(0, len(self.combinations)):
            nvariations = self.combinations[lvl]
            combination.append(nvariations-1 if nvariations > 0 else 0)
        return combination

    def decrement(self):
        """Remove a combination"""

        for lvl in xrange(0, len(self.combinations)):
            if self.combinations[lvl] > 0:
                self.combinations[lvl] = self.combinations[lvl] -1
                break

    def get_confs(self):
        """Returns a list of configurations."""

        combinations = []
        while(self.sum()>0):
            combination = self.get()
            if combination not in combinations:
                combinations.append(combination)
            self.decrement()

        confs = []
        for combination in combinations:
            conf = []
            for lvl in xrange(0, len(combination)):
                variation = combination[lvl]
                conf.append(self.bohrium[lvl][variation])
            confs.append(conf)

        return confs

def gen_jobs_launcher_format(result_file, config, args):
    print("Launcher style.")

    results = prep_results(args.repos_root, args.suite_file.name)
    suites = load_suite(args.suite_file.name)

    print "Benchmark suite '%s'; results are written to: %s" % (args.suite_file.name, result_file.name)
    i=0
    for suite in suites:
        
        # Add a simple generator if we are not using Bohrium
        if not "bohrium" in suite or suite["bohrium"] == None:
            suite["bohrium"] = [[('NA', 'bridge', None)],[('NA', 'node', None)],[('NA', 'cpu', None)]]

        for script_alias, script, script_args in suite['scripts']:
            for launcher_alias, launcher_cmd, launcher_env in suite['launchers']:
                if "bohrium" in suite:    # Create Bohrium config

                    confparser = SafeConfigParser()     # Read current configuration
                    confparser.read(config)             # 

                    combinations = StackCombinator(suite["bohrium"]).get_confs()
                    
                    for stack in combinations:
                        envs = os.environ.copy()        # Orig environment variables
                        envs_overwrite = {}             # Overwritten by components

                        if not stack[0][1] == "bridge":
                            raise Exception("First component must be a bridge.")

                        engine = ""
                        engine_alias = ""
                        manager = ""
                        manager_alias = ""
                        manager_cmd = ""

                        component_names = []
                        for cidx, component in enumerate(stack):
                            last = cidx == len(stack)-1
                            comp_alias  = component[0]  # Grab the alias
                            comp_name   = component[1]  # Grab the name
                            comp_envs   = component[-1] # and environment

                            if comp_envs:               # Overwrite envs
                                envs_overwrite.update(comp_envs)

                            if not confparser.has_section(comp_name):
                                if args.bh_config_file == None:
                                    raise Exception("Component does not exist: " + str(comp_name) 
                                        + "\nThis is probably caused by not being able to find the Bohrium config file."
                                        + "\nTry setting --bh_config_file with the path to the Bohrium config file")
                                else:
                                    raise Exception("Component does not exist: " + str(comp_name))
                                                        
                                                        # Collect all components
                            if comp_name not in component_names:
                                component_names.append(comp_name)

                            # This is to remain backwards compatible.
                            comp_type = confparser.get(comp_name, "type")
                            if comp_type == "ve" and not engine:
                                engine = comp_name
                                engine_alias = comp_alias
                            elif comp_type == "vem" and not manager:
                                manager = comp_name
                                manager_alias = comp_alias
                                manager_cmd = component[2]

                            if not last:                # Set the child
                                name_child = stack[cidx+1][1]
                                confparser.set(comp_name, "children", name_child)
                            elif confparser.has_option(comp_name, "children"):
                                remove_option(comp_name, "children")

                        # Remove all unused components from configuration file
                        all_components = confparser.sections()
                        for comp_name in all_components:
                            if comp_name not in component_names:
                                confparser.remove_section(comp_name)

                        bh_config = StringIO.StringIO() # Construct a new config
                        confparser.write(bh_config)     # And write it to a string buffer

                        #
                        #   Now do this...
                        #
                        p = "Scheduling %s/%s on " % (launcher_alias, script)
                        if manager and manager != "node":
                            p += "%s/ " % manager_alias
                        print "%snode/%s" % (p, engine_alias)

                        run = {
                            'script_alias':script_alias,
                            'bridge_alias':launcher_alias,
                            'engine_alias':engine_alias,
                            'manager_alias':manager_alias,
                            'script':script,
                            'manager':manager,
                            'engine':engine,
                            'envs':envs,
                            'envs_overwrite':envs_overwrite,
                            'pre-hook': suite.get('pre-hook', None),
                            'post-hook': suite.get('post-hook', None),
                            'script' : script,
                            'script_args' : script_args,
                            'bridge_cmd' : launcher_cmd,
                            'manager_cmd' : manager_cmd,
                            'jobs':[],
                            'bh_config':bh_config.getvalue(),
                            'use_perf': args.with_perf,
                            'use_time': args.with_time,
                            'save_data_output': args.save_data,
                            'pre_clean': args.pre_clean,
                            'data_output': [],
                            'use_slurm_default':suite.get('use_slurm_default', False),
                            'elapsed': [],
                            'timings': {},
                            'time': [],
                            'stdout': [],
                            'stderr': [],
                            'perf':[]
                        }
                        njobs = 1
                        job_nrun = args.runs
                        if args.multi_jobs:
                            njobs = args.runs
                            job_nrun = 1
                        for _ in xrange(njobs):
                            i += 1
                            add_pending_job(run, job_nrun, args.partition)
                        results['runs'].append(run)
                        results['meta']['ended'] = str(datetime.now())

                        bh_config.close()
                        write2json(result_file, results)

def gen_jobs(result_file, config, args):
    """Generates benchmark jobs based on the benchmark suites"""

    benchmarks = load_suite(args.suite_file.name)
    nsuites = len(benchmarks)
    nnew = 0
    for suite in benchmarks:
        if "launchers" in suite:
            nnew += 1

    if nnew == 0:
        gen_jobs_bridge_format(result_file, config, args)
    elif nnew == nsuites:
        gen_jobs_launcher_format(result_file, config, args)
    else:
        print "ERROR! Cant mix and match launcher and bridge suite format."

def handle_result_file(result_file, args):
    """Execute, submits, and/or parse results of the benchmarks in 'result_file'
       Returns True when all benchmark runs is finished or failed"""

    result_file.seek(0)
    res = json.load(result_file)
    for run in res['runs']:
        for job in run['jobs']:
            if job['status'] == 'finished' or (job['status'] == 'failed' and not args.restart):
                continue
            slurm_id = job.get('slurm_id', None)
            if slurm_id is None or (job['status'] == 'failed' and args.restart):
                #The user wants to use SLURM
                if not args.no_slurm and (args.slurm or run.get('use_slurm_default',False)):
                    nnodes = run['envs'].get('BH_SLURM_NNODES', 1)
                    nnodes = run['envs_overwrite'].get('BH_SLURM_NNODES', nnodes)
                    slurm_run(job, nnodes, queue=None)
                else:
                    #The user wants local execution
                    p = "Executing %s/%s on "%(run['bridge_alias'],run['script'])
                    if run['manager'] and run['manager'] != "node":
                        p += "%s/"%run['manager_alias']
                    print "%snode/%s"%(p,run['engine_alias'])
                    if run['pre-hook'] is not None:
                        print "pre-hook cmd: \"%s\""%run['pre-hook']
                        check_call(run['pre-hook'], shell=True)
                    execute_run(job)
                    parse_run(run, job)
            else:#The job has been submitted to SLURM
                if slurm_run_finished(job):#And it is finished
                    parse_run(run, job)
            write2json(result_file, res)

    #Check if any jobs are pending
    for run in res['runs']:
        for job in run['jobs']:
            if job['status'] == 'pending':
                return False
    return True

