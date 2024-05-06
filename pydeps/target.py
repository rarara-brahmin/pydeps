# -*- coding: utf-8 -*-
"""
Abstracting the target for pydeps to work on.
"""
from __future__ import print_function
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
import logging
log = logging.getLogger(__name__)


class Target(object):
    """
    The compilation target.
    ファイル名、配置場所、属性(存在有無、Pythonファイルか、モジュールか)などのフラグの作成
    モジュールであればos.depを.に置換するなどの解析の前処理
    """
    is_pysource = False
    is_module = False
    is_dir = False

    def __init__(self, path):
        # log.debug("CURDIR: %s, path: %s, exists: %s", os.getcwd(), path, os.path.exists(path))
        # print("Target::CURDIR: %s, path: %s, exists: %s" % (os.getcwd(), path, os.path.exists(path)))

        self.calling_fname = path
        self.calling_dir = os.getcwd()
        self.exists = os.path.exists(path)

        if self.exists:
            self.path = os.path.realpath(path)
        else:  # pragma: nocover
            # nocoverはカバレッジ対象外の宣言
            print("No such file or directory:", repr(path), file=sys.stderr)
            if os.path.exists(path + '.py'):
                print("..did you mean:", path + '.py', '?', file=sys.stderr)
            sys.exit(1)
        self.is_dir = os.path.isdir(self.path)
        self.is_module = self.is_dir and '__init__.py' in os.listdir(self.path)
        self.is_pysource = os.path.splitext(self.path)[1] in ('.py', '.pyc', '.pyo', '.pyw')
        self.fname = os.path.basename(self.path)
        if self.is_dir:
            self.dirname = self.fname
            self.modname = self.fname
        else:
            self.dirname = os.path.dirname(self.path)
            self.modname = os.path.splitext(self.fname)[0]

        if self.is_pysource:
            # we will work directly on the file (in-situ)
            self.workdir = os.path.dirname(self.path)
        else:
            self.workdir = os.path.realpath(tempfile.mkdtemp())

        self.syspath_dir = self.get_package_root()
        # split path such that syspath_dir + relpath == path
        self.relpath = self.path[len(self.syspath_dir):].lstrip(os.path.sep)
        if self.is_dir:
            self.modpath = self.relpath.replace(os.path.sep, '.')
        else:
            self.modpath = os.path.splitext(self.relpath)[0].replace(os.path.sep, '.')
        self.package_root = os.path.join(
            self.syspath_dir,
            self._path_parts(self.relpath)[0]
        )

    @contextmanager
    def chdir_work(self):
        """
        コンテキストマネージャなのでwith句で使用する。
        (1)最初にself.workdirに移動して、ターゲットのパッケージのルートディレクトリをモジュール検索パスの先頭に加えてから
        (2)呼び元の操作を実行して、
        (3)最後にself.calling_dirに移動して、ターゲットのパッケージのルートディレクトリをモジュール検索パスの先頭から削除する
        """
        try:
            os.chdir(self.workdir)
            sys.path.insert(0, self.syspath_dir)
            # ターゲットのパッケージのルートディレクトリをモジュール検索パスの先頭に加える
            yield
        finally:
            os.chdir(self.calling_dir)
            if sys.path[0] == self.syspath_dir:
                sys.path = sys.path[1:]
                # モジュール検索パスの先頭がターゲットのパッケージのルートディレクトリであれば、モジュール検索パスからそれを除外する
            self.close()

    def get_package_root(self):
        """
        __init__.pyが含まれないディレクトリを探して返す（__init__.pyが含まれるフォルダはパッケージとして扱われる）
        """
        for d in self.get_parents():
            if '__init__.py' not in os.listdir(d):
                # __init__.pyが含まれないディレクトリを探して返す（__init__.pyが含まれるフォルダはパッケージとして扱われる）
                return d

        raise Exception(
            "do you have an __init__.py file at the "
            "root of the drive..?")  # pragma: nocover

    def get_parents(self):
        """
        C:\a\b\testというパスの場合、["C:\a\b\test", "C:\a\b", "C:\a"]という順のリストを作成する
        """
        def _parent_iter():
            parts = self._path_parts(self.path)
            # パス文字列を分解する
            for i in range(1, len(parts)):
                yield os.path.join(*parts[:-i])
                # リスト名に*をつけるとリストがアンパックして渡される
                # パスをディレクトリごとに区切ってリスト化している場合には、結合時に上記の表記が必要
        return list(_parent_iter())

    def _path_parts(self, pth):
        """
        Return a list of all directories in the path ``pth``.
        パス文字列を\もしくは/で分割する。パスのトップが/（＝Linux？）のときには先頭に/を加える
        """
        res = re.split(r"[\\/]", pth)
        if res and os.path.splitdrive(res[0]) == (res[0], ''):
            # ドライブ名が空文字（＝Linux？）のとき、ドライブ名に"/"を加える
            res[0] += os.path.sep
        return res

    def __del__(self):
        self.close()

    def close(self):
        """Clean up after ourselves.
        """
        try:
            # make sure we don't delete the user's source file if we're working
            # on it in-situ.
            if not self.is_pysource and hasattr(self, 'workdir'):
                shutil.rmtree(self.workdir)
        except OSError:
            pass

    def __repr__(self):  # pragma: nocover
        return json.dumps(
            {k: v for k, v in self.__dict__.items() if not k.startswith('_')},
            indent=4, sort_keys=True
        )
