//! Spawning and supervising the `lemmata-server` sidecar (contract: wiki/sprints/S03/S03-brief.md).

use crate::recent::{self, Project};
use crate::state::{self, ErrorInfo};
use serde_json::Value;
use std::collections::VecDeque;
use std::time::Duration;
use tauri::AppHandle;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// A one-file PyInstaller binary unpacks itself on first start and then scans the project.
const READY_TIMEOUT: Duration = Duration::from_secs(120);
const STDERR_TAIL: usize = 40;

#[derive(Clone, Debug)]
pub enum Target {
    Project(Project),
    Sample { reset: bool },
}

/// PATH for child processes. A Finder-launched app gets a minimal PATH, so add Homebrew locations.
pub fn child_path() -> String {
    let base = std::env::var("PATH").unwrap_or_else(|_| "/usr/bin:/bin:/usr/sbin:/sbin".into());
    if cfg!(target_os = "macos") {
        format!("{base}:/opt/homebrew/bin:/usr/local/bin")
    } else {
        base
    }
}

/// Ask the sidecar to stop (SIGTERM), then force-kill it if it is still alive after a grace period.
pub fn terminate(child: CommandChild) {
    #[cfg(unix)]
    {
        // SAFETY: plain signal to a pid we spawned.
        unsafe {
            libc::kill(child.pid() as i32, libc::SIGTERM);
        }
        tauri::async_runtime::spawn(async move {
            tokio::time::sleep(Duration::from_secs(3)).await;
            let _ = child.kill();
        });
    }
    #[cfg(not(unix))]
    {
        let _ = child.kill();
    }
}

/// Used at quit: the async runtime may be going away, so block briefly instead.
pub fn terminate_blocking(child: CommandChild) {
    #[cfg(unix)]
    {
        // SAFETY: plain signal to a pid we spawned.
        unsafe {
            libc::kill(child.pid() as i32, libc::SIGTERM);
        }
        std::thread::sleep(Duration::from_millis(300));
    }
    let _ = child.kill();
}

fn build_args(app: &AppHandle, target: &Target) -> Result<Vec<String>, ErrorInfo> {
    let pid = std::process::id().to_string();
    let common = ["--port", "0", "--no-open", "--ready-json", "--parent-pid", &pid, "--watch"];
    let mut a: Vec<String> = Vec::new();
    match target {
        Target::Project(p) => {
            a.extend(["open".into(), p.path.clone()]);
            if let Some(x) = &p.paper {
                a.extend(["--paper".into(), x.clone()]);
            }
            if let Some(x) = &p.code {
                a.extend(["--code".into(), x.clone()]);
            }
        }
        Target::Sample { reset } => {
            let dir = recent::app_data(app)
                .map(|d| d.join("sample"))
                .ok_or_else(|| ErrorInfo::new("no_app_data", "Lemmata could not find its data folder.", ""))?;
            a.extend(["demo".into(), "--dir".into(), dir.to_string_lossy().into_owned()]);
            if !reset {
                a.push("--keep".into());
            }
        }
    }
    a.extend(common.iter().map(|s| s.to_string()));
    Ok(a)
}

/// Start the sidecar for `target`, wait for its ready line, then navigate the window to it.
/// Progress and errors are reported through `SessionState` plus the `state-changed` event.
pub async fn open(app: AppHandle, target: Target) {
    // Kill the previous sidecar first and show the launcher in "opening" state.
    let (gen, previous) = state::begin_open(&app, &target);
    if let Some(c) = previous {
        terminate(c);
    }
    state::show_launcher(&app);
    state::notify(&app);

    match start(&app, &target, gen).await {
        Ok(info) => {
            if !state::finish_open(&app, gen, &info) {
                return; // superseded by a newer open
            }
            if let Target::Project(p) = &target {
                let mut p = p.clone();
                p.name = info.project.clone();
                recent::push(&app, p);
            }
            state::navigate_to(&app, &info.url, &format!("Lemmata \u{2014} {}", info.project));
            state::notify(&app);
        }
        Err(e) => {
            state::fail_open(&app, gen, e);
            state::notify(&app);
        }
    }
}

struct Ready {
    url: String,
    project: String,
    root: String,
}

async fn start(app: &AppHandle, target: &Target, gen: u64) -> Result<state::Opened, ErrorInfo> {
    if let Target::Project(p) = target {
        if !std::path::Path::new(&p.path).exists() {
            return Err(ErrorInfo::new("not_found", &format!("The folder {} no longer exists.", p.path), ""));
        }
    }
    let args = build_args(app, target)?;
    let cmd = app
        .shell()
        .sidecar("lemmata-server")
        .map_err(|e| ErrorInfo::new("spawn_failed", "Lemmata's analysis engine is missing from this app.", &e.to_string()))?
        .env("PATH", child_path())
        .env("PYTHONUNBUFFERED", "1")
        .args(args);
    let (mut rx, child) = cmd
        .spawn()
        .map_err(|e| ErrorInfo::new("spawn_failed", "Lemmata's analysis engine could not be started.", &e.to_string()))?;
    let pid = child.pid();
    state::set_child(app, gen, child);

    let (tx, rx_ready) = tokio::sync::oneshot::channel::<Result<Ready, ErrorInfo>>();
    let app2 = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut tx = Some(tx);
        let mut tail: VecDeque<String> = VecDeque::new();
        let mut ready = false;
        while let Some(ev) = rx.recv().await {
            match ev {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes).trim().to_string();
                    if line.is_empty() {
                        continue;
                    }
                    match serde_json::from_str::<Value>(&line) {
                        Ok(v) if v["event"] == "ready" => {
                            let s = |k: &str| v[k].as_str().unwrap_or("").to_string();
                            ready = true;
                            if let Some(t) = tx.take() {
                                let _ = t.send(Ok(Ready { url: s("url"), project: s("project"), root: s("root") }));
                            }
                        }
                        Ok(v) if v["event"] == "error" => {
                            // Give stderr a moment to arrive so the details are complete.
                            tokio::time::sleep(Duration::from_millis(150)).await;
                            while let Some(CommandEvent::Stderr(b)) = rx.try_recv().ok() {
                                push_tail(&mut tail, &b);
                            }
                            let code = v["code"].as_str().unwrap_or("error");
                            let msg = v["message"].as_str().unwrap_or("The analysis engine reported an error.");
                            if let Some(t) = tx.take() {
                                let _ = t.send(Err(ErrorInfo::new(code, msg, &join_tail(&tail))));
                            }
                        }
                        _ => push_tail(&mut tail, line.as_bytes()), // unexpected stdout: keep for details
                    }
                }
                CommandEvent::Stderr(b) => push_tail(&mut tail, &b),
                CommandEvent::Error(e) => push_tail(&mut tail, e.as_bytes()),
                CommandEvent::Terminated(p) => {
                    let msg = format!("Lemmata's analysis engine stopped (exit code {}).", p.code.map(|c| c.to_string()).unwrap_or_else(|| "unknown".into()));
                    let err = ErrorInfo::new("server_stopped", &msg, &join_tail(&tail));
                    if let Some(t) = tx.take() {
                        let _ = t.send(Err(err));
                    } else if ready {
                        state::server_died(&app2, gen, err);
                    }
                    break;
                }
                _ => {}
            }
        }
        // Channel closed without a Terminated event.
        if let Some(t) = tx.take() {
            let _ = t.send(Err(ErrorInfo::new("server_stopped", "Lemmata's analysis engine stopped.", &join_tail(&tail))));
        }
    });

    match tokio::time::timeout(READY_TIMEOUT, rx_ready).await {
        Ok(Ok(Ok(r))) => Ok(state::Opened { url: r.url, project: r.project, root: r.root, pid }),
        Ok(Ok(Err(e))) => Err(e),
        Ok(Err(_)) => Err(ErrorInfo::new("server_stopped", "Lemmata's analysis engine stopped.", "")),
        Err(_) => {
            state::kill_if_current(app, gen);
            Err(ErrorInfo::new("timeout", "Opening the project took longer than two minutes, so Lemmata stopped it.", ""))
        }
    }
}

fn push_tail(tail: &mut VecDeque<String>, bytes: &[u8]) {
    for l in String::from_utf8_lossy(bytes).lines() {
        if tail.len() == STDERR_TAIL {
            tail.pop_front();
        }
        tail.push_back(l.to_string());
    }
}

fn join_tail(tail: &VecDeque<String>) -> String {
    tail.iter().cloned().collect::<Vec<_>>().join("\n")
}
