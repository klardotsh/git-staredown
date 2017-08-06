extern crate clap;
extern crate github_rs;
extern crate git2;
extern crate subprocess;

use std::collections::HashSet;
use std::path::PathBuf;
use clap::{App, Arg};
use git2::{Commit, Oid, Repository};
use github_rs::client::Github;

const APPLICATION: &str = "git-staredown";

struct FileChangeTracker<'repo, 'path> {
    filename: &'path PathBuf,
    repo: &'repo Repository,
    commits_to_test: Vec<Commit<'repo>>,
    known_commits_to_test: HashSet<Oid>,
    found_ids: HashSet<Oid>,
}

impl <'repo, 'path> FileChangeTracker<'repo, 'path> {
    fn new(repo: &'repo Repository, filename: &'path PathBuf) -> FileChangeTracker<'repo, 'path> {
        let head_oid = repo.head().unwrap().target().unwrap();
        let head_commit = repo.find_commit(head_oid).unwrap();
        let mut known_commits_to_test = HashSet::new();
        known_commits_to_test.insert(head_commit.id());

        FileChangeTracker {
            filename: filename,
            repo: repo,
            commits_to_test: vec![head_commit],
            found_ids: HashSet::new(),
            known_commits_to_test: known_commits_to_test,
        }
    }
}

impl <'repo, 'path> Iterator for FileChangeTracker<'repo, 'path> {
    type Item = Commit<'repo>;

    fn next(&mut self) -> Option<Commit<'repo>> {
        let tested_commit: Commit = match self.commits_to_test.pop() {
            Some(c) => c,
            None => {
                return None;
            }
        };

        let tree = self.repo.find_tree(tested_commit.tree_id()).unwrap();
        let file_in_commit = match tree.get_path(&self.filename) {
            Ok(p) => p,
            Err(_) => {
                return self.next();
            }
        };

        if self.found_ids.contains(&file_in_commit.id()) {
            return self.next();
        }

        if tested_commit.parents().len() == 0 {
            return Some(tested_commit);
        }

        let mapped = tested_commit.parents().map(|commit| {
            let commit_id: Oid = commit.id();
            let tree_id = commit.tree_id();

            if !self.known_commits_to_test.contains(&commit_id) {
                self.known_commits_to_test.insert(commit_id);
                self.commits_to_test.push(commit);
            }

            let parent_tree = self.repo.find_tree(tree_id).unwrap();

            match parent_tree.get_path(&self.filename) {
                Ok(p) => p.id() != file_in_commit.id(),
                // Path did not exist in parent, so it was clearly added here
                Err(_) => true
            }
        })
        .any(|x| x);

        if mapped {
            Some(tested_commit)
        } else {
            self.next()
        }
    }
}

trait TrackFileChanges<'repo> {
    fn all_commits_where_file_changed(&self, path: &'repo PathBuf) -> Vec<Commit>;
    fn all_commit_ids_where_file_changed(&self, path: &'repo PathBuf) -> HashSet<Oid>;
}

impl<'repo> TrackFileChanges<'repo> for Repository {
    fn all_commits_where_file_changed(&self, path: &'repo PathBuf) -> Vec<Commit> {
        let commits_where_changed = FileChangeTracker::new(self, path);
        let mut all_commits: Vec<Commit> = commits_where_changed.collect();
        all_commits.sort_by(|a, b| b.time().cmp(&a.time()));
        all_commits
    }

    fn all_commit_ids_where_file_changed(&self, path: &'repo PathBuf) -> HashSet<Oid> {
        let commits_where_changed = FileChangeTracker::new(self, path);
        let mut all_commits: HashSet<Oid> = HashSet::new();

        for commit in commits_where_changed {
            all_commits.insert(commit.id());
        }

        all_commits
    }
}

fn main() {
    let matches = App::new(APPLICATION)
        .about("A utility to find which GitHub pull requests have been associated with a file")
        .arg(Arg::with_name("repo")
             .short("r")
             .long("repo")
             .default_value("./")
             .help("Override path to repository"))
        .arg(Arg::with_name("filename")
             .required(true)
             .index(1)
             .help("File to analyze"))
        .get_matches();

    let repo_path = matches.value_of("repo").unwrap();
    let repo = Repository::open(repo_path).unwrap();
    let repo_config = repo.config().unwrap();

    let gh: Github = match repo_config.get_string("staredown.githubpasswordcmd") {
        Ok(s) => {
            let mut cmd_output = String::new();
            let mut cmd = subprocess::Exec::shell(s).stream_stdout().unwrap();
            cmd.read_to_string(&mut cmd_output).unwrap();

            let cmd_output_len = cmd_output.len();
            cmd_output.truncate(cmd_output_len - 1);

            Github::new(cmd_output).unwrap()
        },
        Err(_) => match repo_config.get_string("staredown.githubpassword") {
            Ok(s) => Github::new(s).unwrap(),
            Err(_) => {
                eprintln!("Please configure an API Token (or command to read it), see --help");
                std::process::exit(255);
            }
        }
    };

    let pathname = std::path::PathBuf::from(matches.value_of("filename").unwrap());
    let changed_commit_ids: HashSet<Oid> = repo.all_commit_ids_where_file_changed(&pathname);

    let pulls = gh.get().repos().owner("sdispater").repo("pendulum").pulls().execute();

    match pulls {
        Ok((_, _, json)) => {
            if let Some(json) = json {
                println!("{:?}", json);
            }
        },
        Err(_) => {},
    }
}
