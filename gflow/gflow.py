#!/usr/bin/env python3
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable, Optional

from sh import git
import sh


class GFlow:
  def __init__(self):
    pass

  def method(self, name: str) -> Optional[Callable]:
    sanitized = "do_" + name.replace("-", "_")
    if hasattr(self, sanitized):
      return getattr(self, sanitized)

  def do_current_branch(self):
    print(self._current_branch())

  def do_publish(self, *args):
    ap = ArgumentParser()
    ap.add_argument("--force", action='store_true')
    ap.add_argument("branch", nargs='?', help="Branch name to publish (defaults to current)")
    pargs = ap.parse_args(args)

    branch = pargs.branch or self._current_branch()
    gargs = ["--no-verify"]
    if pargs.force:
      gargs.append("--force")

    print(self._git("push", "origin", "{0}:{0}".format(branch), gargs), end='')

  def do_unpublish(self, *args):
    ap = ArgumentParser()
    ap.add_argument("--rm", action='store_true', help="Removes local branch too")
    ap.add_argument("--merged", action='store_true', help="Removes all branches which which master is up to date")
    ap.add_argument("branches", nargs='*', default=(), help="Branch name to unpublish (defaults to current)")
    pargs = ap.parse_args(args)

    current_branch = self._current_branch()
    branches = []
    if pargs.merged:
      candidates = [b.strip() for b in self._git("branch", "--merged", "master").split()]
      candidates.remove("master")
      if candidates:
        print("Branches to be removed")
        for c in candidates:
          print("  " + c)
        ok = input("Ok [y/n]? ")
        if ok != "y": return
    elif pargs.branches:
      branches = pargs.branches
    else:
      branches = [current_branch]

    for branch in branches:
      if branch == "master":
        print("Cowardly refusing to delete master")
      if branch == current_branch:
        self._git("checkout", "master")
      print(self._git("push", "origin", ":{}".format(branch)))
      if pargs.rm:
        print(self._git("branch", "-d", branch))

  def _git(self, *args) -> sh.RunningCommand:
    baked = git.bake(*args)
    # It would be awesome to print in grey here if output is a TTY
    print(baked)
    return baked()

  def _current_branch(self) -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").strip()

def main(argv):
  flow = GFlow()
  bin_name = Path(argv[0]).name
  method = flow.method(bin_name)
  args = argv[1:]

  if method is None and len(argv) > 1:
    method = flow.method(argv[1])
    args = argv[2:]

  if method is None:
    print("Usage: {} action [opts...]")
    sys.exit(1)

  method(*args)

if __name__ == '__main__':
  main(sys.argv)
