#!/usr/bin/env python3
# Requires Python 3.6 or later
r"""
Alex's GitHub workflow scripts.

These scripts automate complicated or multiple-step git commands to implement the workflow
of working on branches which are continually rebased, reviewed as a GitHub pull request, and
landed by fast-forwarding main.

Typical usage:
  $ git checkout -b mybranch
  ...work work work...
  $ git commit -a
  $ # pull main from origin and rebase this branch against it:
  $ gflow up
  $ # send a pull request for review
  $ gflow pr
  ... more work ...
  $ # fetch yet more changes and publish updated PR
  $ git commit -a
  $ gflow up
  $ gflow publish
  $ # LGTM, let's land it
  $ gflow land


Upcoming features fixes:
- add --help option to describe commands
- add squash option to land
- add delete branch/s option to land
- count the diff stat size and append a description to PR title
- add commands for chaining a rebase through branches
- add "rm" command to delete remote+local branch
- cleanup origin: "git branch -r --merged main | grep anorth | sed 's/origin\///'  | xargs -n 1 git push --delete origin"
"""

import re
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable, Optional
from subprocess import CalledProcessError


# Matches an origin URI and extracts project and repo name, e.g. "git@github.com:{org}/{repo}.git"
_ORIGIN_PATTERN = re.compile(r'[\w.@-]+:([\w.-]+)/([\w.-]+)(\.git)?')


def main(argv):
  flow = GFlow()

  # Check if argv[0] matches the name of a command, such as when this file is symlinked in a bin
  # directory as "up", "publish", "land" etc.
  # Otherwise, the command name is the first argument.
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
    if e.stderr:
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

  def do_up(self, *args):
    """Fetches origin/main and rebases a branch."""
    ap = ArgumentParser()
    ap.add_argument("--on", help="Source branch to fetch and rebase on (defaults to main)")
    ap.add_argument("branch", nargs='?', help="Branch name to update (defaults to current)")
    pargs = ap.parse_args(args)

    branch = pargs.branch or self._current_branch()
    on = pargs.on or "main"

    self._git_run("fetch", "origin", "+"+on+":"+on)
    if branch != on:
      self._git_run("rebase", on)

  def do_publish(self, *args):
    """
    Pushes a branch (default: the current branch) to origin, overwriting it unconditionally.
    Refuses to publish main.
    """
    self._no_changes()

    ap = ArgumentParser()
    ap.add_argument("--no-verify", action='store_true', help="Skips pre-push hooks")
    ap.add_argument("source", nargs='?', help="Branch name to publish (defaults to current)")
    pargs = ap.parse_args(args)

    source = pargs.source or self._current_branch()
    if source == 'main' or source == 'master':
      raise FlowError("Refusing to publish main branch, use git push directly.")

    self._publish(source, no_verify=pargs.no_verify)

  def do_unpublish(self, *args):
    """
    Deletes a branch from the origin unconditionally.
    Refuses to delete main.
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
      if branch == "main" or branch == "master":
        print("Refusing to delete main branch")
        continue
      if branch == current_branch:
        self._git_run("checkout", "main")
      self._git_run("push", "origin", "--delete", branch)
      if pargs.rm:
        self._git_run("branch", "-d", branch)

  def do_pr(self, *args):
    """Publishes a branch and opens a pull request in-browser."""
    self._no_changes()

    ap = ArgumentParser()
    ap.add_argument("--on", help="Target branch to compare changes with (defaults to main)")
    ap.add_argument("--no-verify", action='store_true', help="Skips pre-push hooks")
    ap.add_argument("source", nargs='?', help="Branch name to publish (defaults to current)")
    pargs = ap.parse_args(args)

    source = pargs.source or self._current_branch()
    target = pargs.on or "main"
    if source == 'main' or source == 'master':
      raise FlowError("Refusing to publish main branch.")


    origin = self._git_cap("remote", "get-url", "origin")
    org, repo = _ORIGIN_PATTERN.match(origin).group(1, 2)

    self._publish(source, no_verify=pargs.no_verify)

    pr_url="https://github.com/{}/{}/pull/new/{}".format(org, repo, source)
    print(pr_url)
    subprocess.run(["open", pr_url]) # For MacOS


  def do_land(self, *args):
    """Lands changes on origin/main and updates local refs."""
    self._no_changes()

    ap = ArgumentParser()
    ap.add_argument("--on", help="Target branch to land changes on (defaults to main)")
    ap.add_argument("--no-verify", action='store_true', help="Skips pre-push hooks")
    ap.add_argument("source", nargs='?', help="Ref name to land (defaults to HEAD)")
    pargs = ap.parse_args(args)

    source = pargs.source or self._current_branch()
    target = pargs.on or "main"
    extra_args = []
    if pargs.no_verify:
      extra_args.append("--no-verify")

    # Push directly to origin, which will fail if not a fast-forward
    self._git_run("push", "origin", source + ":" + target, *extra_args)
    # Fetch back into the local
    self._git_run("fetch", "origin", "{0}:{0}".format(target))

    # Equivalent, faster, maybe less safe: push the same thing locally
    # self._git_run("push", ".", source + ":" + target, "--no-verify", *extra_args)

  def _current_branch(self) -> str:
    return self._git_cap("rev-parse", "--abbrev-ref", "HEAD").strip()

  def _publish(self, branch, no_verify=False):
    # Fetch origin first in order to push safely regardless of whether remote exists.
    remote_exists = False
    try:
      self._git_run("fetch", "origin", branch)
      remote_exists = True
    except CalledProcessError:
        pass # Branch doesn't exist on remote
    self._push(branch, no_verify=no_verify, set_upstream=(not remote_exists), force=remote_exists)

  def _push(self, branch, no_verify=False, set_upstream=False, force=False):
    extra_args = []
    if no_verify:
      extra_args.append("--no-verify")
    if set_upstream:
      extra_args.append("--set-upstream")
    if force:
      extra_args.append("--force-with-lease")

    return self._git_run("push", "origin", "{0}:{0}".format(branch), *extra_args)

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
    Runs git without capturing output (it goes to this process's stdout/stderr)

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
