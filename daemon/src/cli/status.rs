//! Show Squirrel status for current project.

use std::path::Path;

use crate::cli::service;
use crate::error::Error;
use crate::storage;

/// Exit codes for status command.
pub mod exit_code {
    pub const OK: i32 = 0;
    pub const NOT_INITIALIZED: i32 = 1;
    pub const DAEMON_NOT_RUNNING: i32 = 2;
}

/// Run the status command.
pub fn run() -> Result<i32, Error> {
    let project_root = std::env::current_dir()?;
    let sqrl_dir = project_root.join(".sqrl");

    println!("Squirrel Status");

    // Project path
    println!("  Project: {}", project_root.display());

    // Check if initialized
    let initialized = sqrl_dir.exists();
    println!("  Initialized: {}", if initialized { "yes" } else { "no" });

    if !initialized {
        println!();
        println!("Run 'sqrl init' to initialize Squirrel for this project.");
        return Ok(exit_code::NOT_INITIALIZED);
    }

    // Check daemon status
    let daemon_running = service::is_running().unwrap_or(false);
    println!(
        "  Daemon: {}",
        if daemon_running { "running" } else { "stopped" }
    );

    // Get memory counts
    let (project_count, user_count) = get_memory_counts(&project_root);
    println!(
        "  Memories: {} project, {} user styles",
        project_count, user_count
    );

    // Last activity (from config file modification time)
    if let Some(last_activity) = get_last_activity(&sqrl_dir) {
        println!("  Last activity: {}", last_activity);
    }

    if !daemon_running {
        println!();
        println!("Run 'sqrl on' to start the daemon.");
        return Ok(exit_code::DAEMON_NOT_RUNNING);
    }

    Ok(exit_code::OK)
}

/// Get memory counts from storage.
fn get_memory_counts(project_root: &Path) -> (usize, usize) {
    let project_count = storage::get_project_memories(project_root)
        .map(|m| m.len())
        .unwrap_or(0);

    let user_count = storage::get_user_styles().map(|s| s.len()).unwrap_or(0);

    (project_count, user_count)
}

/// Get last activity time as human-readable string.
fn get_last_activity(sqrl_dir: &Path) -> Option<String> {
    let db_path = sqrl_dir.join("memory.db");

    let modified = std::fs::metadata(&db_path)
        .ok()
        .and_then(|m| m.modified().ok())?;

    let duration = std::time::SystemTime::now().duration_since(modified).ok()?;

    let secs = duration.as_secs();

    let human = if secs < 60 {
        "just now".to_string()
    } else if secs < 3600 {
        let mins = secs / 60;
        format!("{} minute{} ago", mins, if mins == 1 { "" } else { "s" })
    } else if secs < 86400 {
        let hours = secs / 3600;
        format!("{} hour{} ago", hours, if hours == 1 { "" } else { "s" })
    } else {
        let days = secs / 86400;
        format!("{} day{} ago", days, if days == 1 { "" } else { "s" })
    };

    Some(human)
}
