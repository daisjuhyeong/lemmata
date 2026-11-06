//! Connect to a Lemmata hub (S04): remember the URL, probe it, navigate the window to it.
//! The hub page is a remote origin: capabilities grant it no IPC, and page navigation is limited
//! to the hub origin (anything else opens in the default browser).

use crate::recent;
use crate::state::{self, ErrorInfo};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tauri::{AppHandle, Url};
use tauri_plugin_opener::OpenerExt;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

pub const DEFAULT_URL: &str = "http://100.111.135.94:8765";
pub const UNREACHABLE: &str = "Can't reach the Mac mini. Is it on, and is Tailscale connected on both Macs?";
const FILE: &str = "server.json";

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Saved {
    pub url: String,
    /// Reconnect automatically on launch (cleared by Disconnect and Use locally).
    #[serde(default)]
    pub auto: bool,
}

pub fn load(app: &AppHandle) -> Option<Saved> {
    recent::app_data(app)
        .and_then(|d| std::fs::read_to_string(d.join(FILE)).ok())
        .and_then(|s| serde_json::from_str(&s).ok())
}

pub fn save(app: &AppHandle, s: &Saved) {
    if let (Some(d), Ok(t)) = (recent::app_data(app), serde_json::to_string(s)) {
        let _ = std::fs::write(d.join(FILE), t);
    }
}

pub fn forget_auto(app: &AppHandle) {
    if let Some(mut s) = load(app) {
        s.auto = false;
        save(app, &s);
    }
}

/// Accept http(s)://host[:port] only; returns the normalised origin.
pub fn normalise(input: &str) -> Result<Url, ErrorInfo> {
    let t = input.trim();
    let t = if t.contains("://") { t.to_string() } else { format!("http://{t}") };
    let bad = || ErrorInfo::new("bad_url", "Enter the server address, for example http://100.111.135.94:8765", "");
    let u = Url::parse(&t).map_err(|_| bad())?;
    if !matches!(u.scheme(), "http" | "https") || u.host_str().is_none() {
        return Err(bad());
    }
    Url::parse(&u.origin().ascii_serialization()).map_err(|_| bad())
}

/// GET /api/hub/status over a plain TCP connection (http only; the hub is on Tailscale).
async fn probe(u: &Url) -> Result<(), String> {
    let host = u.host_str().unwrap_or_default().to_string();
    let port = u.port_or_known_default().unwrap_or(80);
    let work = async {
        let mut s = tokio::net::TcpStream::connect((host.as_str(), port)).await.map_err(|e| e.to_string())?;
        let req = format!("GET /api/hub/status HTTP/1.0\r\nHost: {host}:{port}\r\nAccept: application/json\r\n\r\n");
        s.write_all(req.as_bytes()).await.map_err(|e| e.to_string())?;
        let mut buf = vec![0u8; 256];
        let n = s.read(&mut buf).await.map_err(|e| e.to_string())?;
        let head = String::from_utf8_lossy(&buf[..n]).to_string();
        if head.starts_with("HTTP/1.") && head.contains(" 200") {
            Ok(())
        } else {
            Err(format!("Unexpected reply: {}", head.lines().next().unwrap_or("")))
        }
    };
    match tokio::time::timeout(Duration::from_secs(5), work).await {
        Ok(r) => r,
        Err(_) => Err("Timed out after 5 s".into()),
    }
}

/// Connect (or reconnect): probe, remember, navigate. Errors land in the launcher banner.
pub async fn connect(app: AppHandle, input: String) {
    let url = match normalise(&input) {
        Ok(u) => u,
        Err(e) => {
            state::set_connect_error(&app, e);
            return;
        }
    };
    let shown = url.as_str().trim_end_matches('/').to_string();
    state::set_connecting(&app, Some(shown.clone()));
    match probe(&url).await {
        Ok(()) => {
            save(&app, &Saved { url: shown.clone(), auto: true });
            state::set_server(&app, &shown, url.host_str().unwrap_or("server"));
        }
        Err(details) => {
            state::set_connect_error(&app, ErrorInfo::new("server_unreachable", UNREACHABLE, &details));
        }
    }
}

/// Navigation policy for the main window: local pages, the connected hub origin and loopback stay;
/// every other http(s) URL opens in the default browser.
pub fn allow_navigation(app: &AppHandle, u: &Url) -> bool {
    match u.scheme() {
        "http" | "https" => {
            let host = u.host_str().unwrap_or("");
            if host == "tauri.localhost" || host == "127.0.0.1" || host == "localhost" {
                return true;
            }
            if let Some(server) = state::connected_server(app) {
                if let Ok(s) = Url::parse(&server) {
                    if s.origin() == u.origin() {
                        return true;
                    }
                }
            }
            open_external(app, u);
            false
        }
        _ => true,
    }
}

pub fn open_external(app: &AppHandle, u: &Url) {
    if matches!(u.scheme(), "http" | "https") {
        let _ = app.opener().open_url(u.as_str(), None::<&str>);
    }
}
