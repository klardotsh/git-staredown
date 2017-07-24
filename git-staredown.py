#!/usr/bin/env python3

import argparse
import enum
import os
import sys

import github3
import pygit2


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


def format_discovered_pr(pull, quietness, prefix=None):
    # TODO implement the other output levels
    return '{prefix}#{num} @{user} {title}'.format(
        prefix=prefix if prefix else '',
        num=pull.number, user=pull.user, title=pull.title,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='Relative path of file to track history of (ex. "README")')
    # parser.add_argument(
    #     '--follow', dest='follow', action='store_true',
    #     help=(
    #         'Follow file through its rename history. Defaults to value of '
    #         '`git config log.follow`'
    #     ),
    # )
    # parser.add_argument(
    #     '--quiet', '-q', action='count', dest='quiet', default=0,
    #     help='Ignored for now, will later control verbosity',
    # )
    parser.add_argument(
        '--repo', '-r', dest='repo', default=os.getcwd(),
        help='Override path to repository (defaults to current working directory)',
    )

    args = parser.parse_args()
    args.quiet = Quietness.ONE_LINE_SUMMARY

    repo = pygit2.Repository(args.repo)

    # if not args.follow:
    #     try:
    #         args.follow = repo.config.get_bool('log.follow')
    #     except KeyError:
    #         args.follow = False

    try:
        username = repo.config['staredown.githubusername']
        password = repo.config['staredown.githubpassword']
    except KeyError:
        panic(
            'Please add GitHub username+password to Git config!\n\n'
            '$ git config --global staredown.githubusername myemail@somewhere.com\n'
            '$ git config --global staredown.githubpassword <API TOKEN>'
        )

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
            shas = {x.sha for x in pull.iter_commits()} | {pull.merge_commit_sha}

            if shas.intersection(commit_ids):
                print(format_discovered_pr(
                    pull, args.quiet,
                    prefix=gh_remote if len(github_remotes) > 1 else None,
                ))


if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        sys.exit(255)
