module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        message: "powershell -ExecutionPolicy Bypass -File scripts/fix_tdr.ps1",
        on: [{
          event: "/restart your computer/i",
          done: true
        }]
      }
    },
    {
      method: "notify",
      params: {
        html: "TDR GPU Timeout increased. Please restart your computer to apply the changes."
      }
    }
  ]
}
