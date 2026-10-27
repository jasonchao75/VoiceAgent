# r46：无接收上下文回调不得猜当前连接

实际生产缺陷：SourceOwnedASRMixin在ContextVar=None时以当前全局epoch代填，未证明归属；协调器又将显式None当旧帧丢弃原文。

- unbound-source-red.txt：2 failed、4 passed，分别复现猜epoch及丢原文；不以环境错误冒充红灯。
- unbound-source-green.txt：118 passed、4依赖警告、1.97秒，相关来源/ASR/正式协调器/工厂回归。
- backend-full.txt：683 passed、5依赖警告、36.82秒，含追加原文stream_epoch=null、turn_id=null、新连接有效帧不清缺口及截止失败断言。
- ruff.txt PASS，types.txt实际Python3.13、3源文件PASS。

命令：.venv/bin/pytest tests -q --ignore=tests/ui；定向pytest tests/test_td_source_frames.py tests/test_td_asr_events.py tests/test_td_runtime.py tests/test_asr_factory.py -q；mypy --explicit-package-bases --follow-imports=silent --python-version 3.13 src/asr/source_frames.py src/asr/factory.py src/pipeline/custom_td.py。

修复遵守D-061：未知连接保留原文与失败原因，阻提交/工具，达到既有最长等待明确错误结束；不把供应商局部时间戳充作连接证据。native/off不增加标签。没有外部调用，无新架构/依赖/配置控件。六模型真实回包/重连与绝对音频时钟仍未验证，未签完整M1/独立审核。r45本地fixture仍在8769，Vite5177，临时数据路径已在r45记录，不删除其他任务资源。
