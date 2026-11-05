//! Download handler: the report's "Export HTML report" link saves into ~/Downloads and is revealed.

use std::path::PathBuf;
use tauri::webview::DownloadEvent;
use tauri::{AppHandle, Manager};
use tauri_plugin_opener::OpenerExt;

fn unique(dir: &PathBuf, name: &str) -> PathBuf {
    let first = dir.join(name);
    if !first.exists() {
        return first;
    }
    let p = std::path::Path::new(name);
    let stem = p.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "report".into());
    let ext = p.extension().map(|s| format!(".{}", s.to_string_lossy())).unwrap_or_default();
    (2..1000).map(|n| dir.join(format!("{stem} ({n}){ext}"))).find(|c| !c.exists()).unwrap_or(first)
}

pub fn on_event(app: &AppHandle, ev: DownloadEvent<'_>) -> bool {
    match ev {
        DownloadEvent::Requested { destination, .. } => {
            let name = destination
                .file_name()
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_else(|| "lemmata-report.html".into());
            let dir = app.path().download_dir().unwrap_or_else(|_| std::env::temp_dir());
            *destination = unique(&dir, &name);
            true
        }
        DownloadEvent::Finished { path: Some(path), success: true, .. } => {
            let _ = app.opener().reveal_item_in_dir(path);
            true
        }
        _ => true,
    }
}
