#!/usr/bin/env python3
# Requires Python 3.6 or later

import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable, Optional

# TODO
# - remove pex
# - update branch
# - push review
# - land changes

def main(argv):
  flow = GFlow()
  print(argv)
  bin_name = Path(argv[0]).name
  method = flow.method(bin_name)
  args = argv[1:]

  if method is None and len(argv) > 1:
    method = flow.method(argv[1])
    args = argv[2:]

  if method is None:
    print("Usage: {} action [opts...]".format(bin_name))
    sys.exit(1)

  try:
    method(*args)
  except subprocess.CalledProcessError as e:
    print(e.stderr, file=sys.stderr)
    sys.exit(e.returncode)
  except KeyboardInterrupt:
    sys.exit(1)


class GFlow:
  def __init__(self):
    pass

  def method(self, name: str) -> Optional[Callable]:
    sanitized = "do_" + name.replace("-", "_")
    if hasattr(self, sanitized):
      return getattr(self, sanitized)

  def do_current_branch(self):
    """Prints the current branch name"""
    print(self._current_branch())

  def do_publish(self, *args):
    """
    Pushes a branch (default: the current branch) to origin, overwriting it unconditionally.
    Refuses to publish master.
    """
    ap = ArgumentParser()
    ap.add_argument("--no-verify", action='store_true', help="Skips pre-push hooks")
    ap.add_argument("branch", nargs='?', help="Branch name to publish (defaults to current)")
    pargs = ap.parse_args(args)

    branch = pargs.branch or self._current_branch()
    if branch == 'master':
      print("Refusing to publish master branch. Use git push directly")
      sys.exit(1)

    gargs = ["--force"]
    if pargs.no_verify:
      gargs.append("--no-verify")

    self._git_run("push", "origin", "{0}:{0}".format(branch), *gargs)

  def do_unpublish(self, *args):
    """
    Deletes a branch from the origin unconditionally.
    Refuses to unpublish master.
    """
    ap = ArgumentParser()
    ap.add_argument("--rm", action='store_true', help="Removes local branch too")
    ap.add_argument("branches", nargs='*', default=(), help="Branch name to unpublish (defaults to current)")
    pargs = ap.parse_args(args)

    current_branch = self._current_branch()
    if pargs.branches:
      branches = pargs.branches
    else:
      branches = [current_branch]

    for branch in branches:
      if branch == "master":
        print("Refusing to delete master branch")
        continue
      if branch == current_branch:
        self._git_run("checkout", "master")
      self._git_run("push", "origin", "--delete", branch)
      if pargs.rm:
        self._git_run("branch", "-d", branch)

  def _current_branch(self) -> str:
    return self._git_cap("rev-parse", "--abbrev-ref", "HEAD").strip()

  def _git_cap(self, *args) -> str:
    """
    Runs git and return stdout captured in a string.

    Throws CalledProcessError if git exits with non-zero status.
    """
    cmd = ["git"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    if proc.stderr:
      print(proc.stderr, file=sys.stderr)
    return proc.stdout

  def _git_run(self, *args):
    """
    Runs git without capturing output (it goes to this process's stdout/stderr

    Throws CalledProcessError if git exists with non-zero status.
    """
    cmd = ["git"] + list(args)
    echo = ' '.join(cmd)
    if sys.stdout.isatty():
      echo = "\033[2m" + echo + "\033[0m"
    else:
      echo = "> " + echo

    print(echo)
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
  main(sys.argv)
