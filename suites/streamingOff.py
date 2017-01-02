from benchpress.default import *

scripts = [
    ('X-ray 1e10',   'xraysim',          '--size=20*40*10'),
    ('MC Pi 1.2e10', 'montecarlo_pi',    '--size=100000000*10'),
    ('MFE 2.3e10',   'idl_init_explode', '--size=40*40*10'),
    ('BEAN 5e9',     'galton_bean_machine', '--size=1000000*1000'),   
]

stack_openmp = [
    [('default',    'bridge',None)],
    [('bcexp',      'bcexp', None)],
    [('bccon',      'bccon', None)],
    [\
      ('streamOn',  'node',  {"BH_OPENMP_ARRAY_CONTRACTION":"1"}),
      ('streamOff', 'node',  {"BH_OPENMP_ARRAY_CONTRACTION":"0"}) \
    ],
    [('openmp',     'openmp',None)],
]

suite_openmp = {
    'scripts': scripts,
    'launchers':  [python_bohrium],
    'bohrium': stack_openmp
}

suites = [
    suite_openmp,
]
