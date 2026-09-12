// UI Binder — Tauri shell.
// The desktop window hosts the React frontend; the Python backend is expected
// to run on 127.0.0.1:8765 (see scripts/dev.py or scripts/start_app.py).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
