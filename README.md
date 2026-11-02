# PRD 到交互设计

这个仓库同时支持 Codex 和 TRAE 中国版。主 Skill 的入口是 [SKILL.md](SKILL.md)；需求与交互分析方法已内置于 [references/knowledge-analysis-method.md](references/knowledge-analysis-method.md)。竞品研究由可单独调用的 `competitive-analysis` 完成；`packages/` 包含主 Skill 和四个专业 Skill 的安装归档。

## TRAE 用户：把仓库链接发给 TRAE

仅粘贴 GitHub 链接不会自动安装 Skill。请把链接和下面这段话一起发给 TRAE：

> 请打开 https://github.com/sghhqzkg4m-debug/prd-to-design ，阅读 README，然后按其中的 TRAE 安装方式安装仓库内全部 5 个 Skill。不要只根据链接重新生成一个 Skill。如果已有同名 Skill 且内容不同，先问我是否替换，不要擅自使用 `--force`。安装后检查 `~/.trae-cn/skills/prd-to-design/SKILL.md`、内置的 `references/knowledge-analysis-method.md` 及另外 4 个 Skill 的 `SKILL.md` 均存在，再告诉我如何开始使用。

也可以在 TRAE 的终端亲自执行一条命令：

```bash
curl -fsSL https://raw.githubusercontent.com/sghhqzkg4m-debug/prd-to-design/main/install.sh | bash -s -- --target trae
```

这会安装到 TRAE 中国版的[全局技能目录](https://docs.trae.cn/ide_skills) `~/.trae-cn/skills/`。安装后重启 TRAE，发送“使用 prd-to-design 分析这份需求”。

## Codex 用户：一次安装

在 macOS 或 Linux 终端运行：

```bash
curl -fsSL https://raw.githubusercontent.com/sghhqzkg4m-debug/prd-to-design/main/install.sh | bash
```

安装脚本会校验归档的 SHA-256，然后将以下五个 Skill 分别放入目标平台的技能目录：

- `prd-to-design`：入口、需求与交互分析、HTML／飞书交付编排
- `competitive-analysis`：独立竞品研究、功能体验评价与报告；主 Skill 触发时也会调用
- `user-journey`：独立用户旅程分析与文档；主 Skill 调用时完整嵌入需求文档
- `sangfor-cloud-console`：深信服控制台页面与组件参考
- `beautiful-feishu-whiteboard`：飞书白板视觉与可编辑图形

安装后开启一个新的 Codex 会话，使用 `$prd-to-design`。如果已安装同名 Skill 且内容相同，脚本会跳过；内容不同且有交互终端时，会列出冲突项并询问是否备份和替换。选择否会在改动任何 Skill 前停止。没有交互终端时也会停止；只有用户明确同意替换后，才应加 `--force` 重试。旧版本备份在目标技能目录的 `.backup/` 下。

也可以单独使用 `$competitive-analysis` 生成竞品功能体验研究文档。主 Skill 仅在研究触发时调用它，并同时交付需求文档和独立竞品分析文档；未触发时仍只交付需求文档。

旧版安装留下的独立 `prd-to-knowledge` 和 `prd-to-ui-spec` 不再是本仓库的依赖；更新脚本不会删除它们。普通需求分析默认交付 HTML；仅当用户要求 Markdown 作为交付物时才将其列入最终交付。触发竞品研究时，额外交付独立竞品分析文档；有飞书目标时仍以飞书设计文档为主交付。

也可以先克隆仓库，再执行 `bash install.sh --source-dir .`。这种方式使用仓库内的归档，不会再次下载。

## 环境能力

浏览器核查需要当前环境提供可用的浏览器能力；若使用 `browser-act`，需按其自身说明另行安装与授权。竞品研究需要可访问的实际产品界面或可靠资料；证据不足时会标明缺口，不编造体验分。`agents/openai.yaml` 是 Codex 元数据；TRAE 通过各目录的 `SKILL.md` 加载技能。

飞书同步需要使用者连接可写入飞书文档和白板的工具，并拥有目标文档的编辑权限。白板 Skill 的原始流程使用已安装并登录的 `@larksuite/cli`；也可由环境中等价的飞书白板工具完成。安装此仓库不会自动配置飞书账号或权限。本地校验脚本需要 Node.js。

`beautiful-feishu-whiteboard` 原作者为 Zara Zhang，按归档内的 MIT License 分发。

用户旅程可单独使用 `$user-journey`，默认生成自包含旅程 HTML；主 Skill 需要旅程时会自动调用，并将完整结果放在原需求文档中，默认不增加独立旅程交付。

主 Skill 已更名为 `prd-to-design`。检测到旧目录 `prd-to-feishu-design` 时，安装器会将其列为迁移确认项；确认后备份旧目录并安装新名称，避免同时加载两份主 Skill。旧名称不再作为调用入口，请改用 `$prd-to-design`。非交互安装遇到旧名称会停止，只有用户同意迁移后才使用 `--force`。
