# 新增 Work 工作区源码搜索

日期：2026-07-23  
范围：`<local-workspace>`

## 搜索方法

对 Work 工作区执行文件名和内容两类只读搜索，排除 `.git`、`node_modules` 和
`.venv` 依赖树：

- 固件身份：`54LMG6HE`、`54L2DNGC`、`G6HE_v1.0.0`、
  `UltraLink_dongle_rx21`；
- 异常实现：`ppt_ptx/bond`；
- 工程入口：`west.yml`、`prj.conf`、`CMakeLists.txt`、DTS/overlay；
- 构建产物：ELF、map、HEX；
- 归档：ZIP、7z、RAR、tar/tgz；
- 工程线索：固件、烧录、DFU、bootloader、配对、死机、watchdog、
  PAW3950/PAW3955、nRF54LM20。

## 结果

- 扫描文件数：45,875；
- 符合固件工程入口或构建产物后缀的文件：0；
- 归档文件：1，`Hunyuan3D-MLX-main.zip`，与鼠标固件无关；
- 精确固件身份/异常字符串内容命中：0；
- G6 HE 相关命中均属于宣讲稿、PPT、渲染图或其构建材料。

文本材料确认产品口径为 PAW3955、nRF54LM20A、8K 和 MagOptic，但没有供应商源码
路径、签名流程、DFU/烧录说明、恢复方法或死机调试记录。

## 判定

新增 Work 根目录没有解除固件本体修复门槛。它补强了产品规格证据，但不能用于重新
构建或签名鼠标/接收器镜像。

随后对 `Base`、桌面、`Downloads` 及其中 120 个归档执行的扩展搜索结果，见
[`LOCAL_SOURCE_SEARCH_20260723.md`](LOCAL_SOURCE_SEARCH_20260723.md)。扩展搜索同样
没有找到 G6 HE 源码、ELF/map、签名流程或官方恢复包。
