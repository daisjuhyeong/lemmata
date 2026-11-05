//! Commands invoked from the launcher page, and the actions shared with the native menu.

use crate::recent::{self, Project};
use crate::sidecar::{self, Target};
use crate::state::{self, ErrorInfo, LauncherState};
use std::path::Path;
use tauri::AppHandle;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
use tauri_plugin_opener::OpenerExt;

pub const HELP_URL: &str = "https://github.com/lemmata-ai/lemmata";

fn folder_name(p: &str) -> String {
    Path::new(p).file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| p.to_string())
}

/// Native folder picker. Runs the blocking dialog off the UI thread.
pub async fn pick_folder(app: &AppHandle, title: &str) -> Option<String> {
    let app = app.clone();
    let title = title.to_string();
    tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title(title)
            .blocking_pick_folder()
            .and_then(|p| p.into_path().ok())
            .map(|p| p.to_string_lossy().into_owned())
    })
    .await
    .ok()
    .flatten()
}

pub async fn open_dialog_then_project(app: AppHandle) {
    if let Some(path) = pick_folder(&app, "Open project folder (paper and/or code)").await {
        sidecar::open(app, Target::Project(Project { name: folder_name(&path), path, paper: None, code: None, opened_at: 0 })).await;
    }
}

pub async fn open_sample(app: AppHandle, reset: bool) {
    if reset {
        let a = app.clone();
        let ok = tauri::async_runtime::spawn_blocking(move || {
            a.dialog()
                .message("This replaces the sample with a fresh copy. Your own projects are not affected.")
                .title("Reset the sample project?")
                .kind(MessageDialogKind::Warning)
                .buttons(MessageDialogButtons::OkCancelCustom("Reset Sample".into(), "Cancel".into()))
                .blocking_show()
        })
        .await
        .unwrap_or(false);
        if !ok {
            return;
        }
    }
    sidecar::open(app, Target::Sample { reset }).await;
}

pub async fn open_recent(app: AppHandle, index: usize) {
    if let Some(p) = recent::load(&app).get(index).cloned() {
        sidecar::open(app, Target::Project(p)).await;
    }
}

pub fn reveal_project(app: &AppHandle) {
    if let Some(root) = state::current_root(app) {
        let _ = app.opener().reveal_item_in_dir(Path::new(&root));
    }
}

pub fn open_help(app: &AppHandle) {
    let _ = app.opener().open_url(HELP_URL, None::<&str>);
}

// ---- commands (launcher) ----

#[tauri::command]
pub fn launcher_state(app: AppHandle) -> LauncherState {
    state::launcher_state(&app)
}

#[tauri::command]
pub async fn pick_folder_cmd(app: AppHandle, title: String) -> Option<String> {
    pick_folder(&app, &title).await
}

#[tauri::command]
pub async fn open_project_dialog(app: AppHandle) {
    open_dialog_then_project(app).await;
}

/// `path` is the project folder; with `paper` and/or `code` set it is the advanced split open.
#[tauri::command]
pub async fn open_project(app: AppHandle, path: String, paper: Option<String>, code: Option<String>) -> Result<(), ErrorInfo> {
    let path = if path.is_empty() { paper.clone().or_else(|| code.clone()).unwrap_or_default() } else { path };
    if path.is_empty() {
        return Err(ErrorInfo::new("no_folder", "Choose a folder first.", ""));
    }
    let name = folder_name(&path);
    sidecar::open(app, Target::Project(Project { name, path, paper, code, opened_at: 0 })).await;
    Ok(())
}

#[tauri::command]
pub async fn open_sample_cmd(app: AppHandle) {
    open_sample(app, false).await;
}

#[tauri::command]
pub async fn open_recent_cmd(app: AppHandle, index: usize) {
    open_recent(app, index).await;
}

#[tauri::command]
pub fn dismiss_error(app: AppHandle) {
    state::clear_error(&app);
}

#[tauri::command]
pub fn install_git() {
    crate::git::install();
}

#[tauri::command]
pub fn clear_recent(app: AppHandle) {
    recent::clear(&app);
    state::notify(&app);
}

#[tauri::command]
pub fn remove_recent(app: AppHandle, index: usize) {
    recent::remove(&app, index);
    state::notify(&app);
}

#[tauri::command]
pub async fn retry_open(app: AppHandle) {
    if let Some(t) = state::last_target(&app) {
        sidecar::open(app, t).await;
    }
}
