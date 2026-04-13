# 贡献指南

感谢你有兴趣为 Aether 项目做出贡献！

## 行为准则

参与本项目请遵守我们的 [行为准则](CODE_OF_CONDUCT.md)。

## 如何贡献

### 报告问题

1. 在提交新问题前，请先搜索现有 [Issues](../../issues)
2. 使用清晰的标题描述问题
3. 提供复现步骤
4. 包含屏幕截图（如适用）
5. 说明你的环境（浏览器、操作系统、Python 版本等）

### 提交代码

1. **Fork 本仓库**

   点击页面右上角的 "Fork" 按钮

2. **克隆你的 Fork**

   ```bash
   git clone https://github.com/你的用户名/daily-assistant.git
   cd daily-assistant
   ```

3. **创建分支**

   ```bash
   git checkout -b feature/你的特性名称
   # 或
   git checkout -b fix/你的修复名称
   ```

4. **设置上游仓库**

   ```bash
   git remote add upstream https://github.com/原作者用户名/daily-assistant.git
   ```

5. **进行更改**

   - 确保代码风格一致
   - 添加必要的注释
   - 测试你的更改

6. **提交更改**

   ```bash
   git add .
   git commit -m "描述你的更改"
   ```

   提交信息格式：
   - `feat: 新功能描述`
   - `fix: 修复描述`
   - `docs: 文档更新`
   - `style: 代码格式调整`
   - `refactor: 重构`
   - `test: 测试相关`

7. **推送到你的 Fork**

   ```bash
   git push origin feature/你的特性名称
   ```

8. **创建 Pull Request**

   - 从你的分支创建 PR 到上游仓库的 `main` 分支
   - 详细描述你的更改
   - 链接相关的 Issue（如有）

## 开发指南

### 环境设置

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_something.py
```

### 代码风格

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- 使用类型提示
- 函数和类要有文档字符串

### 提交前检查清单

- [ ] 代码已格式化
- [ ] 所有测试通过
- [ ] 更新了相关文档
- [ ] 添加了必要的测试
- [ ] 提交信息清晰描述了更改

## 开源协议说明

⚠️ **重要**：所有贡献到本项目的代码将采用 [GNU AGPL-3.0](LICENSE) 协议开源。

这意味着：
- 你的贡献代码将可以免费使用、修改、分发
- 衍生作品必须同样以 AGPL-3.0 开源
- 不得将本项目或其衍生作品用于商业用途

通过提交 Pull Request，你同意你的贡献将受此协议约束。

## 获取帮助

如有任何问题，请随时：
- 开启一个 [Issue](../../issues)
- 在相关的 Issue/PR 下评论

---

再次感谢你的贡献！🎉
