# 个人配置与打包

由AI把已读样本、用户选择和小样反馈写成配置。用户通过看效果与口述偏好参与，无需手工编写JSON。

## 配置内容

| 字段 | 内容 |
|---|---|
| `schema_version` | 当前采用1 |
| `skill_name` | 个人Skill的英文目录名，小写字母、数字及连字符 |
| `display_name` | 用户希望看到的个人排版名称 |
| `account.name` | 本人的公众号名称 |
| `style.sources` | 来源文章的URL或本地文件，以及实际观察 |
| `style.rules` | 已确定的排版规则对象 |
| `components` | 所选组件的ID、使用场景、放置位置与补充参数 |
| `assets` | 本人头像和其他常用素材的本地来源与包内名称 |
| `delivery` | 默认目标编辑器和草稿模式 |

以下展示字段形式，实际内容由本次取得的资料填写。

```json
{
  "schema_version": 1,
  "skill_name": "my-wechat-layout",
  "display_name": "我的公众号排版",
  "account": {"name": "本人的公众号名称"},
  "style": {
    "sources": [{"file": "my-article.html", "observed": "已读取的排版特点与范围"}],
    "rules": {
      "colors": {"text": "从样本读取的正文色", "accent": "已确认的强调色"},
      "typography": {"body": "已确认的字号与行高"},
      "spacing": {"paragraph": "已确认的段距"},
      "images": "样本中的图片比例与图注规则"
    }
  },
  "components": [
    {
      "id": "wechat-svg-envelope",
      "use_when": "正文包含给读者的一封信或结尾寄语时",
      "placement": "对应寄语段落",
      "frequency": "按当篇内容采用",
      "settings": {}
    }
  ],
  "assets": [{"source": "avatar.jpg", "name": "avatar.jpg"}],
  "delivery": {"editor": "xiumi", "mode": "draft"}
}
```

`style.sources` 至少包含一个已实际读取的来源，`style.rules` 保存具体排版规则。来源本地文件与素材路径可相对配置文件，也可采用实际绝对路径。脚本会把所需文件复制进个人Skill，并改为包内相对路径。

`delivery.editor` 可采用 `xiumi`、`wechat` 或 `ask`。采用 `ask` 时，在本篇目标还不明确的情况下补问保存位置。`delivery.mode` 当前采用 `draft`。

每个组件必须写明 `id`、`use_when` 与 `placement`，可补充 `frequency`、`settings` 和本篇素材需求。组件ID采用总览当前清单中的稳定ID。

## 生成个人Skill

50项组件均提供公开单项ZIP。已有完整库或单项ZIP时，打包使用 `--library-root` 或 `--downloads-dir`，沿用本地完整素材。

组件选择后，先下载并展开所选材料，供读取Skill和制作小样。已有完整组件库时直接使用现有文件。

```text
python -X utf8 scripts/fetch_components.py --components wechat-svg-envelope wechat-svg-timeline --out-dir /工作目录/组件下载
```

小样确认后，在本Skill目录中运行打包脚本。输入与输出路径使用本次实际位置，并复用刚才下载的单项ZIP。

```text
python -X utf8 scripts/build_personal_skill.py --config /工作目录/profile.json --out-dir /个人Skill输出目录 --downloads-dir /工作目录/组件下载
```

省略组件来源参数时，打包器会从公开仓库同一个发布版本下载选中的完整组件。网络访问受限时，可以使用已取得的整库或单项ZIP。

```text
python -X utf8 scripts/build_personal_skill.py --config /工作目录/profile.json --out-dir /输出目录 --library-root /wechat-layout-copilot
python -X utf8 scripts/build_personal_skill.py --config /工作目录/profile.json --out-dir /输出目录 --downloads-dir /组件ZIP目录
```

完成后检查生成的个人Skill文件夹与ZIP，确认 `SKILL.md`、个人配置、所选完整组件和本地素材都可读取。输出名称已存在时，保全已有版本，选择新的输出位置或明确的新名称继续。

按当前Agent的Skill发现方式安装完整文件夹。Codex可使用其实际的个人Skill目录，也可以在对话里直接提供文件夹并让AI读取 `SKILL.md`。其他Agent采用其支持的Skill导入方式。

## 继续调整

用户以后修改配色、头像或组件规则时，更新个人Skill内的 `profile.json`，同步修正相关模板并用实际正文核对。需要重新打包时，以更新后的配置在新输出位置生成。可继续自动下载所选组件，或提供原整库及单项ZIP，再按用户要求替换使用版本。
