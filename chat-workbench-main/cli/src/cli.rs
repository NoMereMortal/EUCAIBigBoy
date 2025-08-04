use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "cwb")]
#[command(version = env!("CARGO_PKG_VERSION"))]
#[command(about = "Chat Workbench - Full-stack deployment and development CLI")]
#[command(long_about = None)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,

    /// Environment to use (dev, staging, prod)
    #[arg(long, short, global = true)]
    pub env: Option<String>,

    /// Enable verbose output
    #[arg(long, short, global = true)]
    pub verbose: bool,

    /// Perform a dry run without executing commands
    #[arg(long, global = true)]
    pub dry_run: bool,

    /// Force operation without confirmation prompts
    #[arg(long, short, global = true)]
    pub force: bool,

    /// Configuration file path
    #[arg(long, global = true)]
    pub config: Option<String>,
}

#[derive(Subcommand, Clone)]
pub enum Commands {
    /// Deployment management commands
    #[command(subcommand)]
    Deploy(DeployCommands),

    /// Development workflow commands
    #[command(subcommand)]
    Dev(DevCommands),

    /// Database operations
    #[command(subcommand)]
    Db(DbCommands),

    /// Dependency management
    #[command(subcommand)]
    Deps(DepsCommands),

    /// File and artifact cleanup
    #[command(subcommand)]
    Clean(CleanCommands),

    /// Security and compliance
    #[command(subcommand)]
    Security(SecurityCommands),

    /// Monitoring and debugging
    #[command(subcommand)]
    Monitor(MonitorCommands),

    /// CI/CD operations
    #[command(subcommand)]
    Ci(CiCommands),

    /// Show configuration
    Config {
        #[command(subcommand)]
        action: Option<ConfigCommands>,
    },

    /// Diagnose setup issues
    Doctor,

    /// Show version information
    Version,
}

#[derive(Subcommand, Clone)]
pub enum DeployCommands {
    /// Deploy stack(s)
    Deploy {
        /// Stack name to deploy (optional)
        stack: Option<String>,

        /// Deploy all stacks
        #[arg(long)]
        all: bool,
    },

    /// Destroy stack(s)
    Destroy {
        /// Stack name to destroy (optional)
        stack: Option<String>,

        /// Destroy all stacks
        #[arg(long)]
        all: bool,
    },

    /// Show deployment status
    Status,

    /// Show deployment diff
    Diff {
        /// Stack name
        stack: Option<String>,
    },

    /// Bootstrap CDK environment
    Bootstrap {
        /// AWS region
        #[arg(long)]
        region: Option<String>,
    },

    /// Rollback deployment
    Rollback {
        /// Stack name
        stack: String,
    },

    /// Clean deployment artifacts
    Clean,
}

#[derive(Subcommand, Clone)]
pub enum DevCommands {
    /// Start local development server
    Start {
        /// Component to start (backend, frontend, all)
        #[arg(default_value = "all")]
        component: String,

        /// Port for backend
        #[arg(long)]
        backend_port: Option<u16>,

        /// Port for frontend
        #[arg(long)]
        frontend_port: Option<u16>,
    },

    /// Build component(s)
    Build {
        /// Component to build
        #[arg(default_value = "all")]
        component: String,

        /// Build in release mode
        #[arg(long)]
        release: bool,
    },

    /// Run tests
    Test {
        /// Component to test
        #[arg(default_value = "all")]
        component: String,

        /// Generate coverage report
        #[arg(long)]
        coverage: bool,

        /// Run only specific test
        #[arg(long)]
        test: Option<String>,
    },

    /// Run linting
    Lint {
        /// Component to lint
        #[arg(default_value = "all")]
        component: String,

        /// Auto-fix issues
        #[arg(long)]
        fix: bool,
    },

    /// Format code
    Format {
        /// Component to format
        #[arg(default_value = "all")]
        component: String,
    },

    /// Run type checking
    Typecheck {
        /// Component to check
        #[arg(default_value = "all")]
        component: String,
    },

    /// Run pre-commit hooks
    PreCommit,
}


#[derive(Subcommand, Clone)]
pub enum DbCommands {
    /// Run database migrations
    Migrate,

    /// Seed test data
    Seed {
        /// Seed file
        #[arg(long)]
        file: Option<String>,
    },

    /// Backup database
    Backup {
        /// Backup name
        #[arg(long)]
        name: Option<String>,
    },

    /// Restore database
    Restore {
        /// Backup name
        backup: String,
    },
}

#[derive(Subcommand, Clone)]
pub enum DepsCommands {
    /// Install dependencies
    Install {
        /// Component
        #[arg(default_value = "all")]
        component: String,
    },

    /// Update dependencies
    Update {
        /// Component
        #[arg(default_value = "all")]
        component: String,
    },

    /// Show outdated packages
    Outdated {
        /// Component
        #[arg(default_value = "all")]
        component: String,
    },

    /// Sync all dependencies
    Sync,
}

#[derive(Subcommand, Clone)]
pub enum CleanCommands {
    /// Clean build caches
    Cache,

    /// Clean log files
    Logs,

    /// Clean build artifacts
    Artifacts,

    /// Clean everything
    All,
}

#[derive(Subcommand, Clone)]
pub enum SecurityCommands {
    /// Run security scan
    Scan {
        /// Component
        #[arg(default_value = "all")]
        component: String,
    },

    /// Rotate secrets
    Rotate {
        /// Secret name
        secret: Option<String>,

        /// Environment
        #[arg(long, short)]
        env: Option<String>,
    },

    /// Security audit report
    Audit {
        /// Environment
        #[arg(long, short)]
        env: Option<String>,
    },
}

#[derive(Subcommand, Clone)]
pub enum MonitorCommands {
    /// View application logs
    Logs {
        /// Service name
        service: Option<String>,

        /// Follow logs
        #[arg(long, short)]
        follow: bool,

        /// Number of lines to show
        #[arg(long, short)]
        lines: Option<usize>,

        /// Environment
        #[arg(long, short)]
        env: Option<String>,
    },

    /// Check service health
    Health {
        /// Environment
        #[arg(long, short)]
        env: Option<String>,
    },

    /// Show performance metrics
    Metrics {
        /// Environment
        #[arg(long, short)]
        env: Option<String>,

        /// Time period
        #[arg(long, default_value = "1h")]
        period: String,
    },
}

#[derive(Subcommand, Clone)]
pub enum CiCommands {
    /// Setup CI/CD pipeline
    Setup,

    /// Validate CI configuration
    Validate,

    /// Create release
    Release {
        /// Version number
        version: Option<String>,
    },
}

#[derive(Subcommand, Clone)]
pub enum ConfigCommands {
    /// Show configuration
    Show,

    /// Set configuration value
    Set {
        /// Configuration key
        key: String,

        /// Configuration value
        value: String,
    },

    /// Get configuration value
    Get {
        /// Configuration key
        key: String,
    },
}
