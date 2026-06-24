mod backend_manager;

use backend_manager::{BackendManager, BackendStatus};
use std::net::{SocketAddr, TcpStream};
use std::process::Command;
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

#[tauri::command]
fn ensure_backend_running(state: tauri::State<'_, BackendManager>) -> BackendStatus {
    state.ensure_running()
}

#[tauri::command]
fn get_backend_status(state: tauri::State<'_, BackendManager>) -> BackendStatus {
    state.status()
}

#[tauri::command]
async fn pick_repository_folder(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .set_title("Open Repository")
        .blocking_pick_folder()
        .map(|p| p.to_string())
}

#[tauri::command]
fn launch_lm_studio() -> Result<String, String> {
    // Try to launch LM Studio on Windows
    #[cfg(target_os = "windows")]
    {
        // Try common LM Studio installation paths
        let _possible_paths = vec![
            r"C:\Program Files\LM Studio\LM Studio.exe",
            r"C:\Users\*\AppData\Local\LM Studio\LM Studio.exe",
        ];

        // Try to find LM Studio in PATH or common locations
        if let Ok(output) = Command::new("where").arg("LM Studio.exe").output() {
            if output.status.success() {
                if let Some(path) = String::from_utf8_lossy(&output.stdout).lines().next() {
                    if let Ok(_) = Command::new(path).spawn() {
                        return Ok(format!("Launched LM Studio from: {}", path));
                    }
                }
            }
        }

        // Try shell:apps launcher on Windows
        if let Ok(_) = Command::new("cmd")
            .args(["/c", "start", "lmstudio:"])
            .spawn()
        {
            return Ok("LM Studio launch initiated via Windows protocol".to_string());
        }

        // Fallback: try to open the URL which may trigger the app
        if let Ok(_) = Command::new("cmd")
            .args(["/c", "start", "http://localhost:1234"])
            .spawn()
        {
            return Ok("Opened LM Studio URL (may trigger app launch)".to_string());
        }

        return Err(
            "Could not find or launch LM Studio. Please ensure it is installed.".to_string(),
        );
    }

    #[cfg(not(target_os = "windows"))]
    {
        Err("LM Studio launch is only supported on Windows currently.".to_string())
    }
}

#[tauri::command]
fn check_lm_studio_running() -> bool {
    // Check if LM Studio is running by checking if port 1234 is open
    let addr: SocketAddr = "127.0.0.1:1234".parse().unwrap();
    TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok()
}

#[tauri::command]
fn get_system_status(state: tauri::State<'_, BackendManager>) -> serde_json::Value {
    let backend_status = state.status();
    let addr: SocketAddr = "127.0.0.1:1234".parse().unwrap();
    let lm_studio_running = TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok();

    serde_json::json!({
        "backend": {
            "running": backend_status.running,
            "managed": backend_status.managed,
            "api_url": backend_status.api_url,
            "message": backend_status.message
        },
        "lm_studio": {
            "running": lm_studio_running,
            "url": "http://127.0.0.1:1234"
        },
        "ready": backend_status.running && lm_studio_running
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_manager = BackendManager::new("127.0.0.1", 8000);

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // Callback when a second instance is launched
            // Focus the existing window
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .manage(backend_manager)
        .invoke_handler(tauri::generate_handler![
            ensure_backend_running,
            get_backend_status,
            pick_repository_folder,
            launch_lm_studio,
            check_lm_studio_running,
            get_system_status,
        ])
        .setup(|_app| Ok(()))
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(manager) = window.try_state::<BackendManager>() {
                    manager.stop_if_managed();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(manager) = app_handle.try_state::<BackendManager>() {
                    manager.stop_if_managed();
                }
            }
        });
}
