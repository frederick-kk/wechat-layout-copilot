# 公众号排版外挂

30套组件Skill，让AI看懂你想要的效果，再替你动手排版。

[在线体验30种效果](https://frederick-kk.github.io/wechat-layout-copilot/) · [下载完整组件库](https://github.com/frederick-kk/wechat-layout-copilot/releases/latest/download/wechat-layout-copilot.zip) · [选择单项Skill](#30个入口)

把正文、素材和参考要求交给AI，让它读取相应组件的Skill，检查缺项，生成可修改的组件或操作秀米完成排版。

2026-11-13扩展为30个组件入口。本轮增加十一种效果，每项均含独立Skill、JSON输入示例、生成器、片段和预览。各组件可单独使用，也可整包读取。

各组件的实际测试范围见下表与调研记录。公众号同步与真实手机微信触摸按各组件继续验证。

## 怎么开始

1. 打开在线预览，点按、长按或滑动，挑选适合正文的效果。
2. 点击该效果下的“下载此Skill”，解压后把整个文件夹交给能读取本地文件的AI。需要整套时下载完整组件库，从根目录 [SKILL.md](SKILL.md) 开始。
3. 提供正文、素材和个人风格，AI按组件说明生成结果或通过浏览器操作秀米，再检查实际草稿。

可以这样交代任务。

> 请读取我提供的组件文件夹里的SKILL.md。我会提供正文、参考文章和素材，请先确认所需材料，再沿用我的风格完成组件及排版。完成后告诉我用了哪些组件、分别放在哪一段，以及哪些效果还需要在秀米和手机上检查。

需要制作头像入口时，提供目标公众号名称或文章链接，由 AI 根据当前登录与原生入口取得对应名片。需要进入秀米时，准备浏览器工具与自己的登录状态。脚本采用 Python 3.10+ 标准库，所需参数和实际文件位置见各组件。

## 让AI下次继续用

读者确认效果后，可让AI把自己的配色、字级、间距、常用组件和触发条件整理进个人风格文件或项目流程，并指定后续任务读取这个文件。例如先问后答的短内容采用点击揭秘，关键时间节点采用时间线，多张图片采用图集。

> 请把这次我确认的排版规则整理进我指定的个人风格文件，写清适用场景、组件名称、所需素材和检查步骤。以后排版时先读取这些规则，再结合正文选择组件。

默认自动发现取决于所用AI工具的Skill安装机制。提供文件夹并明确让AI读取，可直接开始使用。

## 30个入口

| 组件 | 做什么 | 当前完成范围 |
|---|---|---|
| [头像跳转](skills/wechat-avatar-profile/SKILL.md) | 原生公众号名片与可见头像结合 | 参数化脚本、合成输入与缺项测试。新组件手机点击待测 |
| [SVG 描边](skills/wechat-svg-drawline/SKILL.md) | 小型分隔线逐渐画出 | 可生成片段与预览，Ego lite 浏览器播放通过 |
| [点击揭秘](skills/wechat-svg-click-reveal/SKILL.md) | 固定画面内点击显示短内容 | 可生成片段与预览，真实点击和320/375px窄屏检查通过 |
| [多热区点击与返回](skills/wechat-svg-hotspots/SKILL.md) | 点开不同注释，再返回总图 | 生成器、双实例、窄屏点击及秀米保存重开后交互通过 |
| [点击旋转切换](skills/wechat-svg-switch/SKILL.md) | 短卡片循环切换 | 生成器、两轮循环、窄屏及秀米保存重开后交互通过 |
| [点击逐层掉落](skills/wechat-svg-layer-peel/SKILL.md) | 按顺序揭晓，最后一张保留 | 生成器、末页停留、窄屏及秀米保存重开后交互通过 |
| [秀米图集](skills/wechat-xiumi-gallery/SKILL.md) | 横滑HTML、点击SVG图集与原生操作 | 新生成器通过320/375px鼠标检查，新输出的秀米保存待测 |
| [秀米 SVG 布局](skills/wechat-xiumi-svg-layout/SKILL.md) | 展开、开窗、掉落、长按与局部热区 | 官方做法与素材清单，各高级效果待逐项实测 |
| [正文排版](skills/wechat-layout-blocks/SKILL.md) | 标题、步骤、引用、表格、图片图注 | 可生成片段与预览，文字保留、列数及320/375px预览通过 |
| [双扇开窗](skills/wechat-svg-open-window/SKILL.md) | 双侧打开与合上，反复查看 | 本地与秀米重开阅读页320/375px，两轮开合通过 |
| [长按显影](skills/wechat-svg-press-reveal/SKILL.md) | 按住显影，松开复原 | 本地与秀米重开阅读页320/375px，按住和松开通过 |
| [长按轮播定格](skills/wechat-svg-hold-cards/SKILL.md) | 按住轮播，松手停留 | 本地与秀米重开阅读页320/375px，轮播与定格通过 |
| [擦拭对比](skills/wechat-svg-wipe-compare/SKILL.md) | 按钮控制正向和反向擦拭 | 本地与秀米重开阅读页320/375px，正反擦拭通过 |
| [单题答题](skills/wechat-svg-quiz/SKILL.md) | 选择答案，显示反馈与重选 | 本地与秀米重开阅读页320/375px，所有选项与重选通过 |
| [分支故事](skills/wechat-svg-story-branches/SKILL.md) | 连续选择与不同结局 | 本地与秀米重开阅读页320/375px，四条路径与重开通过 |
| [轨迹运动](skills/wechat-svg-motion-path/SKILL.md) | 图形沿指定路线运动，可重播 | 本地与秀米重开阅读页320/375px，运动终点与重播通过 |
| [逐字打印](skills/wechat-svg-typewriter/SKILL.md) | 短文逐字显现，可重播 | 本地与秀米重开阅读页320/375px，全部字簇与重播通过 |
| [镜头放大](skills/wechat-svg-zoom-detail/SKILL.md) | 同图放大指定区域，再返回 | 本地与秀米重开阅读页320/375px，放大与返回通过 |
| [数据图表](skills/wechat-svg-data-chart/SKILL.md) | 用户数值驱动柱形动画，保留完整值 | 本地与秀米重开阅读页320/375px，柱高与重播通过 |
| [双面翻牌](skills/wechat-svg-flip-card/SKILL.md) | 压缩翻面，阅读背面后翻回 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [拆信与收信](skills/wechat-svg-envelope/SKILL.md) | 打开封口、抽出信纸、收回 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [百叶窗](skills/wechat-svg-blinds/SKILL.md) | 多条窗叶错峰展开与合上 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [探照灯](skills/wechat-svg-spotlight/SKILL.md) | 按钮选择局部光圈与全景 | 光圈与文字已复核，合并总页320/375px切换通过 |
| [多层视差](skills/wechat-svg-parallax/SKILL.md) | 按钮驱动远近景不同速度位移 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [手风琴面板](skills/wechat-svg-accordion-panels/SKILL.md) | 点击面板展开，其余收窄 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [抽拉标签](skills/wechat-svg-pull-tab/SKILL.md) | 点按横向抽出信息条，再收回 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [唱片启停](skills/wechat-svg-vinyl/SKILL.md) | 唱片旋转的视觉启停 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [拼图拼合](skills/wechat-svg-puzzle-assemble/SKILL.md) | 点按播放碎片拼合展示 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [动态时间线](skills/wechat-svg-timeline/SKILL.md) | 时间线与阶段信息依次出现 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |
| [点按礼花](skills/wechat-svg-confetti/SKILL.md) | 粒子散开、祝福亮起、重播 | 独立预览与合并总页320/375px交互通过，秀米保存待测 |

## 总预览复核

2026-11-13已用Ego lite检查30项总页。1280、375、320px下目录完整、画面无横向溢出，新增十一项在合并页的两种窄屏宽度均通过交互检查。探照灯新版光圈中的文字显示完整。

新增十一项的秀米保存重开、公众号同步与真实手机微信触摸仍按组件继续验证。

## 直接看示例

- [整包交互预览](examples/preview.html)
- [SVG 描边预览](skills/wechat-svg-drawline/examples/preview.html)
- [点击揭秘预览](skills/wechat-svg-click-reveal/examples/preview.html)
- [正文排版预览](skills/wechat-layout-blocks/examples/preview.html)
- [正文组件输入示例](skills/wechat-layout-blocks/examples/blocks.json)
- [头像入口使用请求](skills/wechat-avatar-profile/examples/request.md)

HTML 示例下载后可在浏览器打开。微信原生名片的点击行为，需要在公众号环境中检查。

根目录 [index.html](index.html) 转到交互预览。修改组件示例后，执行 `python scripts/build_preview.py` 重建目录页面。为自己的仓库构建时，可用 `--repository owner/name` 更新页面中的仓库与下载链接。

需要生成发布下载包时，执行 `python scripts/build_downloads.py`，默认输出到 `dist/`。每个单项ZIP包含完整Skill目录，整包ZIP包含总入口和全部组件。重复构建时用 `--overwrite` 明确替换已生成的下载包。

## 调研与文章准备

[调研与复刻计划](docs/调研与复刻计划.md) 记录当前编辑器入口、来源、组件优先级、测试结果及接下来的验证顺序。

这批示例以可替换素材和主题参数组织。使用者提供自己的账号、文章和图片。生成器采用 Python 3.10+ 标准库，导出的交互片段使用 SVG 与 SMIL。图集也可输出普通横滑 HTML。

组件文件可由 AI 指定读取。自动发现取决于使用者是否已安装到其工具的 Skill 目录。浏览器播放、秀米保存重开、公众号同步与手机点击的完成情况见调研记录。

## 许可

本项目以 [MIT License](LICENSE) 提供，组件示例采用原创矢量与测试素材。使用自己的账号资料、正文和图片，按相应平台的实际结果检查交付。
