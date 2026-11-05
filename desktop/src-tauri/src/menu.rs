//! Native menus. Rebuilt whenever the recent list or the open/closed state changes.

use crate::{commands, recent, state};
use tauri::menu::{AboutMetadata, Menu, MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::{AppHandle, Manager, Wry};

fn build(app: &AppHandle) -> tauri::Result<Menu<Wry>> {
    let has = state::has_project(app);
    let connected = state::is_connected(app);
    let recent_list = recent::load(app);

    let mut recent_sub = SubmenuBuilder::new(app, "Open Recent");
    if recent_list.is_empty() {
        recent_sub = recent_sub.item(&MenuItemBuilder::with_id("none", "No recent projects").enabled(false).build(app)?);
    } else {
        for (i, p) in recent_list.iter().enumerate() {
            recent_sub = recent_sub.item(&MenuItemBuilder::with_id(format!("recent:{i}"), &p.name).build(app)?);
        }
        recent_sub = recent_sub.separator().item(&MenuItemBuilder::with_id("clear_recent", "Clear Menu").build(app)?);
    }
    let recent_sub = recent_sub.build()?;

    let about = PredefinedMenuItem::about(
        app,
        Some("About Lemmata"),
        Some(AboutMetadata {
            name: Some("Lemmata".into()),
            version: Some(app.package_info().version.to_string()),
            comments: Some("A pre-submission checker for ML papers.".into()),
            ..Default::default()
        }),
    )?;

    let app_menu = SubmenuBuilder::new(app, "Lemmata")
        .item(&about)
        .separator()
        .hide()
        .hide_others()
        .show_all()
        .separator()
        .quit()
        .build()?;

    let file = SubmenuBuilder::new(app, "File")
        .item(&MenuItemBuilder::with_id("open", "Open Project\u{2026}").accelerator("CmdOrCtrl+O").build(app)?)
        .item(&MenuItemBuilder::with_id("sample", "Open Sample").build(app)?)
        .item(&recent_sub)
        .separator()
        .item(&MenuItemBuilder::with_id("reset_sample", "Reset Sample").build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("connect", "Connect to Server\u{2026}").build(app)?)
        .item(&MenuItemBuilder::with_id("disconnect", "Disconnect").enabled(connected).build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("close", "Close Project").accelerator("CmdOrCtrl+W").enabled(has || connected).build(app)?)
        .item(&MenuItemBuilder::with_id("reveal", if cfg!(target_os = "macos") { "Reveal Project in Finder" } else { "Reveal Project in File Manager" }).enabled(has).build(app)?)
        .build()?;

    // Edit is required on macOS for copy/paste shortcuts to work inside the web view.
    let edit = SubmenuBuilder::new(app, "Edit")
        .undo()
        .redo()
        .separator()
        .cut()
        .copy()
        .paste()
        .select_all()
        .build()?;

    let view = SubmenuBuilder::new(app, "View")
        .item(&MenuItemBuilder::with_id("reload", "Reload").accelerator("CmdOrCtrl+R").enabled(has || connected).build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("zoom_reset", "Actual Size").accelerator("CmdOrCtrl+0").build(app)?)
        .item(&MenuItemBuilder::with_id("zoom_in", "Zoom In").accelerator("CmdOrCtrl+=").build(app)?)
        .item(&MenuItemBuilder::with_id("zoom_out", "Zoom Out").accelerator("CmdOrCtrl+-").build(app)?)
        .build()?;

    let window = SubmenuBuilder::new(app, "Window").minimize().maximize().build()?;

    let help = SubmenuBuilder::new(app, "Help")
        .item(&MenuItemBuilder::with_id("help", "Lemmata on GitHub").build(app)?)
        .build()?;

    let mut mb = MenuBuilder::new(app);
    if cfg!(target_os = "macos") {
        mb = mb.item(&app_menu);
    }
    mb.item(&file).item(&edit).item(&view).item(&window).item(&help).build()
}

pub fn rebuild(app: &AppHandle) {
    if let Ok(m) = build(app) {
        let _ = app.set_menu(m);
    }
}

pub fn on_event(app: &AppHandle, id: &str) {
    let app = app.clone();
    match id {
        "open" => {
            tauri::async_runtime::spawn(commands::open_dialog_then_project(app));
        }
        "sample" => {
            tauri::async_runtime::spawn(commands::open_sample(app, false));
        }
        "reset_sample" => {
            tauri::async_runtime::spawn(commands::open_sample(app, true));
        }
        "close" => {
            if state::is_connected(&app) {
                state::disconnect(&app);
            } else {
                state::close_project(&app);
            }
        }
        "connect" => {
            // Back to the launcher, which has the server field; it focuses the field on this event.
            state::show_launcher(&app);
            let _ = tauri::Emitter::emit(&app, "focus-connect", ());
        }
        "disconnect" => state::disconnect(&app),
        "reveal" => commands::reveal_project(&app),
        "clear_recent" => {
            recent::clear(&app);
            state::notify(&app);
        }
        "reload" => {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.eval("location.reload()");
            }
        }
        "zoom_reset" => state::zoom_step(&app, |_| 1.0),
        "zoom_in" => state::zoom_step(&app, |z| z + 0.1),
        "zoom_out" => state::zoom_step(&app, |z| z - 0.1),
        "help" => commands::open_help(&app),
        other => {
            if let Some(i) = other.strip_prefix("recent:").and_then(|n| n.parse::<usize>().ok()) {
                tauri::async_runtime::spawn(commands::open_recent(app, i));
            }
        }
    }
}
