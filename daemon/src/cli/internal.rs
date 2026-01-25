//! Hidden internal commands for git hooks.

use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use regex::Regex;
use tracing::{debug, info};

use crate::config::Config;
use crate::error::Error;
use crate::storage;

/// Record doc debt after a commit (called by post-commit hook).
pub fn docguard_record() -> Result<(), Error> {
    // Find project root (walk up looking for .sqrl)
    let project_root = match find_project_root() {
        Some(path) => path,
        None => {
            debug!("Not a Squirrel project (no .sqrl found)");
            return Ok(());
        }
    };

    // Load config
    let config = match Config::load(&project_root) {
        Ok(c) => c,
        Err(e) => {
            debug!(error = %e, "Failed to load config, skipping doc debt recording");
            return Ok(());
        }
    };

    // Get last commit info
    let (commit_sha, commit_message) = match get_last_commit_info() {
        Some(info) => info,
        None => {
            debug!("Could not get last commit info");
            return Ok(());
        }
    };

    // Check if we already recorded debt for this commit
    if storage::has_doc_debt_for_commit(&project_root, &commit_sha)? {
        debug!(commit = %commit_sha, "Doc debt already recorded for commit");
        return Ok(());
    }

    // Get changed files from last commit
    let changed_files = get_changed_files_from_commit(&commit_sha);
    if changed_files.is_empty() {
        debug!("No changed files in commit");
        return Ok(());
    }

    // Separate code files from doc files
    let (code_files, doc_files): (Vec<_>, Vec<_>) = changed_files
        .iter()
        .partition(|f| !is_doc_file(f, &config.docs.extensions));

    if code_files.is_empty() {
        debug!("No code files changed");
        return Ok(());
    }

    // Detect expected doc updates using all three detection rules
    let mut expected_docs: HashSet<String> = HashSet::new();
    let mut detection_rules: HashSet<String> = HashSet::new();

    // Rule 1: Config mappings (highest priority)
    for mapping in &config.doc_rules.mappings {
        for code_file in &code_files {
            if matches_glob_pattern(code_file, &mapping.code) {
                expected_docs.insert(mapping.doc.clone());
                detection_rules.insert("config".to_string());
            }
        }
    }

    // Rule 2: Reference patterns (e.g., SCHEMA-001 in code)
    for code_file in &code_files {
        let file_path = project_root.join(code_file);
        if let Ok(content) = fs::read_to_string(&file_path) {
            for ref_pattern in &config.doc_rules.reference_patterns {
                if let Ok(re) = Regex::new(&ref_pattern.pattern) {
                    if re.is_match(&content) {
                        expected_docs.insert(ref_pattern.doc.clone());
                        detection_rules.insert("reference".to_string());
                    }
                }
            }
        }
    }

    // Rule 3: Default patterns based on file extension
    for code_file in &code_files {
        if let Some(doc) = get_default_doc_for_file(code_file) {
            expected_docs.insert(doc);
            detection_rules.insert("pattern".to_string());
        }
    }

    // Remove docs that were actually updated in this commit
    for doc_file in &doc_files {
        expected_docs.remove(*doc_file);
    }

    // If no expected docs remain, no debt
    if expected_docs.is_empty() {
        debug!("No doc debt detected");
        return Ok(());
    }

    // Determine primary detection rule
    let detection_rule = if detection_rules.contains("config") {
        "config"
    } else if detection_rules.contains("reference") {
        "reference"
    } else {
        "pattern"
    };

    // Store doc debt
    let code_files_vec: Vec<String> = code_files.into_iter().cloned().collect();
    let expected_docs_vec: Vec<String> = expected_docs.into_iter().collect();

    storage::add_doc_debt(
        &project_root,
        &commit_sha,
        Some(&commit_message),
        &code_files_vec,
        &expected_docs_vec,
        detection_rule,
    )?;

    info!(
        commit = %commit_sha,
        code_files = code_files_vec.len(),
        expected_docs = expected_docs_vec.len(),
        rule = detection_rule,
        "Recorded doc debt"
    );

    Ok(())
}

/// Check doc debt before push (called by pre-push hook).
pub fn docguard_check() -> Result<bool, Error> {
    // Find project root
    let project_root = match find_project_root() {
        Some(path) => path,
        None => {
            // Not a Squirrel project, allow push
            return Ok(true);
        }
    };

    // Load config
    let config = match Config::load(&project_root) {
        Ok(c) => c,
        Err(_) => {
            // Can't load config, allow push
            return Ok(true);
        }
    };

    // Get unresolved doc debt
    let debts = storage::get_unresolved_doc_debt(&project_root)?;

    if debts.is_empty() {
        return Ok(true);
    }

    // Print warning
    eprintln!(
        "⚠️  Doc debt detected! {} commits have unupdated docs:",
        debts.len()
    );
    eprintln!();

    for debt in &debts {
        let short_sha = &debt.commit_sha[..7.min(debt.commit_sha.len())];
        let msg = debt.commit_message.as_deref().unwrap_or("(no message)");
        eprintln!("  {} {}", short_sha, msg);
        eprintln!("    Expected docs: {}", debt.expected_docs.join(", "));
        eprintln!();
    }

    eprintln!("Run 'sqrl status' for details.");

    // Return based on pre_push_block setting
    if config.hooks.pre_push_block {
        eprintln!("Push blocked. Update docs or use 'git push --no-verify' to bypass.");
        Ok(false)
    } else {
        eprintln!("Warning only. Push will continue.");
        Ok(true)
    }
}

/// Find project root by walking up directories looking for .sqrl.
fn find_project_root() -> Option<PathBuf> {
    let cwd = std::env::current_dir().ok()?;
    let mut current = cwd.as_path();

    loop {
        if current.join(".sqrl").exists() {
            return Some(current.to_path_buf());
        }
        current = current.parent()?;
    }
}

/// Get last commit SHA and message.
fn get_last_commit_info() -> Option<(String, String)> {
    let output = Command::new("git")
        .args(["log", "-1", "--format=%H%n%s"])
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut lines = stdout.lines();
    let sha = lines.next()?.to_string();
    let message = lines.next().unwrap_or("").to_string();

    Some((sha, message))
}

/// Get list of files changed in a commit.
fn get_changed_files_from_commit(commit_sha: &str) -> Vec<String> {
    let output = Command::new("git")
        .args([
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit_sha,
        ])
        .output();

    match output {
        Ok(out) if out.status.success() => String::from_utf8_lossy(&out.stdout)
            .lines()
            .map(String::from)
            .collect(),
        _ => vec![],
    }
}

/// Check if a file is a documentation file.
fn is_doc_file(path: &str, doc_extensions: &[String]) -> bool {
    let path = Path::new(path);
    if let Some(ext) = path.extension() {
        let ext_str = ext.to_string_lossy().to_lowercase();
        return doc_extensions.iter().any(|e| e.to_lowercase() == ext_str);
    }
    false
}

/// Check if a path matches a glob pattern.
fn matches_glob_pattern(path: &str, pattern: &str) -> bool {
    // Simple glob matching using the glob crate's pattern
    if let Ok(glob_pattern) = glob::Pattern::new(pattern) {
        return glob_pattern.matches(path);
    }
    false
}

/// Get default doc file for a code file based on extension.
fn get_default_doc_for_file(path: &str) -> Option<String> {
    let path = Path::new(path);
    let ext = path.extension()?.to_string_lossy().to_lowercase();

    // Default mappings based on file extension
    match ext.as_str() {
        "rs" => Some("specs/ARCHITECTURE.md".to_string()),
        "py" => Some("specs/ARCHITECTURE.md".to_string()),
        "ts" | "tsx" | "js" | "jsx" => Some("docs/README.md".to_string()),
        _ => None,
    }
}
