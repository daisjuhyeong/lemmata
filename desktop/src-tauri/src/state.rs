//! Shared session state: which project is open, the sidecar handle, last error.

use crate::recent::{self, Project};
use crate::sidecar::{self, Target};
use serde::Serialize;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, LogicalSize, Manager, Url};
use tauri_plugin_shell::process::CommandChild;

#[derive(Serialize, Clone, Debug)]
pub struct ErrorInfo {
    pub code: String,
    pub message: String,
    /// stderr tail or other technical details (shown under "Show details").
    pub details: String,
}

impl ErrorInfo {
    pub fn new(code: &str, message: &str, details: &str) -> Self {
        ErrorInfo { code: code.into(), message: message.into(), details: details.into() }
    }
}

#[derive(Clone, Debug)]
pub struct Opened {
    pub url: String,
    pub project: String,
    pub root: String,
    #[allow(dead_code)]
    pub pid: u32,
}

pub struct SessionState {
    pub gen: u64,
    pub child: Option<CommandChild>,
    pub current: Option<Opened>,
    pub opening: Option<String>,
    pub error: Option<ErrorInfo>,
    pub on_launcher: bool,
    pub launcher_url: Option<Url>,
    pub zoom: f64,
    pub last_target: Option<Target>,
    /// Last logical size of the project window (remembered across launches).
    pub project_size: Option<(f64, f64)>,
    /// Hub URL the window is showing (S04), if connected to a server.
    pub server: Option<String>,
    /// Hub URL being probed right now.
    pub connecting: Option<String>,
}

pub struct AppState(pub Mutex<SessionState>);

impl AppState {
    pub fn new() -> Self {
        AppState(Mutex::new(SessionState {
            gen: 0,
            child: None,
            current: None,
            opening: None,
            error: None,
            on_launcher: true,
            launcher_url: None,
            zoom: 1.0,
            last_target: None,
            project_size: None,
            server: None,
            connecting: None,
        }))
    }
}

fn with<R>(app: &AppHandle, f: impl FnOnce(&mut SessionState) -> R) -> R {
    let st = app.state::<AppState>();
    let mut g = st.0.lock().unwrap_or_else(|e| e.into_inner());
    f(&mut g)
}

pub fn begin_open(app: &AppHandle, target: &Target) -> (u64, Option<CommandChild>) {
    let name = match target {
        Target::Project(p) => p.name.clone(),
        Target::Sample { .. } => "sample project".to_string(),
    };
    with(app, |s| {
        s.gen += 1;
        s.current = None;
        s.error = None;
        s.opening = Some(name);
        s.last_target = Some(target.clone());
        (s.gen, s.child.take())
    })
}

pub fn set_child(app: &AppHandle, gen: u64, child: CommandChild) {
    let stale = with(app, |s| {
        if s.gen == gen {
            s.child = Some(child);
            None
        } else {
            Some(child)
        }
    });
    if let Some(c) = stale {
        sidecar::terminate(c);
    }
}

pub fn kill_if_current(app: &AppHandle, gen: u64) {
    let c = with(app, |s| if s.gen == gen { s.child.take() } else { None });
    if let Some(c) = c {
        sidecar::terminate(c);
    }
}

/// Returns false when a newer open superseded this one.
pub fn finish_open(app: &AppHandle, gen: u64, info: &Opened) -> bool {
    with(app, |s| {
        if s.gen != gen {
            return false;
        }
        s.current = Some(info.clone());
        s.opening = None;
        s.error = None;
        true
    })
}

pub fn fail_open(app: &AppHandle, gen: u64, e: ErrorInfo) {
    eprintln!("lemmata: open failed [{}] {}\n{}", e.code, e.message, e.details);
    let c = with(app, |s| {
        if s.gen != gen {
            return None;
        }
        s.opening = None;
        s.error = Some(e);
        s.child.take()
    });
    if let Some(c) = c {
        sidecar::terminate(c);
    }
}

/// The sidecar exited by itself after it had been ready.
pub fn server_died(app: &AppHandle, gen: u64, e: ErrorInfo) {
    let hit = with(app, |s| {
        if s.gen != gen {
            return false;
        }
        s.child = None;
        s.current = None;
        s.error = Some(e);
        true
    });
    if hit {
        show_launcher(app);
        notify(app);
    }
}

/// Close Project: kill the sidecar and go back to the launcher.
pub fn close_project(app: &AppHandle) {
    let c = with(app, |s| {
        s.gen += 1;
        s.current = None;
        s.opening = None;
        s.error = None;
        s.child.take()
    });
    if let Some(c) = c {
        sidecar::terminate(c);
    }
    show_launcher(app);
    notify(app);
}

const SIZE_FILE: &str = "window.json";

/// Remember the project window size in memory (called on resize while a project is shown).
pub fn note_resize(app: &AppHandle, w: f64, h: f64) {
    with(app, |s| {
        if !s.on_launcher {
            s.project_size = Some((w, h));
        }
    });
}

pub fn load_window_size(app: &AppHandle) {
    let size = recent::app_data(app)
        .and_then(|d| std::fs::read_to_string(d.join(SIZE_FILE)).ok())
        .and_then(|t| serde_json::from_str::<(f64, f64)>(&t).ok());
    with(app, |s| s.project_size = size);
}

pub fn save_window_size(app: &AppHandle) {
    if let (Some(sz), Some(d)) = (with(app, |s| s.project_size), recent::app_data(app)) {
        let _ = std::fs::write(d.join(SIZE_FILE), serde_json::to_string(&sz).unwrap_or_default());
    }
}

/// Quit: stop the sidecar synchronously.
pub fn shutdown(app: &AppHandle) {
    save_window_size(app);
    let c = with(app, |s| {
        s.gen += 1;
        s.child.take()
    });
    if let Some(c) = c {
        sidecar::terminate_blocking(c);
    }
}

pub fn clear_error(app: &AppHandle) {
    with(app, |s| s.error = None);
    notify(app);
}

pub fn show_launcher(app: &AppHandle) {
    let (need, url) = with(app, |s| {
        let need = !s.on_launcher;
        s.on_launcher = true;
        s.server = None;
        (need, s.launcher_url.clone())
    });
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.set_title("Lemmata");
        if need {
            save_window_size(app);
            let _ = w.set_min_size(Some(LogicalSize::new(640.0, 480.0)));
            let _ = w.set_size(LogicalSize::new(720.0, 520.0));
            let _ = w.center();
            if let Some(u) = url {
                let _ = w.navigate(u);
            }
        }
    }
}

pub fn navigate_to(app: &AppHandle, url: &str, title: &str) {
    let was_launcher = with(app, |s| std::mem::replace(&mut s.on_launcher, false));
    if let (Some(w), Ok(u)) = (app.get_webview_window("main"), Url::parse(url)) {
        let _ = w.set_title(title);
        if was_launcher {
            let (cw, ch) = with(app, |s| s.project_size).unwrap_or((1440.0, 900.0));
            let _ = w.set_min_size(Some(LogicalSize::new(1100.0, 720.0)));
            let _ = w.set_size(LogicalSize::new(cw.max(1100.0), ch.max(720.0)));
            let _ = w.center();
        }
        let _ = w.navigate(u);
    }
}

pub fn connected_server(app: &AppHandle) -> Option<String> {
    with(app, |s| s.server.clone())
}

pub fn is_connected(app: &AppHandle) -> bool {
    with(app, |s| s.server.is_some())
}

pub fn set_connecting(app: &AppHandle, url: Option<String>) {
    with(app, |s| {
        s.connecting = url;
        s.error = None;
    });
    notify(app);
}

pub fn set_connect_error(app: &AppHandle, e: ErrorInfo) {
    eprintln!("lemmata: connect failed [{}] {}\n{}", e.code, e.message, e.details);
    with(app, |s| {
        s.connecting = None;
        s.error = Some(e);
    });
    show_launcher(app);
    notify(app);
}

/// Close any local project, then show the hub page in the main window.
pub fn set_server(app: &AppHandle, url: &str, host: &str) {
    let child = with(app, |s| {
        s.gen += 1;
        s.current = None;
        s.opening = None;
        s.error = None;
        s.connecting = None;
        // set before navigating: the navigation guard only lets the connected origin through
        s.server = Some(url.to_string());
        s.child.take()
    });
    if let Some(c) = child {
        sidecar::terminate(c);
    }
    navigate_to(app, url, &format!("Lemmata \u{2014} {host}"));
    notify(app);
}

/// Disconnect: forget auto-reconnect and go back to the launcher.
pub fn disconnect(app: &AppHandle) {
    crate::server::forget_auto(app);
    show_launcher(app);
    notify(app);
}

pub fn last_target(app: &AppHandle) -> Option<Target> {
    with(app, |s| s.last_target.clone())
}

pub fn current_root(app: &AppHandle) -> Option<String> {
    with(app, |s| s.current.as_ref().map(|c| c.root.clone()))
}

pub fn has_project(app: &AppHandle) -> bool {
    with(app, |s| s.current.is_some())
}

pub fn zoom_step(app: &AppHandle, f: impl FnOnce(f64) -> f64) {
    let z = with(app, |s| {
        s.zoom = f(s.zoom).clamp(0.5, 3.0);
        s.zoom
    });
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.set_zoom(z);
    }
}

/// Tell the launcher to re-read state and refresh the native menu.
pub fn notify(app: &AppHandle) {
    let _ = app.emit("state-changed", ());
    crate::menu::rebuild(app);
}

#[derive(Serialize)]
pub struct GitStatus {
    pub ok: bool,
    pub version: String,
}

#[derive(Serialize)]
pub struct LauncherState {
    pub version: String,
    pub git: GitStatus,
    pub recent: Vec<RecentView>,
    pub opening: Option<String>,
    pub error: Option<ErrorInfo>,
    pub connecting: Option<String>,
    pub server_url: String,
    pub server_auto: bool,
}

#[derive(Serialize)]
pub struct RecentView {
    #[serde(flatten)]
    pub project: Project,
    pub exists: bool,
}

pub fn launcher_state(app: &AppHandle) -> LauncherState {
    let (opening, error, connecting) = with(app, |s| (s.opening.clone(), s.error.clone(), s.connecting.clone()));
    let saved = crate::server::load(app);
    LauncherState {
        connecting,
        server_url: saved.as_ref().map(|x| x.url.clone()).unwrap_or_else(|| crate::server::DEFAULT_URL.to_string()),
        server_auto: saved.map(|x| x.auto).unwrap_or(false),
        version: app.package_info().version.to_string(),
        git: crate::git::check(),
        recent: recent::load(app)
            .into_iter()
            .map(|p| {
                let exists = std::path::Path::new(&p.path).exists();
                RecentView { project: p, exists }
            })
            .collect(),
        opening,
        error,
    }
}
