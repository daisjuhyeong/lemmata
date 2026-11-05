//! Recent projects, stored as JSON in `<app_data>/recent.json` (last 8, newest first).

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

pub const MAX_RECENT: usize = 8;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Project {
    pub name: String,
    /// Folder passed as the positional `project_dir` argument.
    pub path: String,
    /// Optional separate paper folder (advanced open).
    #[serde(default)]
    pub paper: Option<String>,
    /// Optional separate code folder (advanced open).
    #[serde(default)]
    pub code: Option<String>,
    /// Unix seconds of the last successful open.
    #[serde(default)]
    pub opened_at: u64,
}

impl Project {
    pub fn same_as(&self, other: &Project) -> bool {
        self.path == other.path && self.paper == other.paper && self.code == other.code
    }
}

pub fn app_data(app: &AppHandle) -> Option<PathBuf> {
    let dir = app.path().app_data_dir().ok()?;
    std::fs::create_dir_all(&dir).ok()?;
    Some(dir)
}

fn file(app: &AppHandle) -> Option<PathBuf> {
    app_data(app).map(|d| d.join("recent.json"))
}

pub fn load(app: &AppHandle) -> Vec<Project> {
    file(app)
        .and_then(|f| std::fs::read_to_string(f).ok())
        .and_then(|s| serde_json::from_str::<Vec<Project>>(&s).ok())
        .map(|mut v| {
            v.truncate(MAX_RECENT);
            v
        })
        .unwrap_or_default()
}

fn save(app: &AppHandle, list: &[Project]) {
    if let (Some(f), Ok(s)) = (file(app), serde_json::to_string_pretty(list)) {
        let _ = std::fs::write(f, s);
    }
}

pub fn push(app: &AppHandle, mut p: Project) {
    p.opened_at = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let mut list = load(app);
    list.retain(|x| !x.same_as(&p));
    list.insert(0, p);
    list.truncate(MAX_RECENT);
    save(app, &list);
}

pub fn remove(app: &AppHandle, index: usize) {
    let mut list = load(app);
    if index < list.len() {
        list.remove(index);
        save(app, &list);
    }
}

pub fn clear(app: &AppHandle) {
    save(app, &[]);
}
