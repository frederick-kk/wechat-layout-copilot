# 公众号排版外挂

50套组件Skill，先看示例选效果，再让AI替你排版。

[首次配置下载上手Skill](https://github.com/frederick-kk/wechat-layout-copilot/releases/download/v0.7.0/wechat-layout-starter.zip) · [读取完整上手流程](workflows/wechat-layout-starter/SKILL.md)

让AI检查环境、学习你的旧稿、引导选择组件，再生成属于你的本地排版Skill。以后提供正文，按个人风格完成排版与草稿保存。

[查看50款品牌演示](examples/brand-gallery.html) · [下载完整组件库](https://github.com/frederick-kk/wechat-layout-copilot/releases/download/v0.7.0/wechat-layout-copilot.zip) · [查看原版交互目录](examples/preview.html) · [选择单项Skill](#50个入口)

[直接看本轮新增组件](examples/brand-gallery.html#new-components)

v0.7.0提供50款品牌示例，采用纸纹、暖橙和橙帽Fred的示例风格。静态原生排版按实际画面提供静帧或GIF。每项包含可读的Skill、本地HTML模板、独立素材和品牌样式JSON。

已有600px浏览器操作／播放采集记录50／50项、320／375px布局检查50／50项。头像入口另附[手机微信真实跳转录像](skills/wechat-avatar-profile/examples/real-demo.html)，秀米原生布局提供操作示意。各组件的目标账号保存、同步与手机检查范围见下表。

## 怎么开始

### 第一步，首次使用先启动上手 Skill

1. [下载上手配置 Skill](https://github.com/frederick-kk/wechat-layout-copilot/releases/download/v0.7.0/wechat-layout-starter.zip)。
2. 完整解压，保留 `wechat-layout-starter` 整个文件夹。
3. 在 Codex 或能读取本地文件的 AI 工具中新开对话，把解压后的文件夹路径发给它，再复制下面这句话。

> 请读取我刚提供的文件夹中的 SKILL.md，使用 wechat-layout-starter 带我完成公众号排版的首次配置。先检查环境，再学习我的旧文章风格，带我选择组件并生成个人排版 Skill。

已经安装过这个 Skill 时，可以直接输入。

> 用 $wechat-layout-starter 帮我配置公众号排版。

接下来跟着 AI 的引导操作即可。它会检查已有环境，帮助接通 Ego lite、微信公众平台和秀米，读取你提供的旧文章，再带你从50款效果中选择组件。下载所选单项ZIP或使用完整组件库后，完成小样微调，AI会打包你的个人排版 Skill，以后按这套配置处理正文与草稿。

### 已有配置时直接使用组件

1. 打开GIF总览，选择适合正文的效果，再点“打开可操作演示”体验点击、长按或滑动。
2. 点击该效果下的“下载此Skill”，解压后把整个文件夹交给能读取本地文件的AI。需要整套时下载完整组件库，从根目录 [SKILL.md](SKILL.md) 开始。
3. 提供正文、素材和个人风格，AI按组件说明生成结果或通过浏览器操作秀米，再检查实际草稿。

可以这样交代任务。

> 请读取我提供的组件文件夹里的SKILL.md。我会提供正文、参考文章和素材，请先确认所需材料，再沿用我的风格完成组件及排版。完成后告诉我用了哪些组件、分别放在哪一段，以及哪些效果还需要在秀米和手机上检查。

需要制作头像入口时，提供目标公众号名称或文章链接，由 AI 根据当前登录与原生入口取得对应名片。需要进入秀米时，准备浏览器工具与自己的登录状态。脚本采用 Python 3.10+ 标准库，所需参数和实际文件位置见各组件。

## 让AI下次继续用

读者确认效果后，可让AI把自己的配色、字级、间距、常用组件和触发条件整理进个人风格文件或项目流程，并指定后续任务读取这个文件。例如先问后答的短内容采用点击揭秘，关键时间节点采用时间线，多张图片采用图集。

> 请把这次我确认的排版规则整理进我指定的个人风格文件，写清适用场景、组件名称、所需素材和检查步骤。以后排版时先读取这些规则，再结合正文选择组件。

默认自动发现取决于所用AI工具的Skill安装机制。提供文件夹并明确让AI读取，可直接开始使用。

## 50个入口

| 组件 | 做什么 | 当前完成范围 |
|---|---|---|
| [头像跳转](skills/wechat-avatar-profile/SKILL.md) | 原生公众号名片与可见头像结合 | 参数化与缺项测试，另附用户提供的手机微信完整跳转实录 |
| [拆信与收信](skills/wechat-svg-envelope/SKILL.md) | 打开封口、抽出信纸、收回 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [双面翻牌](skills/wechat-svg-flip-card/SKILL.md) | 压缩翻面，阅读背面后翻回 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [多层视差](skills/wechat-svg-parallax/SKILL.md) | 按钮驱动远近景不同速度位移 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [唱片启停](skills/wechat-svg-vinyl/SKILL.md) | 唱片旋转的视觉启停 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [抽拉标签](skills/wechat-svg-pull-tab/SKILL.md) | 点按横向抽出信息条，再收回 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [动态时间线](skills/wechat-svg-timeline/SKILL.md) | 时间线与阶段信息依次出现 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [双扇开窗](skills/wechat-svg-open-window/SKILL.md) | 双侧打开与合上，反复查看 | 本地与秀米重开阅读页320/375px，两轮开合通过 |
| [擦拭对比](skills/wechat-svg-wipe-compare/SKILL.md) | 按钮控制正向和反向擦拭 | 本地与秀米重开阅读页320/375px，正反擦拭通过 |
| [镜头放大](skills/wechat-svg-zoom-detail/SKILL.md) | 同图放大指定区域，再返回 | 本地与秀米重开阅读页320/375px，放大与返回通过 |
| [点击揭秘](skills/wechat-svg-click-reveal/SKILL.md) | 固定画面内点击显示短内容 | 可生成片段与预览，真实点击和320/375px窄屏检查通过 |
| [百叶窗](skills/wechat-svg-blinds/SKILL.md) | 多条窗叶错峰展开与合上 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [探照灯](skills/wechat-svg-spotlight/SKILL.md) | 按钮选择局部光圈与全景 | 光圈与文字已复核，合并总页320/375px切换通过 |
| [手风琴面板](skills/wechat-svg-accordion-panels/SKILL.md) | 点击面板展开，其余收窄 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [拼图拼合](skills/wechat-svg-puzzle-assemble/SKILL.md) | 点按播放碎片拼合展示 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [点按礼花](skills/wechat-svg-confetti/SKILL.md) | 粒子散开、祝福亮起、重播 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [多热区点击与返回](skills/wechat-svg-hotspots/SKILL.md) | 点开不同注释，再返回总图 | 生成器、双实例、窄屏点击及秀米保存重开后交互通过 |
| [点击旋转切换](skills/wechat-svg-switch/SKILL.md) | 短卡片循环切换 | 生成器、两轮循环、窄屏及秀米保存重开后交互通过 |
| [点击逐层掉落](skills/wechat-svg-layer-peel/SKILL.md) | 按顺序揭晓，最后一张保留 | 生成器、末页停留、窄屏及秀米保存重开后交互通过 |
| [长按显影](skills/wechat-svg-press-reveal/SKILL.md) | 按住显影，松开复原 | 本地与秀米重开阅读页320/375px，按住和松开通过 |
| [长按轮播定格](skills/wechat-svg-hold-cards/SKILL.md) | 按住轮播，松手停留 | 本地与秀米重开阅读页320/375px，轮播与定格通过 |
| [单题答题](skills/wechat-svg-quiz/SKILL.md) | 选择答案，显示反馈与重选 | 本地与秀米重开阅读页320/375px，所有选项与重选通过 |
| [分支故事](skills/wechat-svg-story-branches/SKILL.md) | 连续选择与不同结局 | 本地与秀米重开阅读页320/375px，四条路径与重开通过 |
| [轨迹运动](skills/wechat-svg-motion-path/SKILL.md) | 图形沿指定路线运动，可重播 | 本地与秀米重开阅读页320/375px，运动终点与重播通过 |
| [逐字打印](skills/wechat-svg-typewriter/SKILL.md) | 短文逐字显现，可重播 | 本地与秀米重开阅读页320/375px，全部字簇与重播通过 |
| [数据图表](skills/wechat-svg-data-chart/SKILL.md) | 用户数值驱动柱形动画，保留完整值 | 本地与秀米重开阅读页320/375px，柱高与重播通过 |
| [SVG 描边](skills/wechat-svg-drawline/SKILL.md) | 小型分隔线逐渐画出 | 可生成片段与预览，Ego lite 浏览器播放通过 |
| [秀米图集](skills/wechat-xiumi-gallery/SKILL.md) | 横滑HTML、点击SVG图集与原生操作 | 新生成器通过320/375px鼠标检查，新输出的秀米保存待测 |
| [正文排版](skills/wechat-layout-blocks/SKILL.md) | 标题、步骤、引用、表格、图片图注 | 可生成片段与预览，文字保留、列数及320/375px预览通过 |
| [秀米 SVG 布局](skills/wechat-xiumi-svg-layout/SKILL.md) | 展开、开窗、掉落、长按与局部热区 | 官方做法与素材清单，各高级效果待逐项实测 |
| [标签页联动图文](skills/wechat-svg-tabs/SKILL.md) | 切换标签，在同一画面中查看对应图文。 | 浏览器验证通过，平台范围见对应Skill |
| [分步操作向导](skills/wechat-svg-stepper/SKILL.md) | 依次完成操作步骤，也可返回前一步。 | 浏览器验证通过，平台范围见对应Skill |
| [多题计分测验](skills/wechat-svg-score-quiz/SKILL.md) | 逐题选择，答完后查看本次得分与反馈。 | 浏览器验证通过，平台范围见对应Skill |
| [多选统一提交](skills/wechat-svg-multi-select/SKILL.md) | 选择多个选项，再统一提交并查看反馈。 | 浏览器验证通过，平台范围见对应Skill |
| [勾选清单与进度](skills/wechat-svg-checklist/SKILL.md) | 逐项勾选事项，查看完成进度。 | 浏览器验证通过，平台范围见对应Skill |
| [点击配对连线](skills/wechat-svg-match-pairs/SKILL.md) | 按两列内容点击配对，查看连线结果。 | 浏览器验证通过，平台范围见对应Skill |
| [环形目标进度](skills/wechat-svg-progress-ring/SKILL.md) | 用真实目标与完成值展示环形进度。 | 浏览器验证通过，平台范围见对应Skill |
| [增减瀑布图](skills/wechat-svg-waterfall/SKILL.md) | 按顺序查看各项增减与最终合计。 | 浏览器验证通过，平台范围见对应Skill |
| [漏斗转化图](skills/wechat-svg-funnel/SKILL.md) | 按阶段展示真实数量与转化关系。 | 浏览器验证通过，平台范围见对应Skill |
| [雷达能力对比](skills/wechat-svg-radar/SKILL.md) | 在统一量程下比较多个维度的数据。 | 浏览器验证通过，平台范围见对应Skill |
| [多角色流程泳道](skills/wechat-svg-swimlane/SKILL.md) | 按角色分栏，查看流程交接与当前步骤。 | 浏览器验证通过，平台范围见对应Skill |
| [文字弹幕墙](skills/wechat-svg-danmaku/SKILL.md) | 播放短句弹幕，保留静态可读内容。 | 浏览器验证通过，平台范围见对应Skill |
| [多页翻书](skills/wechat-svg-book/SKILL.md) | 按页翻看图文，再返回前页。 | 浏览器验证通过，平台范围见对应Skill |
| [卡片排序题](skills/wechat-svg-word-order/SKILL.md) | 按顺序选择卡片，排完三项查看结果。 | 浏览器验证通过，平台范围见对应Skill |
| [横向宽表](skills/wechat-layout-wide-table/SKILL.md) | 在窄屏中横向查看完整表格。 | 原生HTML示例，发布按目标平台检查 |
| [访谈对话气泡](skills/wechat-layout-dialogue/SKILL.md) | 用原生文字呈现人物对话与问答。 | 原生HTML示例，发布按目标平台检查 |
| [图文边注](skills/wechat-layout-annotations/SKILL.md) | 把图片、注释与对应正文排在一起。 | 原生HTML示例，发布按目标平台检查 |
| [杂志跨栏图文](skills/wechat-layout-magazine/SKILL.md) | 通过图文层级和跨栏组织长内容。 | 原生HTML示例，发布按目标平台检查 |
| [纵向FAQ展开](skills/wechat-xiumi-faq/SKILL.md) | 逐项展开常见问题，保持纵向阅读。 | 原生HTML示例，发布按目标平台检查 |
| [视频封面卡片](skills/wechat-xiumi-video-card/SKILL.md) | 用封面与原生视频入口承接播放内容。 | 原生HTML示例，发布按目标平台检查 |

## 总预览复核

2026-11-13已用Ego lite检查30项总页。1280、375、320px下目录完整、画面无横向溢出，新增十一项在合并页的两种窄屏宽度均通过交互检查。探照灯新版光圈中的文字显示完整。

新增十一项的秀米保存重开、公众号同步与真实手机微信触摸仍按组件继续验证。

## 直接看示例

- [Fred 纸纹暖橙插画试做 · 拆信、探照灯、三层视差](examples/artwork-pilots.html)
- [整包交互预览](examples/preview.html)
- [SVG 描边预览](skills/wechat-svg-drawline/examples/preview.html)
- [点击揭秘预览](skills/wechat-svg-click-reveal/examples/preview.html)
- [正文排版预览](skills/wechat-layout-blocks/examples/preview.html)
- [正文组件输入示例](skills/wechat-layout-blocks/examples/blocks.json)
- [头像入口使用请求](skills/wechat-avatar-profile/examples/request.md)

HTML 示例下载后可在浏览器打开。微信原生名片的点击行为，需要在公众号环境中检查。

根目录 [index.html](index.html) 打开组件总览。完整整包解压后可直接打开，组件文件已经包含在包内。

公开版先执行 `python scripts/build_preview.py` 重建原版预览，再执行 `python scripts/build_brand_catalog.py --avatar assets/brand/avatar.webp --overwrite` 重建品牌目录。页面采用v0.7.0公开下载地址。使用 `python scripts/build_downloads.py --out-dir dist/v0.7.0` 生成本次52个发布包。

其他仓库可用 `--repository owner/name` 或品牌目录的 `--download-base` 指定已发布地址。本地预览可用 `--downloads-dir` 指向已有ZIP目录。

`build_downloads.py` 默认输出到 `dist/`。每个单项ZIP包含完整Skill目录，整包ZIP包含总入口和全部组件。采用本地下载按钮时，可用 `--portable-local` 将整包内的ZIP按钮改为已包含的Skill入口。重建预览后再加 `--overwrite` 重打下载包，使包内页面与当前目录一致。

## 调研与文章准备

[调研与复刻计划](docs/调研与复刻计划.md) 记录当前编辑器入口、来源、组件优先级、测试结果及接下来的验证顺序。

这批示例以可替换素材和主题参数组织。使用者提供自己的账号、文章和图片。生成器采用 Python 3.10+ 标准库，导出的交互片段使用 SVG 与 SMIL。图集也可输出普通横滑 HTML。

组件文件可由 AI 指定读取。自动发现取决于使用者是否已安装到其工具的 Skill 目录。浏览器播放、秀米保存重开、公众号同步与手机点击的完成情况见调研记录。

## 许可

本项目以 [MIT License](LICENSE) 提供，组件示例采用原创矢量与测试素材。使用自己的账号资料、正文和图片，按相应平台的实际结果检查交付。
