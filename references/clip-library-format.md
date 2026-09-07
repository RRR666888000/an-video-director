# 本地素材库工具与格式

`scripts/clip_library.py` 用 Python 标准库维护本地 JSON；探测需 `ffprobe`，单段裁切另需 `ffmpeg` 和 H.264/AAC 编码器。它不负责转写、自动看视频、推断语义或判断平台是否审核通过。复核状态是操作者对实际完成工作的记录，不是脚本验证出的观看事实。

## 命令

在 Skill 目录执行下列示例。`PROJECT` 是另一个项目目录；所有素材库、标注、计划、转写、成片都保留在该项目中，不加入 Skill 仓库。工具拒绝把素材库或裁切结果写入自身 Skill 目录；发布前仍须检查其他副本和 Git 历史。

```sh
python3 scripts/clip_library.py --library "$PROJECT/library.json" ingest "$PROJECT/raw"
python3 scripts/clip_library.py --library "$PROJECT/library.json" ingest "$PROJECT/raw" --recursive
python3 scripts/clip_library.py --library "$PROJECT/library.json" annotate --input "$PROJECT/annotations.json"
python3 scripts/clip_library.py --library "$PROJECT/library.json" inspect --role evidence --status usable
python3 scripts/clip_library.py --library "$PROJECT/library.json" coverage --source-id SOURCE_ID --stage transcript --start 0 --end 120 --note "本区间转写文本已核；未完成视听复核"
python3 scripts/clip_library.py --library "$PROJECT/library.json" check-plan --input "$PROJECT/plan.json"
python3 scripts/clip_library.py --library "$PROJECT/library.json" cut --clip-id CLIP_ID --output "$PROJECT/modules/example.mp4"
```

目录默认只扫描直接子文件；`--recursive` 才含子目录。登记以 SHA-256 识别同一内容，同内容不同文件名作为来源别名；文件内容变更产生新 ID。媒体无法读取或探测失败会保留失败/待核记录，不允许对未知时长标片。原片不改名、不移动、不删。只有显式登记的本地文件会被读取；脚本无上传功能。

所有命令输出 JSON。成功退出码为 0；计划未通过为 2；参数、文件或执行错误为 1。批量登记可部分成功，必须检查输出和 `failures/probe_status`，不能只凭退出码宣称全量完成。素材库按一次命令原子写入；**同一个库顺序更新，不要并发写入**。

## 标注输入

`annotations.json` 是对象数组。以下为虚构格式例，ID 必须替换为 `ingest` 的实际结果，时间必须在原片内。

```json
[
  {
    "source_id": "SOURCE_ID",
    "start_s": 10.0,
    "end_s": 19.0,
    "product_identity": ["bag_a_v1"],
    "topic": ["快取钥匙"],
    "content_roles": ["hook", "experience", "evidence"],
    "evidence_types": ["observed_action"],
    "emotional_state": ["neutral"],
    "semantic_complete": "complete",
    "context_dependency": ["standalone"],
    "timeliness": "stable",
    "use_status": "usable",
    "review_status": "av_checked",
    "review_note": "示例：复核者、日期、实际观看并听完的区间、核对结果；执行时填写真实记录",
    "original_meaning": "说明钥匙位置并连续取出",
    "visible_action": "手从外格取出钥匙",
    "claim_scope": "只支持本次装取动作，不证明所有场景都更快",
    "duplicate_group_id": "key_access_a"
  }
]
```

完整枚举见 [词表](clip-taxonomy.json)。未填写的状态安全落为 `candidate/proposed/uncertain/unknown`，不自动补成可用。`usable` 要求 `av_checked`；`transcript_checked` 与 `av_checked` 要有复核说明。工具不能替代这次复核。自由字段可记录原意、动作、来源、用途及限制；不会被脚本自动理解。

`clip_id` 由源 ID 与时间窗稳定生成；相同输入重复导入不增加版本。修改标签保留旧标注历史；修改切点生成新 ID，可在自由字段 `supersedes_clip_id` 关联旧段。一次导入先全部验证，再变更素材库。

`coverage` 的 `proposed/transcript/av` 区间分别合并去重；标注导入登记选段范围，复核标注还登记相应复核范围。全量转写只增加文本覆盖，不变成全量视听完成。`inspect` 提供每源初标、已复核、未处理秒数及独立文本覆盖；未知时长留 `null`。这些都是记录值，不能把填写进度当作看过原片的证据。

## 计划输入与限制

```json
{
  "direction_id": "D01",
  "variant_id": "V01",
  "purpose": "让有快取需求的人进直播间看同款演示",
  "hypothesis": "完整装取动作比空泛形容更能解释使用价值",
  "target_product_id": "bag_a_v1",
  "segments": [
    {"clip_id": "CLIP_ID", "actual_role": "experience", "relation": "same_product"}
  ]
}
```

每段仍须人工核对承诺、依据范围、拼接因果、字幕原意和实际落地页/直播承接。程序仅检查已有记录和源文件：

- 目标、假设、片段及本次作用齐全；若 `actual_role` 不在候选标签中，须用 `role_reason` 说明新作用。
- 片段为 `usable/av_checked/complete/stable`，且有复核说明、合法时码、未改变的原片哈希。
- 特定商品计划要求段内唯一商品与目标一致。品类计划把 `target_product_id` 设 `null`；已识别商品的每段需 `relation: category_example` 及 `relation_note` 解释身份和主张关系。涉及特定商品的特点/体验/证据等不能缺少商品身份。
- `general_visual` 仅用于 `actual_role: broll` 且有 `relation_note` 的补充画面，不能用来绕过跨款证据检查。
- 非独立语境要在该段加 `resolved_context: ["支持片段ID"]` 和 `context_resolution_note`，支持片段必须出现在计划中；邻句依赖还要求相邻。是否真正补齐含义，仍需人看原片和顺序确认。
- 当前版本保守拒绝 `time_bound/expired/unknown`。活动或价格即使核实仍属有时限，不能为了过检查改成 `stable`。此类内容应独立核验有效期并走人工制作审查；该版本不输出自动通过。

`structural_check_passed: true` 只表示这些结构与记录检查通过，不代表声画已验收、内容合规、平台审核通过、用户会进房或会成交。

## 裁切与后续混剪

`cut` 可从任何已登记片段导出模块供复核，不把模块自动升级为可投成片；输出状态固定为 `exported_pending_visual_and_audio_review`。裁切使用原片秒数、重新编码和可选原音轨，保留源画幅，不为无声素材伪造原声。现有输出不会被覆盖；输出前后校验原片哈希并核对导出时长。

本版本**不包含自动转写、字幕、音乐选择、混剪渲染或剪映控制器**。组片计划确定后，由当前可用制作工具读取模块和计划执行；按 [制作验收](production.md) 核查每条成片。没有生成媒体时，交付应明确是素材登记/标注/计划，不能称已剪好。
