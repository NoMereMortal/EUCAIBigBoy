use anyhow::Result;
use dialoguer::{Confirm, Input, Select};

pub fn confirm(message: &str, default: bool) -> Result<bool> {
    Ok(Confirm::new()
        .with_prompt(message)
        .default(default)
        .interact()?)
}

pub fn confirm_destructive(action: &str, target: &str) -> Result<bool> {
    let message = format!(
        "Are you sure you want to {} '{}'? This action cannot be undone.",
        action, target
    );

    Ok(Confirm::new()
        .with_prompt(message)
        .default(false)
        .interact()?)
}

pub fn input_string(prompt: &str, default: Option<&str>) -> Result<String> {
    let mut input = Input::new().with_prompt(prompt);

    if let Some(default_value) = default {
        input = input.default(default_value.to_string());
    }

    Ok(input.interact_text()?)
}

pub fn select_option(prompt: &str, options: &[&str]) -> Result<usize> {
    Ok(Select::new()
        .with_prompt(prompt)
        .items(options)
        .interact()?)
}

pub fn select_option_with_default(prompt: &str, options: &[&str], default: usize) -> Result<usize> {
    Ok(Select::new()
        .with_prompt(prompt)
        .items(options)
        .default(default)
        .interact()?)
}
