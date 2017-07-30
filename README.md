# git-staredown

`git-staredown` is a tool designed to compliment `git log` and `git blame` for
repositories which use GitHub's Pull Request workflow. It's still in a pretty
early stage of development where ideas are still being fleshed out, but at the
moment, it's able to provide a list of commit IDs (SHAs) and their associated
GitHub Pull Request for a file path (even if that path no longer exists). For
example, if we want to see every PR that has included a modification to the main
file of [pendulum](https://github.com/sdispater/pendulum), we could find out
with:

```
$ » git staredown -r /path/to/clone/of/pendulum pendulum/pendulum.py
89e9ac2 sdispater/pendulum#108  @neonquill  When creating without tzinfo, preserve fold value.
fa40f64 sdispater/pendulum#93   @iv597      Add support for stdlib datetime.timezone instances
9eb456b sdispater/pendulum#64   @kleschenko Add validation for days of the week.
6024485 sdispater/pendulum#61   @gordol     fix carbon refs
afee386 sdispater/pendulum#39   @iv597      Resolve an AttributeError when calling between
a616a02 sdispater/pendulum#30   @jkeyes     Allow pendulum comparison to None.
54dd169 sdispater/pendulum#16   @sdispater  Tz improvements
e8c1d3b sdispater/pendulum#5    @kmario23   replace old style string formatting with new format
d16994d sdispater/pendulum#4    @skia92     minor addition
```

More functionality (including more verbose output levels) is planned!

## Installation

`git-staredown` depends on the `libgit2` system library, and is only supported
on Python 3.x. Python dependencies are listed in `requirements.txt`.

Arch Linux users can install
[git-staredown-git](https://aur.archlinux.org/packages/git-staredown-git) from
the AUR.

## Configuration

`git-staredown` integrates with Git's [built-in configuration
system](https://www.atlassian.com/git/tutorials/setting-up-a-repository/git-config),
meaning you can have global, user-level, and repository-level configs (perhaps
for cases where you have a work and personal GitHub account). Currently, three
config variables are parsed, of which two will be used:

* `staredown.githubusername`, a valid GitHub login (username or email)

* `staredown.githubpassword`, a plaintext GitHub password or (more
	securely), [API
	token](https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/).
	If a token is used, it will require at least `repo:status` and
	`public_repo` scopes. Will be used instead of
	`staredown.githubpasswordcmd` if both are present.

* `staredown.githubpasswordcmd`, anything `git-staredown` can run in a
	subprocess shell and receive your GitHub password or API token over
	STDOUT. **This is the recommended way to store your credentials for
	privacy reasons**. One example, using
	[dotgpg](https://github.com/ConradIrwin/dotgpg), is:

	```ini
	[staredown]
		githubusername = someone@phony.email.here
		githubpasswordcmd = dotgpg cat ~/.private_gpg/github_api_key
	```

## Contributing

Issues and pull requests are welcome from anyone! `git-staredown` is released
under the [MIT License](https://tldrlegal.com/license/mit-license).
