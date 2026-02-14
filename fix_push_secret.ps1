# 修复 push 被拒：从历史中移除含 API Key 的 commit
# 在项目根目录运行: powershell -ExecutionPolicy Bypass -File fix_push_secret.ps1

Write-Host ">>> Step 1: 回退到 2b21e2b（保留文件修改）..."
git reset --soft 2b21e2b

Write-Host ">>> Step 2: 重新提交（不含 API Key）..."
git add render.yaml render_start.sh
git status
git commit -m "fix: 部署迁移脚本；OPENAI_API_KEY 改在 Render 控制台配置"

Write-Host ">>> Step 3: 查看新历史（应不再包含 5156c2e、c53db87）..."
git log --oneline -5

Write-Host ""
Write-Host ">>> 请手动执行: git push origin master --force"
