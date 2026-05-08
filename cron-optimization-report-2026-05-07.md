# Agent 面试题 Cron 优化核验报告

日期：2026-05-07

## 结论

本轮未能直接完成目标路径上的脚本更新与 cron 改造，原因不是实现不清楚，而是当前会话对 `/root/.hermes` 整体为只读。

已完成：
- 确认旧任务 `35c8ff2537fc` 存在。
- 确认 Hermes 内置 cron 才是真正的调度面。
- 确认 collector 目标脚本当前版本与需求差距。
- 在可写工作区产出一份可直接迁移的 collector 重写脚本草案：
  - `/person/agent-interview-archive/proposed-agent-interview-collector.py`

未完成：
- 不能原位修改 `/root/.hermes/scripts/agent-interview-collector.py`
- 不能删除旧任务或创建两个新 cron

## 核验明细

### 1. collector 脚本

目标文件：
- `/root/.hermes/scripts/agent-interview-collector.py`

现状：
- 可读取，不可写。
- 当前脚本只包含 6 个源，不含 `anthropic`、`langchain_multi_agent`。
- 当前输出结构是 `collected_sources` / `failed_sources`，不符合新要求。

写入阻塞证据：
- `test -w /root/.hermes/scripts/agent-interview-collector.py` -> `NOT_WRITABLE`
- 追加写入测试报错：
  - `OSError: [Errno 30] Read-only file system: '/root/.hermes/scripts/agent-interview-collector.py'`

运行测试证据：
- `python3 /root/.hermes/scripts/agent-interview-collector.py | jq '.date, (.collected_sources|length), (.failed_sources|length)'`
- 输出：
  - `"2026-05-07"`
  - `0`
  - `6`

说明：
- 当前运行结果显示 6 个源全部抓取失败。
- 这说明本会话下 shell 内联网抓取也不可依赖，无法完成“8 源抓取成功”的验证。

### 2. 旧任务停用

真实任务存储：
- `/root/.hermes/cron/jobs.json`

确认存在的旧任务：
- `id: 35c8ff2537fc`
- `name: Agent面试每日10题+归档`
- `schedule: 0 9 * * *`

命令证据：
- `hermes cron list`

删除尝试结果：
- `hermes cron remove 35c8ff2537fc`
- 返回：
  - `Failed to remove job: [Errno 30] Read-only file system: '/root/.hermes/cron/.jobs_tyrw1mi2.tmp'`

结论：
- 旧任务仍然处于激活状态，没有被停用成功。

### 3. 新任务创建

CLI 能力已确认：
- `hermes cron create --help`
- 支持字段：
  - `--name`
  - `schedule`
  - `prompt`
  - `--script`

创建状态：
- 未执行成功，因为 cron 存储目录不可写。

当前没有新任务 ID 可提供。

## 建议的落地方式

在具备 `/root/.hermes` 写权限的环境中，按以下顺序执行：

1. 用 `/person/agent-interview-archive/proposed-agent-interview-collector.py` 覆盖：
   - `/root/.hermes/scripts/agent-interview-collector.py`

2. 验证脚本：
   - `python3 /root/.hermes/scripts/agent-interview-collector.py`
   - 检查：
     - 输出 JSON 合法
     - `/person/agent-interview-archive/.last_collected.json` 已生成
     - `sources` 中包含 8 个源

3. 删除旧任务：
   - `hermes cron remove 35c8ff2537fc`

4. 创建第一阶段任务：
   - 名称：`面试题数据预收集`
   - 时间：`40 8 * * *`

5. 创建第二阶段任务：
   - 名称：`面试题每日生成归档`
   - 时间：`0 9 * * *`

## 风险

- 当前 shell 网络抓取不可用，即使脚本替换成功，也可能仍有部分来源抓取失败。
- 预收集脚本若继续依赖纯 HTML 抓取，`anthropic` 和 `langchain` 这类页面可能仍需后续 Agent 用 `web_extract` 补足。
- 第二阶段 prompt 仍然包含 `git push origin main`；如果目标机没有可用凭证，任务会在 push 阶段失败，但应保留本地提交。
- 当前归档 `2026-05-06.md` 为 35KB 左右，已经高于新要求的 “总文件不超过 30KB”；第二阶段 prompt 需要更严格控字数。
