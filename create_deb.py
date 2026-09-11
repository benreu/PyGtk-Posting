# create_deb.py
#
# Copyright (C) 2018 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# run this file with the command    python3 ./create_deb.py
# (dpkg-deb --root-owner-group makes root own the files, so no fakeroot)

import shutil, os, sys, subprocess, re, gzip, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# git decides what exists; these are the only trees anything is swept from
PACKAGED_DIRS = ("src", "templates", "help", "icons")
# (source prefix, suffixes that ship, destination prefix). whatever lies
# below the source prefix keeps its relative path under the destination,
# so src/admin/x.ui lands in .../ui/admin/x.ui. first matching row wins.
ROUTES = (
	("src", (".py", ".sql"), "usr/lib/python3/dist-packages/pygtk_posting"),
	("src", (".ui",), "usr/share/pygtk_posting/ui"),
	("templates", (".odt", ".txt", ".html"), "usr/share/pygtk_posting/templates"),
	("help/C/pygtk-posting", (".page",), "usr/share/help/C/pygtk-posting"),
	("icons", None, "usr/share/icons"),
)
# src/linuxzpl is the LinuxZPL submodule, a whole application. Only its zplcore
# engine and gtkui frontend are Posting's business; qtui is PySide2, tests
# imports qtui, and linuxzpl.py is its standalone launcher. None are ever
# imported by Posting, so shipping them would be dead weight in the .deb.
SKIP_PATHS = tuple(Path("src", "linuxzpl", name)
					for name in ("qtui", "tests", "linuxzpl.py"))
# 1:1 copies into unrelated trees, with the mode debian policy wants: only
# the launcher and the maintainer scripts are executable
SINGLE_FILES = (
	("pygtk-posting", "usr/bin", 0o755),
	("pygtk-posting.desktop", "usr/share/applications", 0o644),
	("copyright", "usr/share/doc/pygtk-posting", 0o644),
	("code128.ttf", "usr/share/fonts/truetype/code128", 0o644),
	("control", "DEBIAN", 0o644),
	("postinst", "DEBIAN", 0o755),
	("prerm", "DEBIAN", 0o755),
)
# (source, destination file) pairs that policy wants gzipped at level 9
GZIPPED_FILES = (
	("changelog", "usr/share/doc/pygtk-posting/changelog.gz"),
	("pygtk-posting.1", "usr/share/man/man1/pygtk-posting.1.gz"),
)


def git_ls_files (*args, cwd = None):
	"NUL separated so git never quotes a path, decoded the way the os sees names"
	out = subprocess.run(["git", "ls-files", "-z", *args], cwd = cwd,
						capture_output = True, check = True).stdout
	return [os.fsdecode(name) for name in out.split(b"\0") if name]


def tracked_files ():
	"every file git knows about under the packaged trees, submodule included"
	return [Path(name) for name in
			git_ls_files("--recurse-submodules", "--", *PACKAGED_DIRS)]


def destination (path):
	"where a repo-relative file lands in the package, or None if it does not ship"
	if any(path.is_relative_to(skip) for skip in SKIP_PATHS):
		return None
	for source, suffixes, dest in ROUTES:
		if path.is_relative_to(source) and (suffixes is None or path.suffix in suffixes):
			return Path(dest) / path.relative_to(source)
	return None


def check_submodule ():
	"a .deb built without the submodule ships a designer that cannot open"
	if not Path("src", "linuxzpl", "zplcore").is_dir():
		raise SystemExit("src/linuxzpl is empty. Run:\n"
							"    git submodule update --init src/linuxzpl")
	status = subprocess.run(["git", "submodule", "status", "src/linuxzpl"],
							capture_output = True, text = True).stdout
	if status.startswith('+'):
		print("WARNING: src/linuxzpl is not at the pinned commit, so this "
				"package would ship an engine no commit describes:\n  "
				+ status.strip())


def warn_untracked ():
	"a module that was never git added would silently be missing from the .deb"
	names = git_ls_files("--others", "--exclude-standard", "--", *PACKAGED_DIRS)
	# --others does not recurse into submodules, so ask linuxzpl itself
	names += ["src/linuxzpl/" + name for name in
				git_ls_files("--others", "--exclude-standard", cwd = "src/linuxzpl")]
	missing = [name for name in names if destination(Path(name)) is not None]
	if missing:
		print("WARNING: these files would ship but are not tracked by git, "
				"so they are NOT in this package (git add them if they belong):")
		for name in missing:
			print("  " + name)


def posting_version ():
	"VERSION in src/constants.py is the one source, shared with the about dialog"
	sys.dont_write_bytecode = True
	sys.path.insert(0, str(ROOT / "src"))
	from constants import VERSION
	return VERSION


def write_control_version (version):
	"keep the tracked control file in step with constants.py"
	control = Path("control")
	text, count = re.subn(r"^Version: .*$", "Version: " + version,
							control.read_text(), count = 1, flags = re.M)
	if count != 1:
		raise SystemExit("control has no Version: line")
	control.write_text(text)


def check_changelog (version):
	"the changelog is written by hand, so make sure it was not forgotten"
	top = Path("changelog").read_text().split("\n", 1)[0]
	match = re.match(r"^pygtk-posting \((\S+)\) ", top)
	if match is None:
		raise SystemExit("changelog does not start with a 'pygtk-posting (version)' entry")
	if match.group(1) != version:
		raise SystemExit("changelog's newest entry is %s but src/constants.py says %s. "
							"Add a changelog entry for this release." % (match.group(1), version))


def copy_tracked_files (package_folder):
	"copy every tracked file that has a place in the package"
	copied = 0
	for path in tracked_files():
		dest = destination(path)
		if dest is None:
			continue
		target = package_folder / dest
		target.parent.mkdir(parents = True, exist_ok = True)
		shutil.copy2(path, target)
		os.chmod(target, 0o644)
		copied += 1
	return copied


def copy_single_files (package_folder):
	"launcher, desktop entry, docs, font and the debian maintainer files"
	for name, dest, mode in SINGLE_FILES:
		target = package_folder / dest
		target.mkdir(parents = True, exist_ok = True)
		shutil.copy2(name, target)
		os.chmod(target / name, mode)


def gzip_files (package_folder):
	"changelog and man page. mtime 0 keeps the archive reproducible"
	for name, dest in GZIPPED_FILES:
		target = package_folder / dest
		target.parent.mkdir(parents = True, exist_ok = True)
		with gzip.GzipFile(target, "wb", compresslevel = 9, mtime = 0) as gz:
			gz.write(Path(name).read_bytes())
		os.chmod(target, 0o644)


def write_md5sums (package_folder):
	"DEBIAN/md5sums lets dpkg --verify spot files changed after installing"
	lines = []
	for path in sorted(package_folder.rglob("*")):
		if path.is_file() and not path.is_relative_to(package_folder / "DEBIAN"):
			digest = hashlib.md5(path.read_bytes()).hexdigest()
			lines.append("%s  %s\n" % (digest, path.relative_to(package_folder)))
	md5sums = package_folder / "DEBIAN" / "md5sums"
	md5sums.write_text("".join(lines))
	os.chmod(md5sums, 0o644)


def main ():
	os.chdir(ROOT)
	os.umask(0o022) # so every directory the package creates is 0755
	if shutil.which("dpkg-deb") is None:
		raise SystemExit("dpkg-deb is not installed")
	check_submodule()
	warn_untracked()
	version = posting_version()
	check_changelog(version)
	write_control_version(version)
	package_name = "pygtk_posting_%s-1" % version
	package_folder = ROOT / package_name
	if package_folder.exists():
		print("removing %s left behind by an earlier run" % package_name)
		shutil.rmtree(package_folder)
	copied = copy_tracked_files(package_folder)
	copy_single_files(package_folder)
	gzip_files(package_folder)
	write_md5sums(package_folder)
	print("%d tracked files packaged" % copied)
	subprocess.run(["dpkg-deb", "--build", "--root-owner-group", package_name],
					check = True)
	if shutil.which("lintian") is None:
		print("lintian is not installed, skipping the package check")
	else:
		subprocess.call(["lintian", package_name + ".deb"])
	shutil.rmtree(package_folder)


if __name__ == "__main__":
	main()
