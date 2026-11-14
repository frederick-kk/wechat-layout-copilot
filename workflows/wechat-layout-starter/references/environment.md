# 环境准备

先检查用户已有的环境与本次目标。Ego lite在用户电脑上运行，Agent需要能调用同机的浏览器命令。

## 检查制作脚本的运行环境

组件生成、下载与个人Skill打包使用Python 3.10或更新版本，依赖Python标准库。先检查本机可用解释器。

| 系统 | 检查方式 |
|---|---|
| Windows | 查找 `python` 或 `py`，运行其版本检查，采用实际可用的解释器 |
| macOS | 检查 `python3 --version`，沿用实际可用路径 |

本机缺少合适版本时，按用户当前的环境配置要求，从[Python官方下载页](https://www.python.org/downloads/)获取对应系统安装包，完成后重新检查。已有合适环境时直接复用。

后续文档中的 `python` 采用本机实际可用命令，例如 `python3` 或 `py -3`，并保留 `-X utf8` 参数处理中文文件与输出。

## 安装和接通

1. 检查 `ego-browser` 是否可用，并读取当前已安装的浏览器Skill。
2. 尚未安装时，引导用户从[官方下载页](https://lite.ego.app/download?auto=1)安装Ego lite，完成首次启动向导。安装步骤以[官方快速上手](https://lite.ego.app/document/en/docs/quick-start)为准。
3. 向导会注册浏览器CLI，并向已识别的Agent安装浏览器Skill。完成后重新打开终端与Agent应用，使新命令和Skill被加载。
4. 在实际制作的Agent会话里验证CLI，再按当前浏览器操作说明打开公开页面，读取真实标题与URL。

Windows PowerShell可先检查以下命令。

```powershell
Get-Command ego-browser
ego-browser nodejs -e "console.log('ego-browser ready')"
ego-browser skill
```

macOS的命令查找使用 `command -v ego-browser`。安装包、系统支持与连接方式以官网当前说明为准。

`ego-browser ready` 表明命令能运行。浏览器连接还需要在当前Agent里完成实际打开页面的检查。

Codex连接细节参见[官方Codex接入说明](https://lite.ego.app/document/en/docs/codex)，其他Agent参见[官方Agent接入说明](https://lite.ego.app/document/en/docs/custom-agent-harness)。按实际宿主支持的Skill导入方式配置。

遇到命令找不到、向导未结束或宿主连接问题，说明具体卡点并按官方对应系统说明处理。权限按实际命令错误定位，采用完成当前动作所需的配置。云端、容器或远程Agent需要其正式支持的宿主连接方式。

## 微信和秀米登录

1. 按当前Ego说明创建本次工作空间，后续沿用它。
2. 打开[微信公众平台](https://mp.weixin.qq.com/)与[秀米](https://xiumi.us/)，查看各自登录状态。
3. 需要扫码或验证时，将浏览器交给用户，等待明确“继续”。
4. 在同一工作空间恢复，核对公众号名称及本次秀米账号。

登录凭据保留在用户浏览器中。个人排版配置保存账号名称和页面线索，文件中只记录登录检查结果。

用户本次只希望制作一个平台的草稿时，先完成该平台可用的流程。需要在秀米与公众号之间同步时，再补齐两端登录。

## 连接后的日常动作

每次实际使用浏览器，先运行 `ego-browser skill` 并遵循其当前输出。工作空间、用户接手、页面保存和结束处理都采用当前说明。用户接手结束后继续其原任务。
