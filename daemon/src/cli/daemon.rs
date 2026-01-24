//! Daemon control commands (on/off).

use std::fs;
use std::path::PathBuf;

use tracing::info;

use crate::error::Error;

/// Enable the watcher daemon.
pub async fn enable() -> Result<(), Error> {
    let config_path = get_config_path()?;

    if !config_path.exists() {
        println!("Squirrel not initialized. Run 'sqrl init' first.");
        return Ok(());
    }

    update_watcher_config(&config_path, true)?;
    println!("Watcher enabled.");
    println!("Squirrel will learn from your coding sessions.");

    // TODO: Actually start the watcher daemon process
    // For now, this just updates the config flag

    Ok(())
}

/// Disable the watcher daemon.
pub async fn disable() -> Result<(), Error> {
    let config_path = get_config_path()?;

    if !config_path.exists() {
        println!("Squirrel not initialized. Run 'sqrl init' first.");
        return Ok(());
    }

    update_watcher_config(&config_path, false)?;
    println!("Watcher disabled.");
    println!("Run 'sqrl on' to re-enable.");

    // TODO: Actually stop the watcher daemon process
    // For now, this just updates the config flag

    Ok(())
}

fn get_config_path() -> Result<PathBuf, Error> {
    let project_root = std::env::current_dir()?;
    Ok(project_root.join(".sqrl").join("config.json"))
}

fn update_watcher_config(config_path: &PathBuf, enabled: bool) -> Result<(), Error> {
    let content = fs::read_to_string(config_path)?;
    let mut config: serde_json::Value = serde_json::from_str(&content)?;

    config["watcher_enabled"] = serde_json::Value::Bool(enabled);

    fs::write(config_path, serde_json::to_string_pretty(&config)?)?;
    info!(enabled, "Updated watcher config");

    Ok(())
}
