mod backend_manager;

use backend_manager::{BackendManager, BackendStatus};
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_manager = BackendManager::new("127.0.0.1", 8000);

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(backend_manager)
        .invoke_handler(tauri::generate_handler![
            ensure_backend_running,
            get_backend_status,
            pick_repository_folder,
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
