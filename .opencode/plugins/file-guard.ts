import type { Plugin } from "@opencode-ai/plugin";

const fileGuardPlugin: Plugin = async ({ $ }) => {
  return {
    "tool.execute.after": async (input, output) => {
      // 1. 只关注 write 和 edit 工具
      if (input.tool !== "write" && input.tool !== "edit") {
        return;
      }

      const filePath = input.args?.filePath;
      if (!filePath || typeof filePath !== "string") {
        return;
      }

      let fileContent = "";
      try {
        // 使用 $ 执行本地命令读取文件内容，规避环境类型依赖问题
        const res = await $`cat ${filePath}`.nothrow().quiet();
        if (res.exitCode !== 0) return; // 如果读取失败则跳过
        fileContent = res.text();
      } catch (e) {
        // 异常则静默退出，不打断主流程
        return;
      }

      const warnings: string[] = [];

      // 检查 1: configs/vendor/*.json 格式检查
      if (filePath.includes("configs/vendor/") && filePath.endsWith(".json")) {
        try {
          JSON.parse(fileContent);
        } catch (e: any) {
          warnings.push(`[JSON 格式错误] ${filePath} 无法解析: ${e.message}`);
        }
      }

      // 检查 2: Python 语法检查
      if (filePath.endsWith(".py")) {
        try {
          const res = await $`python3 -m py_compile ${filePath}`.nothrow().quiet();
          if (res.exitCode !== 0) {
            let errText = "";
            if (res.stderr) errText += res.stderr.toString();
            if (res.stdout) errText += res.stdout.toString();
            warnings.push(`[Python 语法错误] ${filePath} 解释器报错:\n${errText.trim()}`);
          }
        } catch (e: any) {
          warnings.push(`[Python 执行异常] ${e.message}`);
        }
      }

      // 检查 3: 扫描硬编码密钥
      const checkExtensions = [".py", ".md", ".json", ".env.example"];
      const shouldCheckSecrets = checkExtensions.some(ext => filePath.endsWith(ext));
      
      if (shouldCheckSecrets) {
        const secretPatterns = [
          /(?:API_KEY|SECRET|TOKEN|PASSWORD)\s*(?:=|:)\s*['"][a-zA-Z0-9_\-]{10,}['"]/i, // 典型的环境变量硬编码
          /sk-[a-zA-Z0-9]{32,}/, // OpenAI 等类型的 sk- 密钥
          /AKID[a-zA-Z0-9]{32}/, // 腾讯云等类型的 SecretId 特征
        ];
        
        for (const pattern of secretPatterns) {
          if (pattern.test(fileContent)) {
            warnings.push(
              `[安全红线警告] 🚨 在 ${filePath} 中检测到疑似硬编码的密钥或敏感 Token！\n请遵守 AGENTS.md 规范，切勿将真实密钥写入代码或文档。`
            );
            break; // 触发一次就够了，避免过多警告
          }
        }
      }

      // 检查 4: src/pipeline/*.py 检查同步阻塞代码
      if (filePath.includes("src/pipeline/") && filePath.endsWith(".py")) {
        const blockingPatterns = [
          /time\.sleep\(/,
          /import\s+requests\b/,
          /from\s+requests\s+import/,
          /requests\.(get|post|request)\(/
        ];
        
        for (const pattern of blockingPatterns) {
          if (pattern.test(fileContent)) {
            warnings.push(
              `[架构规范警告] 🚨 在 ${filePath} 中检测到可能存在的同步阻塞调用 (如 time.sleep 或 requests)！\n这是 VoiceAgent 核心 pipeline 的风险提醒，建议使用 asyncio.sleep、aiohttp 或异步 SDK，避免阻塞整个事件循环。`
            );
            break;
          }
        }
      }

      // 检查 5: configs/vendor/*.json 检查必要字段
      if (filePath.includes("configs/vendor/") && filePath.endsWith(".json")) {
        try {
          const config = JSON.parse(fileContent);
          // 如果解析出来的不是对象，跳过
          if (config && typeof config === "object" && !Array.isArray(config)) {
            const commonFields = ["endpoint", "model", "language", "sample_rate", "audio_format", "config"];
            // 只要匹配到一个常见字段，就认为大体没问题
            const hasAnyCommonField = commonFields.some(field => field in config);
            
            if (!hasAnyCommonField && Object.keys(config).length > 0) {
              warnings.push(
                `[配置字段提醒] 📝 发现 ${filePath} 是 vendor 配置文件，但似乎缺少常见的关键字段 (如 endpoint, model, language, sample_rate 等)。\n若该厂商不需要这些字段请忽略此提醒，否则请人工确认配置是否完整。`
              );
            }
          }
        } catch (e) {
          // JSON 格式错误在检查1里报过了，这里忽略
        }
      }

      // 检查 6: 高风险文件修改提醒
      const highRiskPatterns = [
        /\.env$/,
        /AGENTS\.md$/,
        /opencode\.json$/,
        /\.opencode\/agents\/.*\.md$/,
        /\.opencode\/skills\/.*\/SKILL\.md$/,
        /\.opencode\/plugins\/.*\.ts$/
      ];
      
      const isHighRisk = highRiskPatterns.some(pattern => pattern.test(filePath));
      if (isHighRisk) {
        warnings.push(
          `[高风险操作提醒] ⚠️ 你刚刚修改了核心协议或配置文件：${filePath}。\n请确保本次修改完全符合项目协作规范，不要在此类文件中遗留临时测试代码或密码。`
        );
      }

      // 注入警告信息到输出中，让 Agent 看到
      if (warnings.length > 0) {
        const warningMessage = `\n\n⚠️ **本地守卫检测失败 (Hooks)** ⚠️\n` + warnings.map(w => `- ${w}`).join("\n");
        if (typeof output.output === "string") {
          output.output += warningMessage;
        } else {
          // 如果 output 不是 string，尽力转换或附加
          output.output = String(output.output) + warningMessage;
        }
      }
    }
  };
};

export default fileGuardPlugin;
