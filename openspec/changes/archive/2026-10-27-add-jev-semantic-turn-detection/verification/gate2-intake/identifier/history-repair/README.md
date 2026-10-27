# G2-02-OVERFLOW-HISTORY 研发返修

日期2026-10-26。工程缺陷，无产品规则/后端/播放/冻结原型变化，无外部调用。

## 原因与修复

appendTDHistory旧历史回退只以conversation_utterance决定新轮次是否有效，未满位/超位因规则保护尚无普通提交而被清空，尽管编号/提醒/播放证据已存在。新增hasTurnContent允许真实identifier_local_processed、identifier_reminder、identifier_echo_scheduled事件保留轮次；不添加conversation_utterance或td_commit，不补LLM指标或伪造播放。完全缺少可展示新轮次的旧历史继续原逻辑，未归属证据维持原分组。

## SDD/TDD与结果

正式td-history-evidence.spec.js补未满位/超位无conversation_utterance的断言。两项1440负例先失败于轮次缺失（history-red.txt），修复后同正式路由8项全部通过4.9秒，覆盖1440/390、未满位/超位、刷新、中英字面值保留、无普通提交badge/LLM指标、旧历史、正常多轮及无横向溢出（history-green.txt）。页面截图identifier-*.png，非替代验收页面，未更新冻结baseline。一次因编辑命令工作目录错误未落补丁的启动已中止，不计入结果。

原审核gate2-number-playback.spec.js未改断言，使用新隔离临时库和真实本机HTTP/WS/SQLite/AudioWorklet、仅厂商/推理替身，满位16.1秒、超位13.7秒，两项30.4秒通过（runtime-green.txt）。保留唯一正常提交/正常回答、超位0普通提交且唯一提醒、串行播放、未播末段跳过、回执204、刷新历史可见提醒；runtime/complete.json、overflow.json及*-history.png为本次证据。原审核BLOCKED及原失败证据保留。

frontend build通过。Python3.11.15、Chromium153，源码hash见source-sha.json。冻结v0.14 SHA仍657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。

## 复现与边界

组件回归：本机Vite正式入口19000，VOICE_AGENT_UI_URL指向该入口，运行td-history-evidence.spec.js desktop-chromium retries0。API数据用既有fixture适配，非真实厂商。

完整原探针：原browser_number_app.py仅临时库路径替换为/tmp/voiceagent-gate2-number-history-repair-20261026，临时启动脚本/tmp/td-history-number-app.py；NLTK_DATA为已有.venv/nltk_data，PYTHONPATH为仓库根，原端口18998。运行原gate2-number-playback.spec.js，VOICE_AGENT_TD_LOCAL_RUNTIME=1、VOICE_AGENT_GATE2_NUMBER_PLAYBACK=1。临时DB/缓存/密钥/录音不提交；18997未停改。Playwright临时报告在test-results/。

待独立change-verifier复审此缺陷，不签全Change PASS/C/Gate2。真实厂商效果/硬件/手机弱网依然未验证，不由离线播放事实替代。

## 当前独立结论

独立复审已支持关闭G2-02-OVERFLOW-HISTORY，报告independent-review.md；原审核失败报告保留历史。当前缺陷已关闭，但未签完整Checkpoint C/Gate2。自有19000/18998测试服务已停止，18997未停改。
