//! Error types for Squirrel.

use thiserror::Error;

/// Squirrel error type.
#[derive(Error, Debug)]
pub enum Error {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("SQLite error: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("MCP error: {0}")]
    Mcp(String),

    #[error("Home directory not found")]
    HomeDirNotFound,

    #[error("Home directory not found")]
    NoHomeDir,

    #[error("Config not found: {0}")]
    ConfigNotFound(std::path::PathBuf),

    #[error("Global config not found. Run 'sqrl config' first.")]
    GlobalConfigNotFound,

    #[error("MCP config not found: {0}")]
    McpNotFound(String),

    #[error("Config parse error: {0}")]
    ConfigParse(String),
}
