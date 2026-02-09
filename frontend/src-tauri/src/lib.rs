// Titier - Tauri Backend Management
use std::sync::Mutex;
use tauri::State;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

// State para gerenciar o processo do backend
struct BackendState {
    child: Mutex<Option<CommandChild>>,
}

#[tauri::command]
async fn start_backend(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<String, String> {
    let mut child_guard = state.child.lock().map_err(|e| e.to_string())?;
    
    if child_guard.is_some() {
        return Ok("Backend já está rodando".to_string());
    }
    
    // Tentar iniciar o sidecar
    let sidecar_result = app.shell()
        .sidecar("titier-backend")
        .map_err(|e| format!("Erro ao configurar sidecar: {}", e))?
        .spawn();
    
    match sidecar_result {
        Ok((_, child)) => {
            *child_guard = Some(child);
            Ok("Backend iniciado com sucesso".to_string())
        }
        Err(e) => {
            // Em dev, o backend pode rodar separadamente
            Err(format!("Sidecar não disponível (modo dev?): {}", e))
        }
    }
}

#[tauri::command]
async fn stop_backend(state: State<'_, BackendState>) -> Result<String, String> {
    let mut child_guard = state.child.lock().map_err(|e| e.to_string())?;
    
    if let Some(child) = child_guard.take() {
        child.kill().map_err(|e| e.to_string())?;
        Ok("Backend parado".to_string())
    } else {
        Ok("Backend não estava rodando".to_string())
    }
}

#[tauri::command]
async fn get_backend_status(state: State<'_, BackendState>) -> Result<serde_json::Value, String> {
    let child_guard = state.child.lock().map_err(|e| e.to_string())?;
    
    if let Some(child) = &*child_guard {
        Ok(serde_json::json!({
            "alive": true,
            "pid": child.pid(),
        }))
    } else {
        Ok(serde_json::json!({
            "alive": false,
            "pid": null,
        }))
    }
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![greet, start_backend, stop_backend, get_backend_status])
        .setup(|_app| {
            // Auto-start backend em produção
            #[cfg(not(debug_assertions))]
            {
                let handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    // Aguardar um pouco antes de iniciar
                    std::thread::sleep(std::time::Duration::from_millis(500));
                    
                    if let Err(e) = handle.shell()
                        .sidecar("titier-backend")
                        .and_then(|cmd| cmd.spawn())
                    {
                        eprintln!("Erro ao iniciar backend: {:?}", e);
                    }
                });
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
