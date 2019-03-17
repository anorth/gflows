#!/usr/bin/env python3
# Requires Python 3.6 or later

import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable, Optional
from subprocess import CalledProcessError


# TODO
# - update branch
# - push review
# - land changes

def main(argv):
  flow = GFlow()
  # print(argv)
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
  except CalledProcessError as e:
    print(e.stderr, file=sys.stderr)
    sys.exit(e.returncode)
  except FlowError as e:
    if e.message is not None:
      print(e.message, file=sys.stderr)
    sys.exit(e.status)
  except KeyboardInterrupt:
    sys.exit(1)


class FlowError(RuntimeError):
  def __init__(self, message=None, status=1):
    self.message = message
    self.status = status


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
      raise FlowError("Refusing to publish master branch, use git push directly.")

    extra_args = ["--force"]
    if pargs.no_verify:
      extra_args.append("--no-verify")

    self._git_run("push", "origin", "{0}:{0}".format(branch), *extra_args)

  def do_unpublish(self, *args):
    """
    Deletes a branch from the origin unconditionally.
    Refuses to unpublish master.
    """
    ap = ArgumentParser()
    ap.add_argument("--rm", action='store_true', help="Removes local branch too")
    ap.add_argument("branches", nargs='*', default=(),
      help="Branch name to unpublish (defaults to current)")
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

  def do_land(self, *args):
    """Lands changes on origin/master and updates local refs."""
    self._no_changes()

    ap = ArgumentParser()
    ap.add_argument("--on", help="Target branch to land changes on (defaults to master)")
    ap.add_argument("--no-verify", action='store_true', help="Skips pre-push hooks")
    ap.add_argument("source", nargs='?', help="Ref name to land (defaults to HEAD)")
    pargs = ap.parse_args(args)

    source = pargs.source or "HEAD"
    target = pargs.on or "master"
    extra_args = []
    if pargs.no_verify:
      extra_args.append("--no-verify")

    print("Pushing " + source + " to origin/" + target)

    # Push directly to origin, which will fail if not a fast-forward
    self._git_run("push", "origin", source + ":" + target, *extra_args)
    self._git_run("fetch", "origin", "master")
    # Equivalent, faster, maybe less safe: push the same thing locally
    # self._git_run("push", ".", source + ":" + target, "--no-verify", *extra_args)

  def _current_branch(self) -> str:
    return self._git_cap("rev-parse", "--abbrev-ref", "HEAD").strip()

  def _no_changes(self):
    """Raises FlowError if there are unstaged or uncommitted changes."""
    try:
      self._git_cap("diff", "--exit-code")
    except CalledProcessError:
      self._git_run("status", quiet=True)
      raise FlowError()

    try:
      self._git_cap("diff", "--cached", "--exit-code")
    except CalledProcessError:
      self._git_run("status", quiet=True)
      raise FlowError()

  def _git_cap(self, *args) -> str:
    """
    Runs git and return stdout captured in a string.

    Raises CalledProcessError if git exits with non-zero status.
    """
    cmd = ["git"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    if proc.stderr:
      print(proc.stderr, file=sys.stderr)
    return proc.stdout

  def _git_run(self, *args, quiet=False):
    """
    Runs git without capturing output (it goes to this process's stdout/stderr

    Raises CalledProcessError if git exists with non-zero status.
    """
    cmd = ["git"] + list(args)
    echo = ' '.join(cmd)
    if sys.stdout.isatty():
      echo = "\033[2m" + echo + "\033[0m"
    else:
      echo = "> " + echo

    if not quiet:
      print(echo)
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
  main(sys.argv)
