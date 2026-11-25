"""Reject stale Python modules or QML resources in a local packaged build."""
import argparse
from pathlib import Path
from types import CodeType
from PyInstaller.archive.readers import CArchiveReader

def normalized(code):
    return code.replace(co_filename='<source>',co_consts=tuple(normalized(x) if isinstance(x,CodeType) else x for x in code.co_consts))

def check(executable,root):
    archive=CArchiveReader(str(executable));python=archive.open_embedded_archive('PYZ.pyz');mismatches=[]
    for name in python.toc:
        if name!='freshtray' and not name.startswith('freshtray.'):continue
        source=root/'src'/Path(*name.split('.'))
        source=source/'__init__.py' if source.is_dir() else source.with_suffix('.py')
        if not source.is_file():continue
        expected=compile(source.read_bytes(),str(source),'exec',dont_inherit=True,optimize=0)
        if normalized(expected)!=normalized(python.extract(name)):mismatches.append(name)
    for source in (root/'src/freshtray/qml').glob('*.qml'):
        key='freshtray\\qml\\'+source.name
        if key not in archive.toc or archive.extract(key)!=source.read_bytes():mismatches.append(source.name)
    if mismatches:raise RuntimeError('Packaged sources differ: '+', '.join(mismatches))
    print('PASS: packaged FreshTray Python modules and QML match current source')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('executable',type=Path);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args();check(args.executable,args.root)
