use colored::Colorize;

pub fn info(message: &str) {
    println!("{} {}", "INFO".blue().bold(), message);
}

pub fn success(message: &str) {
    println!("{} {}", "SUCCESS".green().bold(), message);
}

pub fn warning(message: &str) {
    println!("{} {}", "WARNING".yellow().bold(), message);
}

pub fn error(message: &str) {
    eprintln!("{} {}", "ERROR".red().bold(), message);
}

pub fn debug(message: &str, verbose: bool) {
    if verbose {
        println!("{} {}", "DEBUG".magenta().bold(), message);
    }
}

pub fn step(step: usize, total: usize, message: &str) {
    println!("{} [{}/{}] {}", "STEP".cyan().bold(), step, total, message);
}
