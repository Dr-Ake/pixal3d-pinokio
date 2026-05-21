module.exports = {
  run: [
    {
      when: "{{platform === 'win32'}}",
      method: "shell.run",
      params: {
        message: "wsl.exe -d Ubuntu --cd \"{{cwd}}\" -- bash scripts/reset_wsl.sh"
      }
    },
    {
      when: "{{exists('app')}}",
      method: "fs.rm",
      params: {
        path: "app"
      }
    }
  ]
}
