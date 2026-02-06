//! Apply global MCP configs to current project (CLI-004).

use std::process::Command;

use tracing::{info, warn};

use crate::error::Error;
use crate::global_config::GlobalConfig;

/// Run the apply command.
pub fn run() -> Result<(), Error> {
    // Load global config
    if !GlobalConfig::exists() {
        println!("Global config not found. Run 'sqrl config' first.");
        return Ok(());
    }

    let config = GlobalConfig::load()?;
    let mcps = GlobalConfig::list_mcps()?;

    if mcps.is_empty() {
        println!("No MCP configs found in ~/.sqrl/mcps/");
        return Ok(());
    }

    println!("Applying MCP configs...");

    let mut applied_claude = Vec::new();

    // Apply to Claude Code if enabled
    if config.tools.claude_code {
        for mcp in &mcps {
            if apply_to_claude_code(mcp)? {
                applied_claude.push(mcp.name.clone());
            }
        }
    }

    // Git hooks are installed separately by sqrl init
    if config.tools.git {
        info!("Git hooks are installed by 'sqrl init'");
    }

    // Print summary
    println!();
    println!("Applied MCP configs:");
    if !applied_claude.is_empty() {
        println!("  Claude Code: {}", applied_claude.join(", "));
    }
    if config.tools.git {
        println!("  Git: (hooks managed by sqrl init)");
    }

    Ok(())
}

/// Apply an MCP config to Claude Code.
fn apply_to_claude_code(mcp: &crate::global_config::McpConfig) -> Result<bool, Error> {
    // Check if claude CLI exists
    let which = Command::new("which").arg("claude").output();
    if which.is_err() || !which.unwrap().status.success() {
        warn!("Claude Code CLI not found, skipping");
        return Ok(false);
    }

    // Build command args
    let mut args = vec![
        "mcp".to_string(),
        "add".to_string(),
        mcp.name.clone(),
        "-s".to_string(),
        mcp.scope.clone(),
        "--".to_string(),
        mcp.command.clone(),
    ];
    args.extend(mcp.args.clone());

    let output = Command::new("claude").args(&args).output()?;

    if output.status.success() {
        info!(name = %mcp.name, "Registered MCP with Claude Code");
        println!("  + {} (Claude Code)", mcp.name);
        Ok(true)
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        // Check if already exists (not a failure)
        if stderr.contains("already exists") {
            info!(name = %mcp.name, "MCP already registered with Claude Code");
            println!("  = {} (already registered)", mcp.name);
            Ok(true)
        } else {
            warn!(name = %mcp.name, stderr = %stderr, "Failed to register MCP");
            println!("  ! {} (failed: {})", mcp.name, stderr.trim());
            Ok(false)
        }
    }
}
