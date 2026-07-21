# CI 平台适配

先读取仓库内 CI 配置，再判断是否有对应 CLI。所有查询必须绑定当前 commit，避免把旧 run 当作新结果。

## GitHub Actions

优先检查：

```bash
gh auth status
gh pr status
gh pr checks <pr-number>
gh run list --branch <branch> --limit 10
gh run view <run-id> --log-failed
```

- 以 PR head SHA 或 workflow run head SHA 对齐当前 commit。
- required checks 未全部完成时保持等待或报告 pending。
- 只对取消、服务故障、runner 丢失等明确瞬时失败重跑。
- 代码或测试失败必须先修复，再等待新 commit 的 run。

## GitLab CI

优先检查：

```bash
glab auth status
glab mr view
glab ci status
glab ci trace <job-id>
```

- 将 pipeline SHA 与当前 commit 对齐。
- 区分 MR pipeline、branch pipeline、merge train 和 deployment job。
- protected branch、environment approval 或 manual job 是策略门禁，不得绕过。

## 其他平台

- CircleCI：读取 `.circleci/config.yml`，使用已配置 CLI 或平台链接查询 workflow。
- Jenkins：读取 `Jenkinsfile`；没有安全的认证入口时只给出 job 名和需要人工查询的证据。
- Buildkite、Azure Pipelines、Bitbucket Pipelines：先读取各自配置，再使用仓库已有工具。

不得为了方便安装全局 CLI、写入凭据或把认证信息加入仓库。缺少平台能力时，生成 handoff 并把状态标记为 `BLOCKED` 或 `UNKNOWN`。

## 失败分类

| 类型 | 证据 | 动作 |
| --- | --- | --- |
| 代码/编译 | 稳定错误、同 commit 可复现 | 最小修复并本地复验 |
| 测试失败 | 断言、快照、覆盖率或竞态 | 定位首个根因，不删除门禁 |
| 环境/凭据 | secret、权限、环境变量缺失 | 不回显值，交由有权限者处理 |
| 基础设施 | runner、网络、服务不可用 | 确认瞬时故障后有限重跑 |
| 配额/策略 | rate limit、审批、保护规则 | 等待或请求授权，不绕过 |
| flaky | 相同代码结果不稳定且有历史证据 | 记录频率，修复不确定性后再通过 |

## CI 完成条件

- 当前 commit 对应的所有 required checks 为成功；
- 没有被忽略的失败、取消或过期 run；
- PR 审批、合并队列、环境审批等策略状态已明确；
- 若用户要求发布，部署和 smoke 状态必须单独验证。
