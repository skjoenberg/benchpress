#!/usr/bi "\\",n/env python
# -*- coding: utf8 -*-
import string
import os
import matplotlib
matplotlib.use('Agg')   # Essential for "headless" operation
import pylab

def brange(begin, end):
    thres = 0
    i = 0
    while thres < end:
        thres = 2**i
        i += 1
    thres = end
        
    c = i = begin
    while i <= end:
        yield i
        i = 2**c
        c += 1

def sanitize_fn(filename):
    valid_chars = ".-_%s%s" % (string.digits, string.ascii_lowercase)
    sanitized = []
    for idx, char in enumerate(filename.lower()):
        if char not in valid_chars:
            char = "_"
        sanitized.append(char)
    return "".join(sanitized)

def texsafe(text):
    """Escape text such that it is tex-safe."""
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless',
        '>': r'\textgreater',
    }
    escaped = []
    
    for char in text:
        if char in conv:
            char = conv[char]
        escaped.append(char)
    return "".join(escaped)

class Graph(object):
    """
    Baseclass for rendering Matplotlib graphs.
    Does alot of the annoying work, just override the plot(...) method,
    and you are good to go!
    """

    colors = [
        "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666",
        "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666",
        "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666",
        "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666",
    ]

    markers = [
        r'o',
        r's',
        r'D',
        r'*',
        r'<',
        r'>',
        r'^',
        r'v',
        r'$\clubsuit$',
        r'p',
        r'd',
    ]

    marker_sizes = [
        6,6,6,9,7,
        7,7,7,7,7,
        7,7
    ]

    hatches = [
        r'o',
        r's',
        r'D',
        r'*',
        r'<',
        r'>',
        r'^',
        r'v',
        r'$\clubsuit$',
        r'p',
        r'd',
    ]

    def __init__(
        self,
        title = "Untitled Graph",
        line_width = 2,
        fn_pattern = "{title}.{ext}",
        file_formats = ["png"],
        directory="."):

        self.title = title
        self.fn_pattern = fn_pattern
        self.file_formats = file_formats
        self.output_path = os.path.expandvars(os.path.expanduser(directory))
        self.line_width = line_width

        self._mpl_init()

    def _mpl_init(self):
        matplotlib.rcParams['axes.labelsize'] = 12
        matplotlib.rcParams['axes.titlesize'] = 14
        matplotlib.rcParams['xtick.labelsize'] = 12
        matplotlib.rcParams['ytick.labelsize'] = 12
        matplotlib.rcParams['legend.fontsize'] = 12
        matplotlib.rcParams['font.family'] = 'serif'
        matplotlib.rcParams['font.serif'] = ['Computer Modern Roman']
        matplotlib.rcParams['text.usetex'] = True
        matplotlib.rcParams['figure.max_open_warning'] = 400

    def plot(self):
        raise Exception("Unimplemented the actual plotting.")

    def prep(self):
        pylab.clf()                     # Essential! Othervise the plots will be f**d up!
        pylab.figure(1)

        pylab.gca().yaxis.grid(True)    # Makes it easier to compare bars
        pylab.gca().xaxis.grid(False)
        pylab.gca().set_axisbelow(True)

    def tofile(self, fn_args):          # Creates the output-file.

        if not os.path.exists(self.output_path):
            raise("Output path %s does not exists. Cannot spit out graphs")

        paths = []
        for file_format in self.file_formats:
        
            filename = sanitize_fn(self.fn_pattern.format(
                ext=file_format,
                **fn_args
            ))
            abs_path = os.sep.join([
                self.output_path,
                filename
            ])
            paths.append(abs_path)

            pylab.savefig(abs_path)
            pylab.show()

        return paths
