from __future__ import annotations

import multiprocessing
from pathlib import Path
import stat
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from client import core, installation, update_package as package


def make_archive(path, target='9.9.9', extra=()):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('DQAConnect.exe', b'MZ-app')
        archive.writestr('runtime/python.exe', b'MZ-python')
        archive.writestr('install-complete.txt', target)
        for name, data in extra:
            archive.writestr(name, data)
    return path


@pytest.fixture
def installed(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    old = root / 'versions/1.4.0-1'
    (old / 'runtime').mkdir(parents=True)
    (old / 'DQAConnect.exe').write_bytes(b'MZ-current')
    (old / 'runtime/python.exe').write_bytes(b'MZ-runtime')
    (old / 'install-complete.txt').write_text('1.4.0')
    (root / 'DQALauncher.exe').write_bytes(b'MZ-launcher')
    (root / 'active-slot.txt').write_text(old.name)
    monkeypatch.setattr(core, 'app_dir', lambda: old)
    monkeypatch.setattr(package, 'verify_slot', lambda slot: True)
    return root, old


def test_apply_preserves_all_old_bytes_and_switches_only_after_validation(installed, tmp_path, monkeypatch):
    root, old = installed
    before = {p.relative_to(old): p.read_bytes() for p in old.rglob('*') if p.is_file()}
    def verify(slot):
        assert (root / 'active-slot.txt').read_text() == old.name
        assert (slot / 'runtime/python.exe').read_bytes() == b'MZ-python'
        return True
    monkeypatch.setattr(package, 'verify_slot', verify)
    assert package.apply_package(make_archive(tmp_path/'update.zip'), '9.9.9') == '9.9.9'
    assert installation.active_version(root) == '9.9.9'
    assert before == {p.relative_to(old): p.read_bytes() for p in old.rglob('*') if p.is_file()}


@pytest.mark.parametrize('name', ['../escape', '/escape', 'C:/escape', 'x\\escape', 'x/../escape',
    'x//escape', 'x:stream', 'CON', 'a/NUL.txt', 'COM1.txt', 'a /x', 'a./x', 'runtime/python.exe',
    'RUNTIME/PYTHON.EXE', 'bad\x01name'])
def test_unsafe_windows_names_fail_without_activation(installed, tmp_path, name):
    root, old = installed
    archive = make_archive(tmp_path/'update.zip', extra=[(name,b'evil')])
    with pytest.raises((ValueError, FileExistsError)):
        package.apply_package(archive, '9.9.9')
    assert (root / 'active-slot.txt').read_text() == old.name
    assert list((root/'versions').iterdir()) == [old]


def test_symlink_entry_is_rejected(installed, tmp_path):
    entry=zipfile.ZipInfo('escape')
    entry.create_system=3
    entry.external_attr=(stat.S_IFLNK | 0o777)<<16
    with pytest.raises(ValueError):
        package.apply_package(make_archive(tmp_path/'update.zip',extra=[(entry,b'../out')]),'9.9.9')


@pytest.mark.parametrize('failure', ['budget','startup','version','activation','corrupt','write'])
def test_failure_keeps_pointer_and_removes_own_incomplete_slot(installed, tmp_path, monkeypatch, failure):
    root, old = installed
    archive=make_archive(tmp_path/'update.zip',target='9.9.8' if failure=='version' else '9.9.9')
    if failure=='budget': monkeypatch.setattr(package,'MAX_EXPANDED_BYTES',5)
    if failure=='startup': monkeypatch.setattr(package,'verify_slot',lambda _:False)
    if failure=='corrupt': archive.write_bytes(b'PK broken')
    def fail(*a,**k): raise OSError('disk failure')
    if failure=='activation': monkeypatch.setattr(package,'activate_slot',fail)
    if failure=='write': monkeypatch.setattr(package.os,'fsync',fail)
    with pytest.raises((ValueError,OSError,zipfile.BadZipFile)):
        package.apply_package(archive,'9.9.9')
    assert (root/'active-slot.txt').read_text()==old.name
    assert list((root/'versions').iterdir())==[old]


def test_repeat_or_older_target_never_reopens_archive(installed, tmp_path):
    root, old=installed
    for target in ('1.4.0','1.3.0'):
        assert package.apply_package(tmp_path/'absent.zip',target)=='1.4.0'
    assert list((root/'versions').iterdir())==[old]


def test_versions_symlink_is_rejected(installed, tmp_path):
    root, _=installed
    moved=tmp_path/'outside'
    (root/'versions').rename(moved)
    (root/'versions').symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError):
        package.apply_package(make_archive(tmp_path/'update.zip'),'9.9.9')


def _contend(root, output):
    try:
        with package.update_lock(Path(root)): output.put('acquired')
    except (BlockingIOError,OSError): output.put('busy')


def test_other_process_cannot_update_until_lock_is_released(installed):
    root, _=installed
    ctx=multiprocessing.get_context('spawn')
    output=ctx.Queue()
    with package.update_lock(root):
        child=ctx.Process(target=_contend,args=(str(root),output));child.start();child.join(10)
        assert child.exitcode==0 and output.get(timeout=2)=='busy'
    child=ctx.Process(target=_contend,args=(str(root),output));child.start();child.join(10)
    assert child.exitcode==0 and output.get(timeout=2)=='acquired'
