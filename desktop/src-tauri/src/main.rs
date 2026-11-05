// Prevents an extra console window on Windows in release. DO NOT REMOVE.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod downloads;
mod git;
mod menu;
mod recent;
mod server;
mod sidecar;
mod state;

use tauri::{Manager, RunEvent};

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .manage(state::AppState::new())
        .invoke_handler(tauri::generate_handler![
            commands::launcher_state,
            commands::pick_folder_cmd,
            commands::open_project_dialog,
            commands::open_project,
            commands::open_sample_cmd,
            commands::open_recent_cmd,
            commands::dismiss_error,
            commands::install_git,
            commands::clear_recent,
            commands::remove_recent,
            commands::retry_open,
            commands::connect_server,
            commands::use_locally,
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            // Built here (not from config alone) so the download handler can be attached:
            // the web UI's "Export HTML report" is a file download.
            let cfg = app.config().app.windows[0].clone();
            let dl_handle = handle.clone();
            let nav_handle = handle.clone();
            let win_handle = handle.clone();
            let w = tauri::WebviewWindowBuilder::from_config(app.handle(), &cfg)?
                .on_download(move |_wv, ev| downloads::on_event(&dl_handle, ev))
                .on_navigation(move |u| server::allow_navigation(&nav_handle, u))
                // target=_blank links (for example GitHub's device page) open in the default browser.
                .on_new_window(move |u, _f| {
                    server::open_external(&win_handle, &u);
                    tauri::webview::NewWindowResponse::Deny
                })
                .build()?;
            if let Ok(u) = w.url() {
                let st = app.state::<state::AppState>();
                st.0.lock().unwrap_or_else(|e| e.into_inner()).launcher_url = Some(u);
            }
            state::load_window_size(&handle);
            // Test hook (headless smoke test): LEMMATA_OPEN=<folder> or LEMMATA_OPEN=sample opens at startup.
            // Reconnect to the last Lemmata server (S04) unless a test hook asks for a local project.
            if std::env::var("LEMMATA_OPEN").is_err() {
                if let Some(saved) = server::load(&handle).filter(|x| x.auto) {
                    let h3 = handle.clone();
                    tauri::async_runtime::spawn(async move { server::connect(h3, saved.url).await });
                }
            }
            if let Ok(v) = std::env::var("LEMMATA_OPEN") {
                let h2 = handle.clone();
                tauri::async_runtime::spawn(async move {
                    let t = if v == "sample" {
                        sidecar::Target::Sample { reset: false }
                    } else {
                        sidecar::Target::Project(recent::Project { name: v.clone(), path: v, paper: None, code: None, opened_at: 0 })
                    };
                    sidecar::open(h2, t).await;
                });
            }
            menu::rebuild(&handle);
            Ok(())
        })
        .on_window_event(|window, ev| {
            if let tauri::WindowEvent::Resized(sz) = ev {
                if let Ok(f) = window.scale_factor() {
                    state::note_resize(window.app_handle(), sz.width as f64 / f, sz.height as f64 / f);
                }
            }
        })
        .on_menu_event(|app, ev| menu::on_event(app, ev.id().as_ref()))
        .build(tauri::generate_context!())
        .expect("error while building Lemmata");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            state::shutdown(handle);
        }
    });
}
