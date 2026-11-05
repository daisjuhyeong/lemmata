//! git availability check. Lemmata reads project history with git.

use crate::sidecar::child_path;
use crate::state::GitStatus;
use std::process::{Command, Stdio};

pub fn check() -> GitStatus {
    // On a Mac without Apple's Command Line Tools, /usr/bin/git is a stub that pops up
    // the installer. Ask xcode-select first so that merely launching Lemmata never does that.
    if cfg!(target_os = "macos") && !has_homebrew_git() {
        let clt = Command::new("xcode-select")
            .arg("-p")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if !clt {
            return GitStatus { ok: false, version: String::new() };
        }
    }
    match Command::new("git").arg("--version").env("PATH", child_path()).output() {
        Ok(o) if o.status.success() => GitStatus {
            ok: true,
            version: String::from_utf8_lossy(&o.stdout).trim().to_string(),
        },
        _ => GitStatus { ok: false, version: String::new() },
    }
}

fn has_homebrew_git() -> bool {
    ["/opt/homebrew/bin/git", "/usr/local/bin/git"].iter().any(|p| std::path::Path::new(p).exists())
}

/// Opens Apple's Command Line Tools installer.
pub fn install() {
    let _ = Command::new("xcode-select").arg("--install").spawn();
}
