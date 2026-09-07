# an-video-director · 内容编导

从“我不知道拍什么”，到账号内容体系、选题脚本、直播切片分类和混剪计划。

这是一份中文 **Agent Skill**：把编导的判断方法、参考资料和本地素材工具交给 AI 助手。适合创作者、工作室和直播电商团队，也适合普通生活、知识和个人 IP 内容。**核心功能不需要原作者的课程、账号或私人资料。**

[直接下载 ZIP](https://github.com/RRR666888000/an-video-director/archive/refs/heads/main.zip) · [AI 入口 SKILL.md](SKILL.md) · [批量素材操作](references/clip-library-format.md) · [反馈问题](https://github.com/RRR666888000/an-video-director/issues)

## 能帮你做什么

| 你遇到的问题 | Skill 引导助手完成的工作 |
|---|---|
| 账号内容很散，不知道定位 | 看现有作品和观众反馈，梳理内容线与试行方向 |
| 没有选题，文案不像自己 | 从真实经历、事件和可拍条件发展选题与脚本 |
| 工作室和个人 IP 不知道怎么分工 | 区分事件、视角、表达者与制作交接 |
| 直播切片很多，不知道怎么用 | 登记去重、分段、多标签标注、记录语境与复核范围 |
| 想把素材重新混剪 | 判断每段在本条中的作用，列组片计划、缺口和制作要求 |
| 拍完效果不好 | 对齐原目标、实际作品与数据，提出下一轮可验证的改动 |

**能力边界：**脚本能登记素材、检查标注/计划、导出单段视频；不自带自动看视频、语音转写、字幕配乐、完整混剪渲染或剪映控制。语义分类与声画复核需要具备相应工具的 Agent 或人类完成。生成了计划不等于剪好了成片，检查通过不等于平台审核通过或一定有效。

## 人类怎么下载安装

### 方法一：不用命令行

1. 点击上方 **直接下载 ZIP**；也可在仓库页点击绿色 **Code → Download ZIP**。
2. 解压，将 `an-video-director-main` 文件夹改名为 **`an-video-director`**。
3. 将整个文件夹放入下面与你的工具对应的位置。不要只复制 `SKILL.md`，不要多套一层文件夹。
4. 打开工具并使用下方示例。若未识别，重新打开会话或重启工具。

| 工具 | 个人安装位置 | 只在一个项目使用 |
|---|---|---|
| Codex | `~/.agents/skills/an-video-director/` | `项目目录/.agents/skills/an-video-director/` |
| Claude Code | `~/.claude/skills/an-video-director/` | `项目目录/.claude/skills/an-video-director/` |
| 其他 Agent | 使用该工具官方支持的 Skill 目录或导入入口 | 没有统一安装路径，按宿主说明操作 |

`~` 表示你自己的用户主目录；Windows 通常对应 `%USERPROFILE%`。macOS 访达可按 `Command + Shift + G` 输入目录，Windows 资源管理器可在地址栏输入 `%USERPROFILE%\.agents\skills`（Codex）。目录不存在时新建。部分 Codex 环境由安装器管理在 `~/.codex/skills`；沿用实际安装器返回的位置，避免两处重复安装同名技能。

最终应能找到 `…/an-video-director/SKILL.md`，其旁边还有 `references/` 和 `scripts/`。

### 方法二：用 Git 下载

以下命令适用于 macOS、Linux 或 Git Bash，需已安装 Git。目标目录若已有版本，先看“更新”，不要覆盖本地改动。

Codex 个人安装：

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/RRR666888000/an-video-director.git "$HOME/.agents/skills/an-video-director"
```

Claude Code 个人安装：

```sh
mkdir -p "$HOME/.claude/skills"
git clone https://github.com/RRR666888000/an-video-director.git "$HOME/.claude/skills/an-video-director"
```

只选与你使用的工具对应的一种即可。公开下载无需作者账号或访问令牌。主分支下载的是当时的最新内容；需要复现版本时记录提交 SHA。

## AI／Agent 怎么下载安装

把下面整段发给**有网络和本地文件操作权限的 Agent**：

```text
请帮我安装这个 Skill：
https://github.com/RRR666888000/an-video-director

先读取仓库 README.md 和 SKILL.md，确认内容和当前宿主支持的安装方式。
这份仓库根目录本身就是 an-video-director Skill，不是仓库里的另一个子目录。
若当前 Codex 提供 skill-installer，优先使用它从该仓库根目录安装；
否则完整下载或克隆，并放入当前宿主支持的个人 skills 目录，目录名为 an-video-director。
保持 SKILL.md、references、scripts、agents 等配套文件完整。
发现同名技能或本地修改时先说明，保留备份，不直接覆盖。
不要下载作者的其他仓库，不读取或上传私人素材，不修改无关配置。
安装后回读 SKILL.md，报告实际安装路径和提交 SHA（可获取时），
再确认宿主是否能发现技能；不能确认自动发现时明确说明。
若 Python 可用，运行 course_lookup.py 的 route 示例验证参考路径；
需要做视频登记或裁切时再检查 ffprobe/ffmpeg。
```

Codex 内也可直接说：

```text
$skill-installer 请从 https://github.com/RRR666888000/an-video-director 安装根目录 Skill，名称为 an-video-director。
```

**只会聊天、不能写文件的 AI 无法替你安装。**可以让它阅读本仓库并在本次对话中参考方法，但这不等于永久安装；网页阅读也不会自动赋予视频处理能力。

## 安装后怎么用

Codex 中可用 `$an-video-director`，Claude Code 中可用 `/an-video-director`；其他宿主使用其技能选择器或明确要求加载本技能。自然描述匹配时，支持自动发现的宿主也可能自行选用。

**找选题：**

```text
使用 an-video-director。我拍普通生活内容，不卖货，每周能拍两小时。
这是我最近的三个经历：……请帮我选一个最值得拍的方向，并写出具体镜头和自然口播。
```

**批量整理直播切片：**

```text
使用 an-video-director。这批视频在我指定的素材目录：……
先登记、去重、分类，不剪片。
逐段说明讲了什么、商品身份、候选作用、缺少的上下文和复核范围。
把可用方向、备用片段和缺口列出来，不把同义版本算成独立方向。
素材库保存在另一个项目目录：……；保留所有原片。
```

**开始制作：**

```text
使用 an-video-director，基于已确认的素材库做两条不同方向的视频。
用途：……；目标时长和画幅：……；输出目录：……。
先说明每段在本条中的实际作用，再按可用工具完成制作。
缺素材就指出缺口，不虚构原话。交付能播放的文件并说明实际检查范围；
若当前工具只能完成计划，请明确说这是计划。
```

第一次可以只给几段素材试用，确认分类和表达符合你的需求后再扩大批量。素材、转写、项目记录、经营数据和成片都放在**本 Skill 文件夹之外**。

## 依赖与自检

| 工作 | 需要什么 |
|---|---|
| 账号策划、选题、脚本与制作建议 | 能阅读 Skill 的 AI；不要求 Python |
| 参考路由、本机可选资料检索 | Python 3.10+，仅标准库 |
| 登记视频时长、画幅、音轨 | Python 与 `ffprobe` |
| 导出单段 MP4 | 另需 `ffmpeg`，支持 H.264/AAC 编码 |
| 理解视频、转写、字幕、配乐和完整成片 | 宿主另外提供的工具与对应访问权限 |

[Python 下载](https://www.python.org/downloads/) · [FFmpeg 下载](https://ffmpeg.org/download.html)。Windows 可把下面的 `python3` 换为已经安装的 `py -3`。安装媒体工具后确认它们能在终端中找到。

在下载后的 Skill 根目录执行：

```sh
python3 scripts/course_lookup.py route '一堆直播切片怎么分类混剪'
python3 scripts/clip_library.py --help
python3 -m unittest discover -s tests -v
```

第一条应返回相关参考文件，第二条应显示命令帮助。测试使用临时生成的合成媒体；没有 FFmpeg 时媒体测试可能跳过，需要看实际结果，不把跳过算通过。测试不代表真实素材的内容质量或平台审核结果。

批量操作的字段、标注示例和每条命令见 [工具与格式](references/clip-library-format.md)。`SOURCE_ID`、`CLIP_ID` 必须用自己登记后的实际 ID 替换，不能照抄占位符。同一个素材库顺序写入，不要让多个 Agent 同时修改。

## 文件结构

```text
an-video-director/
├── README.md                 人类下载、Agent 安装与使用说明
├── SKILL.md                  AI 的入口与任务路由
├── agents/openai.yaml        Codex 展示信息
├── references/               账号、选题、脚本、素材库、制作及复盘参考
├── scripts/
│   ├── course_lookup.py      参考路由与可选本机资料检索
│   └── clip_library.py       素材登记、标注、计划检查与单段裁切
└── tests/                    合成数据与媒体测试
```

## 更新与常见问题

- **Git 安装更新：**进入实际安装目录，先运行 `git status --short`。有本地修改先保留并处理；无修改再运行 `git pull --ff-only`，重新自检。
- **ZIP 安装更新：**先将旧版本备份到 skills 目录之外，再下载、解压、替换。个人资料始终单独保存。
- **找不到技能：**检查是否多套了 `an-video-director-main` 文件夹，确认 `SKILL.md` 在正确层级、宿主目录正确，必要时重启。不要在多个扫描目录重复安装。
- **提示缺课程配置：**普通策划和 `route` 不需要课程。只有 `list/search/read` 等可选原文检索才需要你自己有权使用的外部资料，见 [来源与配置](references/source-map.md)。
- **提示找不到 ffprobe/ffmpeg：**安装媒体依赖并检查环境路径；在此之前仍可做策划和文本工作。
- **能看到文件但没自动调用：**下载成功和宿主发现是两步。通过技能选择器或明确调用确认，不只看文件是否存在。
- **为什么没有一键完整混剪：**本版本提供编导方法、素材库与单段工具；完整制作能力由 Agent 所在环境提供。

## 数据、来源与反馈

本仓库只分发通用方法、词表、脚本和合成测试，不分发课程原文、私人案例、原视频、转写、经营数据或本机配置。附带脚本无网络上传功能；你所使用的 AI 服务如何处理素材，取决于该服务和你的设置。`an-video-director` 是沿用的调用名，不代表讲师官方产品，第三方原材料的权利不随本仓库转移。

本仓库供下载试用，当前未附通用开源许可证；不要据此推定已获得任意商业再分发或第三方材料的授权。

反馈请在 Issues 写清：使用工具、需求、实际结果、预期结果和可复现步骤。不要公开凭据、私人素材或客户信息，优先提供脱敏示例。

安装位置与调用方式参考：[Codex 官方技能文档](https://developers.openai.com/codex/skills) · [Claude Code 官方技能文档](https://code.claude.com/docs/en/skills)。不同宿主版本可能调整入口，以实际安装器与官方文档为准。
