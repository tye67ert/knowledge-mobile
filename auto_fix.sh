#!/bin/bash
echo "🔧 开始自动修复 main.py..."

# 备份当前文件
cp main.py main.py.auto_bak

# 删除开头的错误行（如果存在）
sed -i '' '/^import osn/d' main.py
sed -i '' '/^APP_DIR = Path.*"data"n/d' main.py
sed -i '' '/^APP_DIR.mkdir(dparentes=True, exist_ok=True)n/d' main.py

# 在文件开头插入正确的内容
sed -i '' '1i\
import os
from pathlib import Path

APP_DIR = Path(os.path.dirname(__file__)) / "data"
APP_DIR.mkdir(parents=True, exist_ok=True)
' main.py

echo "✅ main.py 修复完成。"

# 确保工作流文件存在
if [ ! -f .github/workflows/build.yml ]; then
    echo "📄 创建工作流文件..."
    mkdir -p .github/workflows
    cat > .github/workflows/build.yml << 'YAML'
name: Build APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install flet

      - name: Build APK
        env:
          FLET_YES: 1
        run: |
          flet build apk --org com.yourcompany --product "知识图谱" --yes

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: knowledge-graph-app
          path: build/apk/*.apk
YAML
    echo "✅ 工作流文件已创建。"
else
    echo "✅ 工作流文件已存在。"
fi

# 提交并推送
echo "📤 提交并推送修复..."
git add main.py .github/workflows/build.yml
git commit -m "Auto-fix: correct main.py header and ensure workflow" || echo "没有新变更需要提交"
git push

echo ""
echo "🎉 修复完成！请打开以下页面手动触发构建："
echo "https://github.com/tye67ert/knowledge-mobile/actions"
echo "点击左侧 'Build APK' → 'Run workflow' → 选择分支 'main' → 点击运行。"
