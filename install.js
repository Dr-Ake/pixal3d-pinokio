module.exports = {
  run: [
    {
      when: "{{platform === 'win32'}}",
      method: "shell.run",
      params: {
        message: [
          "powershell -Command \"[Console]::OutputEncoding = [System.Text.Encoding]::Unicode; if ((wsl.exe -l -v 2>&1 | Out-String) -notmatch 'Ubuntu') { Write-Host 'Ubuntu WSL distribution not found. Installing Ubuntu...'; wsl.exe --install -d Ubuntu --no-launch } else { Write-Host 'Ubuntu WSL distribution is already installed.' }\"",
          "wsl.exe -d Ubuntu -u root apt-get update",
          "wsl.exe -d Ubuntu -u root apt-get install -y bzip2 git curl",
          "wsl.exe -d Ubuntu --cd \"{{cwd}}\" -- bash scripts/install_wsl.sh"
        ]
      },
      next: null
    },
    {
      when: "{{platform !== 'linux' || gpu !== 'nvidia'}}",
      method: "notify",
      params: {
        html: "Pixal3D local install requires Linux with an NVIDIA CUDA GPU, or Windows with WSL Ubuntu and WSL GPU support."
      },
      next: null
    },
    {
      when: "{{!exists('app')}}",
      method: "shell.run",
      params: {
        message: [
          "git clone https://github.com/TencentARC/Pixal3D.git app"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        message: "bash scripts/apply_patches.sh app"
      }
    },
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install --upgrade pip setuptools wheel",
          "uv pip install -r requirements-hfdemo.txt",
          "uv pip install --upgrade gradio gradio_client spaces nest_asyncio pandas lpips tensorboard \"transformers>=4.58.0\"",
          "uv pip install --force-reinstall --no-deps https://github.com/LDYang694/Storages/releases/download/20260430/utils3d-0.0.2-py3-none-any.whl"
        ]
      }
    },
    {
      method: "fs.link",
      params: {
        venv: "app/env"
      }
    },
    {
      method: "notify",
      params: {
        html: "Pixal3D is installed. Start Low VRAM is recommended for first launch."
      }
    }
  ]
}
