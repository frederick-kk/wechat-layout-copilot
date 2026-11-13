---
name: wechat-svg-drawline
description: 为公众号正文制作可调颜色、长度、粗细和时长的SVG描边分隔线，生成内联HTML与浏览器预览，并指导秀米和微信草稿验证。
metadata:
  version: "0.1.0"
---

# SVG 描边分隔线

用于章节之间的小幅度线条动效。使用系统已有的 Python 3.10 或更新版本，渲染脚本仅使用标准库。

## 先收集本次输入

- 用户指定的主题色、尺寸、粗细、播放时长和循环次数优先。
- 未指定时，可使用本组件的暖橙默认色 `#D97706`、600×48画布、3单位线宽、2.8秒、单次播放。交付时说明采用了这些默认值。
- 确认放入哪篇文章、哪个章节附近，以及输出目录。要进入秀米或微信时，再检查相应浏览器工具和登录状态。
- 缺少组件目标位置、账号授权或登录时，集中列出需要补充的项，并保留已生成的本地预览。

## 生成

```text
python <本Skill目录>/scripts/render.py --out <本次目录>/drawline.html --preview-out <本次目录>/drawline-preview.html --color "#D97706" --duration 2.8 --repeat 1
```

`--repeat loop` 表示循环播放。`--width`、`--height` 和 `--stroke-width` 可调整画布和线条。已有输出须在本次允许替换后加 `--overwrite`。

`drawline.html` 是用于组装正文的内联片段，`drawline-preview.html` 是独立浏览器预览页。实际组件保持一条短分隔线，正文标题和文字继续使用原生文本。

## 检查和插入

1. 在浏览器打开预览，观察线条从左向右画出，再停在完整状态。循环版本每轮重新描边。
2. 在窄屏检查宽度、比例、线宽和上下间距。根SVG使用响应宽度，画布比例固定。
3. 通过本次实际可用的编辑器入口插入片段，保存并重新打开，检查SVG和动画标签是否保留。
4. 同步到公众号草稿后查看手机预览，确认线条播放及静止显示。使用者明确授权后才执行对应草稿操作。

动画未被保留时，SVG的基础状态显示完整线条。可将 `repeat` 改成 `1` 便于减少连续运动。

## 验证范围与依据

2026-11-11已完成文件生成、结构自检和Ego lite浏览器时点验证。0、1.68、2.8秒的实际描边偏移依次为100、约0、0，末帧保留完整线条。秀米及微信保存重开、手机预览继续待实测。组件代码依据SVG规范独立编写，描边表现使用标准 `pathLength`、`stroke-dasharray`、`stroke-dashoffset` 与 `animate`。

示例见 [examples/preview.html](examples/preview.html)。技术依据和参数解释见 [references/implementation.md](references/implementation.md)。
