# 贡献指南

感谢您对 AccountingCLI 的关注！我们欢迎所有形式的贡献，包括但不限于报告问题、提交功能请求、改进文档和代码贡献。

## 开始之前

### 行为准则

请确保您的行为符合开源社区的基本准则：
- 友善和专业的沟通
- 尊重不同的观点和经验
- 接受建设性的批评

### 寻找可以贡献的地方

- 查看 [Issues](../../issues) 列表中的 bug 和功能请求
- 改进文档和示例
- 添加新的测试用例
- 优化代码性能

## 开发流程

### 环境设置

1. Fork 并克隆仓库
2. 确保安装了 Python 3.9 或更高版本
3. 创建虚拟环境并安装依赖：
   ```bash
   cd python
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

### 运行测试

项目使用 pytest 进行测试：

```bash
cd python
pytest tests/ -v --cov=src --cov-report=term-missing
```

所有 PR 都需要：
- 通过所有现有测试
- 添加新功能的测试
- 保持高代码覆盖率

## 代码贡献指南

### 代码风格

- 遵循 PEP 8 规范
- 使用有意义的变量名和函数名
- 添加必要的注释和文档字符串

### 提交规范

使用清晰的提交信息，格式建议：

```
<类型>: <简短描述>

<详细描述>
```

类型包括：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具链相关

### Pull Request 流程

1. 创建新的功能分支：`git checkout -b feature/my-new-feature`
2. 提交您的更改：`git commit -am 'feat: add some feature'`
3. 推送到分支：`git push origin feature/my-new-feature`
4. 创建一个 Pull Request

### PR 要求

- 一个 PR 只做一件事
- PR 描述清晰说明更改内容和原因
- 确保所有测试通过
- 更新相关文档

## 报告问题

在报告 Bug 时，请包含：

1. 操作系统和 Python 版本
2. 项目版本（git commit hash）
3. 复现步骤
4. 预期行为和实际行为
5. 相关日志或输出

## 功能请求

在建议新功能时，请考虑：

1. 这个功能对大多数用户有用吗？
2. 是否有其他替代方案可以实现相同效果？
3. 这个功能会增加多少维护成本？

## 文档改进

文档同样重要！如果您发现：
- 拼写错误
- 不清楚的说明
- 缺失的文档
- 过时的示例

请随时提交 PR 进行改进。

## 问题？

如有任何问题，请在 Issues 中提问，我们会尽快回复。

再次感谢您的贡献！🎉