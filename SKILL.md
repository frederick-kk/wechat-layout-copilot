---
name: wechat-layout-copilot
description: 为公众号文章选择头像、排版、图集和SVG交互组件，支持开窗、长按、答题、分支、擦拭、轨迹、逐字显示和图表等效果。检查素材缺项，调用对应生成器或秀米原生做法，再核对实际保存与交互。
metadata:
  version: "0.4.1"
---

# 公众号排版外挂

根据用户想要的效果选择下表中的入口。各组件可单独下载，也可一起使用。

| 要做的效果 | 读取入口 |
|---|---|
| 点击头像打开原生公众号名片 | [头像跳转](skills/wechat-avatar-profile/SKILL.md) |
| 手绘线条逐渐出现的小动效 | [SVG 描边](skills/wechat-svg-drawline/SKILL.md) |
| 固定画面内点击揭晓文字或图形 | [SVG 点击揭秘](skills/wechat-svg-click-reveal/SKILL.md) |
| 同一画面里点不同位置查看说明，再返回 | [多热区点击与返回](skills/wechat-svg-hotspots/SKILL.md) |
| 短卡片轻旋转切换，末张返回首张 | [点击旋转切换](skills/wechat-svg-switch/SKILL.md) |
| 逐层揭开内容，最后一层保留 | [点击逐层掉落](skills/wechat-svg-layer-peel/SKILL.md) |
| 横滑图片、点击切图，或在秀米制作原生图集 | [秀米图集](skills/wechat-xiumi-gallery/SKILL.md) |
| 在秀米制作展开、开窗、掉落、长按或局部热区 | [秀米原生SVG布局](skills/wechat-xiumi-svg-layout/SKILL.md) |
| 章节、步骤、引用、短表和图注 | [正文排版组件](skills/wechat-layout-blocks/SKILL.md) |
| 两扇窗打开露出内容，再合上重看 | [双扇开窗](skills/wechat-svg-open-window/SKILL.md) |
| 按住显现内容，松开或移出恢复 | [长按显影](skills/wechat-svg-press-reveal/SKILL.md) |
| 按住轮播，松手停在当前卡片 | [长按轮播定格](skills/wechat-svg-hold-cards/SKILL.md) |
| 点击按钮擦出前后对比，可反向恢复 | [擦拭对比](skills/wechat-svg-wipe-compare/SKILL.md) |
| 选择答案获得相应反馈，再重选 | [单题答题](skills/wechat-svg-quiz/SKILL.md) |
| 多步选择走向不同结局，再从头开始 | [分支故事](skills/wechat-svg-story-branches/SKILL.md) |
| 图形沿指定贝塞尔路径运动，可重播 | [轨迹运动](skills/wechat-svg-motion-path/SKILL.md) |
| 文字逐字显现，可重新播放 | [逐字打印](skills/wechat-svg-typewriter/SKILL.md) |
| 同一图片局部放大，再回到全景 | [镜头放大](skills/wechat-svg-zoom-detail/SKILL.md) |
| 按用户数值生成柱形入场动画 | [数据图表](skills/wechat-svg-data-chart/SKILL.md) |
| 卡片正面压缩翻到背面，再翻回 | [双面翻牌](skills/wechat-svg-flip-card/SKILL.md) |
| 打开封口，抽出信纸，再收回 | [拆信与收信](skills/wechat-svg-envelope/SKILL.md) |
| 分条窗叶错峰展开与合上 | [百叶窗](skills/wechat-svg-blinds/SKILL.md) |
| 在几个位置照亮局部，再查看全景 | [探照灯](skills/wechat-svg-spotlight/SKILL.md) |
| 远景、中景与前景以不同位移移动 | [多层视差](skills/wechat-svg-parallax/SKILL.md) |
| 点击面板展开，其他面板同时收窄 | [手风琴面板](skills/wechat-svg-accordion-panels/SKILL.md) |
| 从侧面抽出信息条，再收回 | [抽拉标签](skills/wechat-svg-pull-tab/SKILL.md) |
| 控制唱片转动与停止 | [唱片启停](skills/wechat-svg-vinyl/SKILL.md) |
| 点按播放碎片拼合成完整图案 | [拼图拼合](skills/wechat-svg-puzzle-assemble/SKILL.md) |
| 一条时间线串起逐阶段出现的信息 | [动态时间线](skills/wechat-svg-timeline/SKILL.md) |
| 点按触发粒子散开与祝福文字 | [点按礼花](skills/wechat-svg-confetti/SKILL.md) |

## 开始使用

1. 读取正文和本次要求，识别所需组件。已有风格资料时采用它的颜色、字级和间距。用户只要求排版时保留原文。
2. 查看对应组件的必需输入，集中指出缺项，并说明怎样提供。例如原生公众号卡片、图片顺序、需要揭晓的内容。
3. 确认本次可用的制作与浏览器工具。脚本采用 Python 标准库。需要操作秀米时，先读取当地可用的 Ego lite 操作说明，沿用用户登录状态。
4. 使用组件内的脚本、模板或编辑器做法生成结果，按组件的检查项验证。浏览器显示、秀米保存、微信保存、手机点击分别按实际完成的范围说明。
5. 交付可编辑素材、生成文件或实际草稿位置，以及仍需补充的材料。发布、群发、购买和账号设置按用户本次授权执行。

## 选择时看什么

- 一段短答案采用点击揭秘。多个可单独查看的注释采用多热区，说明层带返回入口。
- 同一组短内容需要反复翻看时采用旋转切换。希望按顺序揭晓、最后停留在结论时采用逐层掉落。
- 图片需要保留原图与图注时采用图集。未指定自动播放时采用读者手动控制。
- 长按玩法先确认松开后的目标。显影组件会恢复，轮播组件会定格。轮播结果随松手时刻变化。
- 一题多种反馈采用答题组件。需要连续选择和不同结局时采用分支故事。
- 擦拭对比目前通过按钮控制正反方向。按本次用户要求选择实际可实现的操作方式，并在交付中写清。
- 图片局部检查采用同图放大。图表先取得实际数值和单位，核对静态完整值后再加动画。
- 真正改变文章占位高度的展开、复杂滑动或需要在秀米参数面板里继续编辑的交互，读取秀米原生 SVG 做法，再按当前界面操作。
- 翻牌、拆信、百叶窗和抽拉标签各自提供不同的出场动作，按正文含义选择。手风琴用面板宽度表达当前焦点。
- 探照灯与视差示例采用按钮控制。需要跟手滑动时，结合秀米原生滑动入口及本次材料制作，并单独测试。
- 拼图示例提供点按拼合的动效，时间线使用真实阶段文字。礼花用于祝福与完成反馈。
- 唱片示例提供视觉启停。实际播放音频需要用户的音频素材和目标平台原生音频入口。
- 保留本篇文字和阅读主线。需要的素材已提供时直接使用，缺项集中指出。示例文案与占位图只用于试效果。

可交互示例见 [组件预览](examples/preview.html)。调研来源与逐项验证见 [调研与复刻计划](docs/调研与复刻计划.md)。

预览包含30个Skill入口。组件示例修改后执行 `python scripts/build_preview.py`，刷新整包预览。根目录 `index.html` 提供相对路径入口，供后续静态托管使用。
