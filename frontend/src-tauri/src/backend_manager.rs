use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct BackendStatus {
    pub running: bool,
    pub managed: bool,
    pub message: String,
    pub api_url: String,
}

pub struct BackendManager {
    child: Mutex<Option<Child>>,
    managed: Mutex<bool>,
    api_host: String,
    api_port: u16,
}

impl BackendManager {
    pub fn new(api_host: &str, api_port: u16) -> Self {
        Self {
            child: Mutex::new(None),
            managed: Mutex::new(false),
            api_host: api_host.to_string(),
            api_port,
        }
    }

    fn api_url(&self) -> String {
        format!("http://{}:{}", self.api_host, self.api_port)
    }

    fn health_url(&self) -> String {
        format!("{}/health", self.api_url())
    }

    fn is_port_open(&self) -> bool {
        TcpStream::connect_timeout(
            &format!("{}:{}", self.api_host, self.api_port)
                .parse()
                .unwrap(),
            Duration::from_millis(400),
        )
        .is_ok()
    }

    fn check_health(&self) -> bool {
        if !self.is_port_open() {
            return false;
        }
        ureq::get(&self.health_url())
            .timeout(Duration::from_secs(2))
            .call()
            .map(|r| r.status() == 200)
            .unwrap_or(false)
    }

    fn find_project_root() -> Option<PathBuf> {
        if let Ok(root) = std::env::var("DIRIGENT_ROOT") {
            let path = PathBuf::from(root);
            if path.join("backend").is_dir() {
                return Some(path);
            }
        }

        if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
            let path = PathBuf::from(manifest)
                .parent()?
                .parent()?
                .to_path_buf();
            if path.join("backend").is_dir() {
                return Some(path);
            }
        }

        if let Ok(exe) = std::env::current_exe() {
            let mut dir = exe.parent()?.to_path_buf();
            for _ in 0..6 {
                if dir.join("backend").is_dir() {
                    return Some(dir);
                }
                if !dir.pop() {
                    break;
                }
            }
        }

        None
    }

    fn find_python(project_root: &PathBuf) -> Option<String> {
        let venv_python = if cfg!(windows) {
            project_root.join("venv").join("Scripts").join("python.exe")
        } else {
            project_root.join("venv").join("bin").join("python")
        };
        if venv_python.is_file() {
            return Some(venv_python.to_string_lossy().into_owned());
        }

        for candidate in ["python", "python3", "py"] {
            if Command::new(candidate)
                .arg("--version")
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
            {
                return Some(candidate.to_string());
            }
        }

        None
    }

    fn spawn_backend(&self) -> Result<(), String> {
        let project_root = Self::find_project_root()
            .ok_or_else(|| "Could not locate Dirigent project root".to_string())?;
        let python = Self::find_python(&project_root)
            .ok_or_else(|| "Python not found. Install Python 3.12+ or create a venv.".to_string())?;

        let script = project_root.join("run_backend.py");
        if !script.is_file() {
            return Err(format!("Backend script not found: {}", script.display()));
        }

        let child = Command::new(&python)
            .arg(&script)
            .arg("--no-reload")
            .current_dir(&project_root)
            .env("DIRIGENT_DEV", "0")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start backend: {e}"))?;

        *self.child.lock().unwrap() = Some(child);
        *self.managed.lock().unwrap() = true;
        Ok(())
    }

    pub fn ensure_running(&self) -> BackendStatus {
        if self.check_health() {
            return BackendStatus {
                running: true,
                managed: *self.managed.lock().unwrap(),
                message: "Backend is online".to_string(),
                api_url: self.api_url(),
            };
        }

        if let Err(err) = self.spawn_backend() {
            return BackendStatus {
                running: false,
                managed: false,
                message: err,
                api_url: self.api_url(),
            };
        }

        let deadline = Instant::now() + Duration::from_secs(30);
        while Instant::now() < deadline {
            if self.check_health() {
                return BackendStatus {
                    running: true,
                    managed: true,
                    message: "Backend started successfully".to_string(),
                    api_url: self.api_url(),
                };
            }
            std::thread::sleep(Duration::from_millis(300));
        }

        BackendStatus {
            running: false,
            managed: *self.managed.lock().unwrap(),
            message: "Backend failed to start within 30 seconds".to_string(),
            api_url: self.api_url(),
        }
    }

    pub fn stop_if_managed(&self) {
        let managed = *self.managed.lock().unwrap();
        if !managed {
            return;
        }

        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *self.managed.lock().unwrap() = false;
    }

    pub fn status(&self) -> BackendStatus {
        BackendStatus {
            running: self.check_health(),
            managed: *self.managed.lock().unwrap(),
            message: if self.check_health() {
                "Backend is online".to_string()
            } else {
                "Backend is offline".to_string()
            },
            api_url: self.api_url(),
        }
    }
}
