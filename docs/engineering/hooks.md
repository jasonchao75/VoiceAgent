# Hooks 轻量守卫与后续规划

Hooks 是 OpenCode 在特定事件发生时（比如刚写完一个文件）自动触发的本地插件规则。它就像是一个后台运行的“小保安”，默默帮你检查代码，不需要像 Skill 那样每次都手动去调用它。

## 当前已启用的轻量 Hook
- **文件位置**: `.opencode/plugins/file-guard.ts`
- **加载方式**: 通过根目录 `opencode.json` 的 `plugin` 配置加载。
- **Hook 类型**: `tool.execute.after`（工具执行后触发）。
- **监听范围**: 当前仅监听 `write` 和 `edit` 两个文件写入操作。
- **检查内容**:
  1. 写完 `configs/vendor/*.json` 后，检查 JSON 格式是否正确，并轻量检查是否包含常见的核心配置字段。
  2. 写完 Python 文件后，运行 `py_compile` 检查是否存在基础语法错误。
  3. 扫描文本文件是否疑似硬编码了 API Key 或 Token。
  4. 修改 `src/pipeline/*.py` 后，检查是否混入了同步阻塞代码（如 `time.sleep`、`requests`）并给出架构风险提醒。
  5. 修改高风险核心文件（如 `.env`、`AGENTS.md` 等）后，追加规范修改提醒（注：当前由于交互限制暂未在修改前阻断，均通过修改后追加提醒实现）。
- **当前策略**: **只提醒，不阻止，不自动修改文件**。如果检查出问题，它会在工具执行结果的末尾追加一段警告，让 Agent 看到并自行修复。

## 未来可探索的 Hooks 规划路线图
*(注：以下仅为未来实际开发中可以考虑的方向，目前并未实现。)*
- **`tool.execute.before` (事前拦截)**: 当前暂未启用。未来如果需要真正的参数拦截或权限阻断，可用于高危操作前的提醒与阻止（例如执行 `rm -rf` 大范围删除、`git reset` 等破坏性操作）。
- **`tool.execute.after` (事后检查扩展)**: 未来可继续扩展为修改特定的适配器后提醒运行对应的自动化评测测试。
- **`Stop` / 任务结束前检查**: 当前 OpenCode v1.14.28 暂无直接 stop Hook。现阶段通过 AGENTS.md / Skills 的完成前清单约束实现；未来若插件 SDK 支持 session end 或 stop 事件，再考虑自动化。
- **`shell.env` (环境变量注入)**: 后期进入真实厂商联调时考虑启用，用于在运行测试脚本时向子进程安全注入环境变量，避免 API Key 出现在代码和对话历史里。
- **`permission.ask` (自动化白名单)**: 等待自动化评测流水线成熟后再考虑。可用于让 Evaluation-Engineer 在批量读取 `benchmarks/` 或执行 `scripts/evaluation/` 时自动放行，减少人机交互中的重复确认流程。
