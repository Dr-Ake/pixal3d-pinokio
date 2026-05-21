module.exports = {
  run: [
    {
      when: "{{platform === 'win32'}}",
      method: "shell.run",
      params: {
        message: "wsl.exe -d Ubuntu --cd \"{{cwd}}\" -- bash scripts/update_wsl.sh"
      },
      next: null
    },
    {
      when: "{{exists('.git')}}",
      method: "shell.run",
      params: {
        message: "git pull"
      }
    },
    {
      when: "{{exists('app')}}",
      method: "shell.run",
      params: {
        path: "app",
        message: "git pull"
      }
    },
    {
      when: "{{exists('app/env')}}",
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install -r requirements-hfdemo.txt",
          "uv pip install --upgrade gradio gradio_client spaces nest_asyncio pandas lpips tensorboard",
          "uv pip install --force-reinstall --no-deps https://github.com/LDYang694/Storages/releases/download/20260430/utils3d-0.0.2-py3-none-any.whl"
        ]
      }
    }
  ]
}
