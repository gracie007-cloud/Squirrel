//! Squirrel - local-first memory system for AI coding tools.
//!
//! Single binary. No daemon. No AI. Just storage + git hooks.

use clap::{Parser, Subcommand};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

mod cli;
mod config;
mod error;
mod global_config;
mod mcp;
mod storage;
mod web;

pub use error::Error;
pub use global_config::GlobalConfig;

#[derive(Parser)]
#[command(name = "sqrl")]
#[command(about = "Squirrel - local-first memory system for AI coding tools")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Open web UI for global configuration
    Config {
        /// Don't open browser automatically
        #[arg(long)]
        no_open: bool,
    },

    /// Initialize Squirrel for this project
    Init,

    /// Apply global MCP configs to current project
    Apply,

    /// Remove all Squirrel data from this project
    Goaway {
        /// Skip confirmation prompt
        #[arg(long, short)]
        force: bool,
    },

    /// Show Squirrel status
    Status,

    /// Start MCP server (called by AI tool config, not user)
    #[command(name = "mcp-serve")]
    McpServe,

    /// Internal commands (used by git hooks)
    #[command(hide = true, name = "_internal")]
    Internal {
        #[command(subcommand)]
        cmd: InternalCommands,
    },
}

#[derive(Subcommand)]
enum InternalCommands {
    /// Show diff summary before push (pre-push hook)
    #[command(name = "docguard-check")]
    DocguardCheck,
}

fn main() -> Result<(), Error> {
    // Initialize logging
    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(EnvFilter::from_default_env().add_directive("sqrl=info".parse().unwrap()))
        .init();

    let cli = Cli::parse();

    match cli.command {
        None => {
            use clap::CommandFactory;
            Cli::command().print_help().unwrap();
            println!();
        }
        Some(Commands::Config { no_open }) => {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                if let Err(e) = web::serve(!no_open).await {
                    eprintln!("Error: {}", e);
                    std::process::exit(1);
                }
            });
        }
        Some(Commands::Init) => {
            cli::init::run()?;
        }
        Some(Commands::Apply) => {
            cli::apply::run()?;
        }
        Some(Commands::Goaway { force }) => {
            cli::goaway::run(force)?;
        }
        Some(Commands::Status) => {
            let exit_code = cli::status::run()?;
            if exit_code != 0 {
                std::process::exit(exit_code);
            }
        }
        Some(Commands::McpServe) => {
            mcp::run()?;
        }
        Some(Commands::Internal { cmd }) => match cmd {
            InternalCommands::DocguardCheck => {
                if !cli::internal::docguard_check()? {
                    std::process::exit(1);
                }
            }
        },
    }

    Ok(())
}
