#!/usr/bin/env python3

import argparse
import enum
import os
import subprocess
import sys

import github3
import pygit2
from colorama import init as colorama_init
from colorama import Fore

MAX_USERNAME_LENGTH = 10
SHORT_SHA_LENGTH = 7
COLOR_MAPPINGS = {
    'COLOR_SHA': Fore.RED,
    'COLOR_REPO': Fore.GREEN,
    'COLOR_AUTHOR': Fore.BLUE,
    'COLOR_DEFAULT': Fore.RESET,
    'COLOR_RESET': Fore.RESET,
}

ERR_NO_GH_CREDS = '''
Please add GitHub username+password to Git config!
$ git config --global staredown.githubusername myemail@somewhere.com
$ git config --global staredown.githubpassword <API TOKEN>
# OR
$ git config --global staredown.githubpasswordcmd <COMMAND>
'''.strip()


# Rather than "Verbosity", because we'll default to being chatty
# and leave it to the caller to ask us to pipe down (for scripting purposes)
class Quietness(enum.IntEnum):
    INTERACTIVE = 0
    TWO_LINE_SUMMARY = 1
    ONE_LINE_SUMMARY = 2
    NUM_ONLY = 3


def panic(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)
    sys.exit(200)


def extract_github_remotes(repo):
    return [
        path.replace('.git', '')
        for server, path in (
            rem.url.split(':')
            for rem in repo.remotes
        )
        if 'github' in server
    ]


def walk_tree_until_file(repo, filename, tree):
    tree_ptr = tree

    to_split = filename

    while to_split:
        path, to_split = os.path.split(to_split)

        if not path:
            try:
                return tree_ptr[to_split]
            except KeyError:
                return None

        try:
            tree_ptr = repo[tree[path].oid]
        except KeyError:
            return None


def all_commits_where_file_changed(repo, filename, cur_commit, commit_ids=None, parents_seen=None):
    if commit_ids is None:
        commit_ids = set()

    if parents_seen is None:
        parents_seen = set()

    parents_seen.add(cur_commit.id)

    file_entry = walk_tree_until_file(repo, filename, cur_commit.tree)

    if file_entry is not None:
        file_in_parents = [
            walk_tree_until_file(repo, filename, parent.tree)
            for parent in cur_commit.parents
        ]

        # None in file_in_parents represents a brand new file
        file_changed = None in file_in_parents or any(
            file_entry.oid != getattr(f, 'oid', None)
            for f in file_in_parents
        )

        if file_changed or not cur_commit.parents:
            commit_ids.add(cur_commit.oid.hex)

    for parent in cur_commit.parents:
        if parent.id not in parents_seen:
            all_commits_where_file_changed(
                repo, filename, parent,
                commit_ids=commit_ids,
                parents_seen=parents_seen,
            )

    return commit_ids


def format_discovered_pr(repo_name, shas, pull, args):
    # TODO implement the other output levels
    for sha in shas:
        username = str(pull.user)

        if len(username) > MAX_USERNAME_LENGTH:
            username = '{}{}'.format(
                username[:MAX_USERNAME_LENGTH - 1],
                '…',
            )

        yield (
            '{COLOR_SHA}{sha} {COLOR_REPO}{repo}#{num:<4d} '
            '{COLOR_AUTHOR}@{user:10s}{COLOR_RESET} {title}'
        ).format(
            sha=sha[:SHORT_SHA_LENGTH], repo=repo_name, num=pull.number,
            user=str(pull.user), title=pull.title,
            **(COLOR_MAPPINGS if not args.nocolor else {x: '' for x in COLOR_MAPPINGS}),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='Relative path of file to track history of (ex. "README")')
    parser.add_argument(
        '--repo', '-r', dest='repo', default=os.getcwd(),
        help='Override path to repository (defaults to current working directory)',
    )
    parser.add_argument(
        '--no-color', dest='nocolor', action='store_true',
        help='Do not use colors (default if output is redirected)',
    )

    args = parser.parse_args()
    args.quiet = Quietness.ONE_LINE_SUMMARY

    if not args.nocolor:
        colorama_init(autoreset=True)

    repo = pygit2.Repository(args.repo)

    password = None
    password_command = None

    try:
        username = repo.config['staredown.githubusername']
        try:
            password = repo.config['staredown.githubpassword']
        except KeyError:
            password_command = repo.config['staredown.githubpasswordcmd']
    except KeyError:
        panic(ERR_NO_GH_CREDS)

    if not password and password_command:
        try:
            pw = subprocess.run(password_command, shell=True, check=True, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            panic('Did not receive GitHub password from `githubpasswordcmd`!')

        gh = github3.login(username, pw.stdout.strip())
    else:
        gh = github3.login(username, password)

    github_remotes = extract_github_remotes(repo)

    if not github_remotes:
        panic('No GitHub remotes seem to be configured for specified git repository {}'.format(args.repo))

    head_commit = repo.head.get_object()
    commit_ids = all_commits_where_file_changed(repo, args.filename, head_commit)

    if not commit_ids:
        panic('File has never existed in visible repository history (starting from HEAD)')

    for gh_remote in github_remotes:
        gh_repo = gh.repository(*gh_remote.split('/'))

        for pull in gh_repo.iter_pulls(state='all'):
            # Sometimes commit IDs change when getting pulled into the repo,
            # so we need to scan for the PR's resulting commit sha as well
            shas = {x.sha for x in pull.iter_commits()}
            shas.add(pull.merge_commit_sha)

            found_shas = shas.intersection(commit_ids)

            if found_shas:
                for line in format_discovered_pr(gh_remote, found_shas, pull, args):
                    print(line)


if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        sys.exit(255)
