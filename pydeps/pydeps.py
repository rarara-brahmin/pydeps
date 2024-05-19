# -*- coding: utf-8 -*-
"""cli entrypoints.
"""
from __future__ import print_function
import json
import os
import sys

from pydeps.configs import Config
from . import py2depgraph, cli, dot, target
from .depgraph2dot import dep2dot, cycles2dot
import logging
from . import colors
log = logging.getLogger(__name__)


def _pydeps(trgt: target.Target, **kw):
    # kwは起動引数で指定されない場合、デフォルト値が詰まっている。
    colors.START_COLOR = kw.get('start_color')
    output = kw.get('output')
    fmt = kw['format']

    if os.getcwd() != trgt.workdir:
        os.chdir(trgt.workdir)

    dep_graph = py2depgraph.py2dep(trgt, **kw)

    dotsrc = depgraph_to_dotsrc(trgt, dep_graph, **kw)

    svg = dot.call_graphviz_dot(dotsrc, fmt)
    svg = svg.replace(b'</title>', b'</title><style>.edge>path:hover{stroke-width:8}</style>')

    with open(output, 'wb') as fp:
        cli.verbose("Writing output to:", output)
        fp.write(svg)

    dot.display_svg(kw, output)


def depgraph_to_dotsrc(target, dep_graph, **kw):
    """Convert the dependency graph (DepGraph class) to dot source code.
    """
    if kw.get('show_cycles'):
        dotsrc = cycles2dot(target, dep_graph, **kw)
    elif not kw.get('no_dot'):
        dotsrc = dep2dot(target, dep_graph, **kw)
    else:
        dotsrc = None
    return dotsrc


def externals(trgt, **kwargs):
    """Return a list of direct external dependencies of ``pkgname``.
       Called for the ``pydeps --externals`` command.
    """
    kw = dict(
        T='svg', config=None, debug=False, display=None, exclude=[], exclude_exact=[],
        externals=True, format='svg', max_bacon=2**65, no_config=True, nodot=False,
        noise_level=2**65, no_show=True, output=None, pylib=True, pylib_all=True,
        show=False, show_cycles=False, show_deps=False, show_dot=False,
        show_raw_deps=False, verbose=0, include_missing=True, start_color=0
    )
    kw.update(kwargs)
    depgraph = py2depgraph.py2dep(trgt, **kw)
    pkgname = trgt.fname
    log.info("DEPGRAPH: %s", depgraph)
    pkgname = os.path.splitext(pkgname)[0]

    res = {}
    ext = set()

    for k, src in list(depgraph.sources.items()):
        if k.startswith('_'):
            continue
        if not k.startswith(pkgname):
            continue
        if src.imports:
            imps = [imp for imp in src.imports if not imp.startswith(pkgname)]
            if imps:
                for imp in imps:
                    ext.add(imp.split('.')[0])
                res[k] = imps
    # return res  # debug
    return list(sorted(ext))


def pydeps(**args):
    """Entry point for the ``pydeps`` command.

       This function should do all the initial parameter and environment
       munging before calling ``_pydeps`` (so that function has a clean
       execution path).
    """

    # 再帰回数の上限設定
    sys.setrecursionlimit(10000)

    _args = cli.parse_args(sys.argv[1:])
    # コマンドライン引数を解析して_argsに詰める。引数がない場合もデフォルトを指定。
    # 入力変数のargsは__main__.pyでは詰められていないので気にしなくてよし。

    _args['curdir'] = os.getcwd()
    # カレントディレクトリも_argsに詰めておく

    inp = target.Target(_args['fname'])
    # ターゲットファイルの属性解析(ターゲット=inp)

    log.debug("Target: %r", inp)


    _args['output'] = os.path.join(
        inp.calling_dir,
        inp.modpath.replace('.', '_') + '.' + _args.get('format', 'svg'))

    with inp.chdir_work():
        """
        self.workdir: ターゲットファイルのディレクトリ
        """
        # log.debug("Current directory: %s", os.getcwd())
        _args['fname'] = inp.fname
        _args['isdir'] = inp.is_dir

        return _pydeps(inp, **_args)


def call_pydeps(file_or_dir, **kwargs):
    """Programatic entry point for pydeps.

       See :class:`pydeps.configs.Config` class for the available options.
    """
    sys.setrecursionlimit(10000)
    inp = target.Target(file_or_dir)
    log.debug("Target: %r", inp)
    config = Config(**kwargs)

    if config.output:
        config.output = os.path.abspath(config.output)
    else:
        config.output = os.path.join(
            inp.calling_dir,
            inp.modpath.replace('.', '_') + '.' + config.format
        )

    ctx = dict(iter(config))

    with inp.chdir_work():
        ctx['fname'] = inp.fname
        ctx['isdir'] = inp.is_dir
        if config.externals:
            del ctx['fname']
            return externals(inp, **ctx)

        return _pydeps(inp, **ctx)


if __name__ == '__main__':  # pragma: nocover
    pydeps()
