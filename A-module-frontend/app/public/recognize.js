/* 监督小宠 · C 模块 学习截图识别 v1.1
 * ------------------------------------------------------------
 * 给 A 模块（前端）用的唯一引入文件。
 *
 * 用法：
 *   <script src="recognize.js"></script>
 *   const result = await window.recognizeScreenshot(file, "demo_zhang");
 *
 * 说明：
 *   1. 单文件、无打包、无额外依赖。云 SDK 由本文件自己按需加载。
 *   2. 任何情况下都【返回标准对象】，不抛异常、不返回 null，
 *      避免调用方的等待态卡死（A 模块 v1.1 第四节第 1 条）。
 *   3. 只带 publishableKey（公开标识，无权限），不含任何私密密钥。
 *   4. 返回结构见接口草案 v1.1。
 * ------------------------------------------------------------ */
(function (global) {
  "use strict";

  var CONFIG = {
    ENDPOINT: "https://supervise-pet.app.workbuddy.host",
    PUBLISHABLE_KEY: "wbpk_7U8B8g9BI4EjIvkNwjFaTH_BLi6qfTHTGU941OO0qhF58RyOPDNTBwQ",
    // 锁定具体版本，不用 @dev 浮动标签（路演当天若上游发 breaking change 就是事故）
    // 当前 @dev 解析到的就是 0.1.4-dev.ca27990.202610161713，行为与验证过的一致
    SDK_URL: "https://cdn.jsdelivr.net/npm/@tencent-ai/workbuddy-cloud-sdk@0.1.4-dev.ca27990.202610161713/lib/index.global.js",
    // r6：SDK 已内嵌在本文件末尾，CDN 只是兜底通道；加载超时时间
    SDK_LOAD_TIMEOUT_MS: 15000,
    // 实测：auto 路由模型响应波动大（5~10 秒），10 秒窗口会把正常学习图误杀成
    // "非学习图片"（test7 实测：10s 窗口两次超时兜底，35s 窗口 5.2s 即正确识别）。
    // 故放宽单次窗口到 20 秒、取消重试——慢响应重试大概率仍超时，且会把最坏耗时翻倍。
    // 最坏情况 20 秒，需在 A 等待态设计中留足。
    // 多轮跑批口径（10 张真实学习截图 × 数轮，20s 窗口+不重试）：
    // 平均 5.4~6.9s，最快约 2.4s，最慢 10.8~14.3s（auto 模型响应本身有波动）。
    // 全部一次成功、无重试。路演材料引用耗时请以此区间为准，不要写单点值。
    TIMEOUT_MS: 20000,        // 单次调用超时；最坏情况 20 秒（不重试）
    MAX_RETRIES: 0,           // 不重试：对"偶发慢响应"，重试收效低且翻倍最坏耗时
    MAX_FILE_BYTES: 10 * 1024 * 1024,
    OK_TYPES: ["image/png", "image/jpeg", "image/webp"]
  };

  var SCHEMA_VERSION = "1.1";

  /* ---------------- 通用小工具 ---------------- */

  function pad2(n) { return n < 10 ? "0" + n : String(n); }

  // 生成本地时区的 ISO8601，例如 2026-10-31T09:20:00+08:00
  function nowISO() {
    var d = new Date();
    var off = -d.getTimezoneOffset();
    var sign = off >= 0 ? "+" : "-";
    var abs = Math.abs(off);
    return (
      d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) +
      "T" + pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds()) +
      sign + pad2(Math.floor(abs / 60)) + ":" + pad2(abs % 60)
    );
  }

  function isNum(v) { return typeof v === "number" && !isNaN(v); }

  // 模型偶尔会把数字写成字符串，统一转成数字；转不了返回 null
  function toNum(v) {
    if (typeof v === "number") return isNaN(v) ? null : v;
    if (v === null || v === undefined || v === "") return null;
    var n = Number(v);
    return isNaN(n) ? null : n;
  }

  // 给某个 code 追加一条 warning，已存在则不重复
  function addWarning(result, code, message) {
    if (!Array.isArray(result.warnings)) result.warnings = [];
    var exists = result.warnings.some(function (w) { return w && w.code === code; });
    if (!exists) result.warnings.push({ code: code, message: message });
  }

  function hasWarning(result, code) {
    return Array.isArray(result.warnings) &&
      result.warnings.some(function (w) { return w && w.code === code; });
  }

  /* ---------------- 返回对象骨架 ---------------- */

  // 任何异常情况下都返回这个标准对象，字段齐全、不缺 key
  function emptyResult(userId) {
    return {
      schema_version: SCHEMA_VERSION,
      user_id: userId || "demo_zhang",
      recognition: { recognized_at: nowISO(), confidence: 0 },
      source_app: null,
      event_date: null,
      event_time: null,
      duration_minutes: null,
      modules: [],
      total_questions: null,
      accuracy: null,
      warnings: [{ code: "NOT_A_STUDY_SCREENSHOT", message: "这张图片没有识别到学习数据" }],
      encouragement: { level: "" }
    };
  }

  // 统一字段顺序，方便 A 对照接口文档联调（不改变内容和结构）
  var FIELD_ORDER = [
    "schema_version", "user_id", "recognition", "source_app", "event_date",
    "event_time", "duration_minutes", "modules", "total_questions",
    "accuracy", "warnings", "encouragement"
  ];
  function normalizeFieldOrder(r) {
    var out = {};
    FIELD_ORDER.forEach(function (k) {
      if (Object.prototype.hasOwnProperty.call(r, k)) out[k] = r[k];
    });
    Object.keys(r).forEach(function (k) {
      if (!Object.prototype.hasOwnProperty.call(out, k)) out[k] = r[k];
    });
    return out;
  }

  /* ---------------- 等级判定（本地算，不信任模型） ---------------- */

  function calcLevel(accuracy, durationMinutes) {
    if (isNum(accuracy) && isNum(durationMinutes) && accuracy > 0.8 && durationMinutes >= 30) return "excellent";
    if (isNum(accuracy) && isNum(durationMinutes) && accuracy >= 0.6 && accuracy <= 0.8 && durationMinutes >= 20) return "good";
    if ((isNum(accuracy) && accuracy < 0.4) || (isNum(durationMinutes) && durationMinutes < 10)) return "low";
    return "normal";
  }

  /* ---------------- 学习时刻距今小时数 ---------------- */

  // A 模块 v1.1 Q8：event_time 有值按该时刻；无值按当天 12:00；event_date 为空则静默跳过
  function hoursSinceStudy(result) {
    if (!result.event_date) return null;
    var timeStr = result.event_time || "12:00";
    var d = new Date(result.event_date + "T" + timeStr + ":00");
    if (isNaN(d.getTime())) return null;
    return (Date.now() - d.getTime()) / (1000 * 60 * 60);
  }

  /* ---------------- accuracy / total_questions 本地重算 ---------------- */

  // A 模块 v1.1 Q4：只用有 correct_count 的模块算；全部模块都缺则 accuracy = null（不填 0）
  function validModules(result) {
    if (!Array.isArray(result.modules)) return [];
    return result.modules.filter(function (m) {
      return m && isNum(toNum(m.question_count)) && toNum(m.question_count) > 0 && isNum(toNum(m.correct_count));
    });
  }

  function recalcNumbers(result) {
    var mods = Array.isArray(result.modules) ? result.modules : [];

    // 把模块里的题量/正确数统一成数字（null 保持 null）
    result.modules = mods.map(function (m) {
      if (!m) return m;
      return {
        name: m.name == null ? null : String(m.name),
        question_count: toNum(m.question_count),
        correct_count: toNum(m.correct_count)
      };
    });

    var valid = validModules(result);
    var sumQuestions = valid.reduce(function (s, m) { return s + toNum(m.question_count); }, 0);
    var sumCorrect = valid.reduce(function (s, m) { return s + toNum(m.correct_count); }, 0);
    var declared = toNum(result.total_questions);

    // accuracy 三态（A 的 Q4 细化）：
    // - 无有效模块 → null（不填 0，避免误触 ACCURACY_TOO_LOW）
    // - 模块题量和 == 总题量（模块数据完整）→ 本地重算，纠正模型算术错误
    // - 模块题量和 != 总题量（截图只露出部分模块）→ 保留模型的 accuracy，
    //   因为模型更可能读到页面上「答对 X/总题数」的总正确率；用残缺模块重算会算偏。
    //   实测 test5：页面明写答对 109/135≈81%，残缺模块重算会错算成 70%。
    if (valid.length === 0) {
      result.accuracy = null;
    } else if (declared === null || sumQuestions === declared) {
      // declared === null 时，下方 total_questions 会用 sumQuestions 回填，
      // 故此处也必须本地重算，保证总题量与正确率来自同一套数据（A 的 P2 建议）。
      // 否则确认卡会出现「总题量 40、正确率 90%，但逐模块行加起来只有 50%」的自相矛盾。
      result.accuracy = Math.round((sumCorrect / sumQuestions) * 100) / 100;
    } else {
      // 模块不全：模型没给 accuracy 时，才用残缺模块兜底
      var modelAcc = toNum(result.accuracy);
      if (modelAcc === null) {
        result.accuracy = Math.round((sumCorrect / sumQuestions) * 100) / 100;
      }
    }

    // 模型偶尔把正确率写成百分制（0.75 写成 75），前端直接乘 100 会显示 7500%，
    // 且等级判定会被推到 excellent。统一归一到 0~1。
    // 注意：accuracy === 1 是合法的 100%，不参与归一。
    if (isNum(result.accuracy) && result.accuracy > 1 && result.accuracy <= 100) {
      result.accuracy = Math.round((result.accuracy / 100) * 100) / 100;
    }

    // total_questions：模型没给就用模块求和（declared 已在上方声明）
    if (declared === null && valid.length > 0) {
      result.total_questions = sumQuestions;
    } else {
      result.total_questions = declared;
    }

    // 模块题量之和与总题量不符
    if (isNum(result.total_questions) && valid.length > 0 && sumQuestions !== result.total_questions) {
      addWarning(result, "MODULE_MISMATCH", "各模块题量之和与总题量不一致，请复核截图");
    }

    // duration_minutes 必须是整数分钟。
    // 实测：模型偶尔把截图上的「8分47秒」误读成小数 8.47（把秒当小数位），
    // 确认卡显示「学习时长 8.47 分钟」会明显穿帮。四舍五入取整，误差在 1 分钟内，
    // 对鼓励等级判定（阈值 10/20/30 分钟）基本无影响。
    if (isNum(result.duration_minutes)) {
      result.duration_minutes = Math.round(result.duration_minutes);
    }
    return result;
  }

  /* ---------------- warnings 本地校验 ---------------- */

  function applyLocalValidation(result) {
    recalcNumbers(result);

    var rawConf = result.recognition ? result.recognition.confidence : null;
    var conf = toNum(rawConf);

    var hasStudyData =
      result.total_questions !== null ||
      result.accuracy !== null ||
      result.duration_minutes !== null ||
      (Array.isArray(result.modules) && result.modules.length > 0);

    // 置信度两档（A 模块 v1.1 Q7）
    if (conf !== null && conf < 0.5) {
      // 非学习截图：warnings 只保留这一个，不追加 DURATION_MISSING 之类的数据类噪音
      result.warnings = [{ code: "NOT_A_STUDY_SCREENSHOT", message: "这张图片没有识别到学习数据" }];
      return result;
    }
    if (conf !== null && conf < 0.6) {
      addWarning(result, "SCREENSHOT_BLURRY", "截图清晰度不足，可能影响识别准确率");
    } else if (!hasStudyData) {
      // confidence ≥ 0.5 但抽不到任何字段：按 A 的划分归 SCREENSHOT_BLURRY，照常出确认卡
      addWarning(result, "SCREENSHOT_BLURRY", "截图清晰度不足，可能影响识别准确率");
    }

    // 时长相关
    var dur = toNum(result.duration_minutes);
    result.duration_minutes = dur;
    if (dur === null) {
      addWarning(result, "DURATION_MISSING", "未识别到学习时长，请确认截图完整");
    } else if (dur < 5) {
      addWarning(result, "DURATION_TOO_SHORT", "学习时长过短，可能未完成一次有效练习");
    } else if (dur > 600) {
      addWarning(result, "DURATION_TOO_LONG", "学习时长超过600分钟，请确认截图数据是否正确");
    }

    // 正确率过低
    if (isNum(result.accuracy) && result.accuracy < 0.4) {
      addWarning(result, "ACCURACY_TOO_LOW", "正确率偏低，建议复盘错题后再继续");
    }

    // 正确数越界
    var invalidCorrect = (Array.isArray(result.modules) ? result.modules : []).some(function (m) {
      return m && isNum(m.correct_count) && isNum(m.question_count) && m.correct_count > m.question_count;
    });
    if (invalidCorrect) {
      addWarning(result, "CORRECT_COUNT_INVALID", "存在正确数大于题量的模块，请复核截图");
    }

    // 来源 App 认不出，但确实有学习数据
    if (!result.source_app && hasStudyData) {
      addWarning(result, "UNRECOGNIZED_APP", "未识别到来源 App，请手动标注");
    }

    // 学习记录距今超过 36 小时
    var hours = hoursSinceStudy(result);
    if (hours !== null && hours > 36) {
      addWarning(result, "OLD_SCREENSHOT", "这次学习记录距今已超过36小时，请确认是否为本次学习");
    }

    // DUPLICATE_RECORD：预留字段，本期不触发（无状态单次调用感知不到重复，去重在前端做）
    return result;
  }

  /* ---------------- 云服务 SDK / 模型 ---------------- */

  var cloud = null;
  var sdkPromise = null;
  var selectedModel = null;

  function loadSdk() {
    if (global.WorkBuddyCloud) return Promise.resolve(global.WorkBuddyCloud);
    if (sdkPromise) return sdkPromise;
    // r6：优先用内嵌的同一份 SDK，避免现场 CDN 被墙/被代理拦截导致整条识别链路不可用
    try {
      var embedded = __embeddedSdk();
      if (embedded && typeof embedded.createWorkBuddyCloud === "function") {
        global.WorkBuddyCloud = embedded;
        return Promise.resolve(embedded);
      }
    } catch (e) {
      // 内嵌执行失败就回退到 CDN（理论上不会发生）
      console && console.warn && console.warn("[识别] 内嵌 SDK 初始化失败，回退 CDN：", e);
    }
    sdkPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = CONFIG.SDK_URL;
      var timer = setTimeout(function () {
        reject(new Error("云服务 SDK 加载超时（" + CONFIG.SDK_LOAD_TIMEOUT_MS + "ms）。"));
      }, CONFIG.SDK_LOAD_TIMEOUT_MS);
      s.onload = function () {
        clearTimeout(timer);
        if (global.WorkBuddyCloud) resolve(global.WorkBuddyCloud);
        else reject(new Error("云服务 SDK 加载后未挂载全局对象。"));
      };
      s.onerror = function () {
        clearTimeout(timer);
        reject(new Error("云服务 SDK 加载失败，请检查网络后重试。"));
      };
      document.head.appendChild(s);
    });
    return sdkPromise;
  }

  function initCloud() {
    if (cloud) return Promise.resolve(cloud);
    return loadSdk().then(function (SDK) {
      cloud = SDK.createWorkBuddyCloud({
        endpoint: CONFIG.ENDPOINT,
        publishableKey: CONFIG.PUBLISHABLE_KEY
      });
      return cloud;
    });
  }

  function ensureModel() {
    if (selectedModel) return Promise.resolve(selectedModel);
    return initCloud().then(function (c) {
      return c.llm.models.list();
    }).then(function (models) {
      if (!models || models.length === 0) {
        throw new Error("当前云服务没有可用模型。");
      }
      var imageModel = models.find(function (m) {
        return m.disabled !== true && m.supportsImages === true;
      });
      if (!imageModel) {
        throw new Error("可用模型均不支持图片识别。");
      }
      selectedModel = imageModel;
      return selectedModel;
    });
  }

  // 超时控制：超过 ms 毫秒直接 reject，避免调用方等待态卡死
  function withTimeout(promise, ms, msg) {
    var timer = null;
    return Promise.race([
      promise,
      new Promise(function (_, reject) {
        timer = setTimeout(function () { reject(new Error(msg)); }, ms);
      })
    ]).then(function (v) {
      clearTimeout(timer);
      return v;
    }, function (e) {
      clearTimeout(timer);
      throw e;
    });
  }

  /* ---------------- 提示词 ---------------- */

  var SYSTEM_PROMPT = [
    "你是一个学习数据识别助手。用户会上传考公学习App的截图，你需要识别其中的学习数据，并严格输出JSON格式。",
    "",
    "输出必须符合以下结构（接口 v1.1），不要输出任何JSON之外的文字：",
    "{",
    '  "schema_version": "1.1",',
    '  "recognition": {',
    '    "recognized_at": "识别时间ISO8601带时区",',
    '    "confidence": "0到1的置信度"',
    "  },",
    '  "source_app": "截图来源App名称，如 粉笔/华图在线/腰果公考/学习强国，识别不出填null",',
    '  "event_date": "学习日期 YYYY-MM-DD，识别不出填null",',
    '  "event_time": "学习时间 HH:MM 24小时制，识别不出填null",',
    '  "duration_minutes": "本次学习时长分钟数，识别不出填null",',
    '  "modules": [',
    '    {"name": "模块名 言语理解/判断推理/数量关系/资料分析/常识判断/申论", "question_count": "题量", "correct_count": "正确数，识别不出填null"}',
    "  ],",
    '  "total_questions": "总题量，识别不出填null",',
    '  "accuracy": "正确率0到1保留两位，识别不出填null",',
    '  "warnings": [{"code": "异常码", "message": "中文说明"}],',
    '  "encouragement": {"level": "low/normal/good/excellent，识别失败时填空字符串"}',
    "}",
    "",
    "异常码（只从下面选）：",
    "- NOT_A_STUDY_SCREENSHOT：图片不是学习截图，或你从图里提取不到任何学习数据",
    "- SCREENSHOT_BLURRY：是学习截图但清晰度不足，部分字段可能不准",
    "- DURATION_MISSING：没有识别到学习时长",
    "- DURATION_TOO_SHORT：学习时长小于5分钟",
    "- DURATION_TOO_LONG：学习时长超过600分钟",
    "- ACCURACY_TOO_LOW：正确率低于0.4",
    "- MODULE_MISMATCH：各模块题量之和不等于总题量",
    "- CORRECT_COUNT_INVALID：某模块正确数大于题量",
    "- UNRECOGNIZED_APP：识别不到来源App，但图里确实有学习数据",
    "",
    "鼓励等级（你只需给出等级，话术由前端生成，不要输出 message）：",
    "- low: 正确率<0.4 或 时长<10分钟",
    "- normal: 完成但表现一般",
    "- good: 正确率0.6-0.8 且 时长≥20分钟",
    "- excellent: 正确率>0.8 且 时长≥30分钟",
    "",
    "规则：",
    "1. 无法确认的信息一律填null，绝对不要猜测、不要编造、不要用上一张图的内容",
    "2. 正确率accuracy = 有正确数模块的(正确数之和 / 题量之和)；如果所有模块都没有正确数，accuracy填null，不要填0",
    "3. confidence是你能从这张图里提取到学习数据的把握程度：低于0.5判定为不可识别，按规则4处理；0.5到0.6之间写入SCREENSHOT_BLURRY警告",
    "4. 如果图片不是学习记录、刷题报告或学习数据截图（如风景、动物、人物、表情包等），或者confidence低于0.5，必须判定为不可识别：source_app/event_date/event_time/duration_minutes/total_questions/accuracy全部填null，modules填空数组[]，warnings填[{\"code\":\"NOT_A_STUDY_SCREENSHOT\",\"message\":\"这张图片没有识别到学习数据\"}]，encouragement填{\"level\":\"\"}，confidence按实际填写。不得虚构任何App名称、日期、题量、正确率、模块成绩或学习时长。",
    "5. 这张图是唯一的输入来源，不要参考任何历史图片或历史结果",
    "6. 耗时若以 分:秒 格式显示（如 01:44、04:52），换算成分钟并取整（01:44→2，04:52→5），绝对不要读成144或104分钟",
    "7. 页面顶部显眼位置的百分比大数字（如橙色的27%、绿色的85%）就是正确率，换算成0到1的小数填入accuracy；即使旁边没写「正确率」三个字也要读取，不要因为排版位置不确定就漏读",
    "8. 只输出JSON，不要有多余解释"
  ].join("\n");

  /* ---------------- 调用模型 ---------------- */

  function fileToBase64(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { reject(new Error("图片读取失败。")); };
      reader.readAsDataURL(file);
    });
  }

  function callModelOnce(imageDataUrl) {
    return ensureModel().then(function (model) {
      return initCloud();
    }).then(function (c) {
      var messages = [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: [
            { type: "text", text: "请识别这张学习截图，按接口 v1.1 格式输出结果。" },
            { type: "image_url", image_url: { url: imageDataUrl } }
          ]
        }
      ];
      return c.llm.chat.completions.create({
        model: selectedModel.id,
        messages: messages,
        stream: true,
        response_format: { type: "json_object" }
      });
    }).then(function (stream) {
      // SDK 返回可迭代的流，逐段拼接成完整答案
      return collectStream(stream);
    }).then(function (answer) {
      if (!answer || !answer.trim()) {
        throw new Error("模型没有返回有效内容。");
      }
      var text = answer.trim().replace(/^```json\s*/i, "").replace(/```\s*$/, "").trim();
      return JSON.parse(text);
    });
  }

  // 兼容两种返回形态：异步可迭代流 / 一次性结果
  function collectStream(stream) {
    if (stream && typeof stream[Symbol.asyncIterator] === "function") {
      var answer = "";
      var iterator = stream[Symbol.asyncIterator]();
      function next() {
        return iterator.next().then(function (r) {
          if (r.done) return answer;
          var chunk = r.value;
          var delta = chunk && chunk.choices && chunk.choices[0] && chunk.choices[0].delta;
          if (delta && delta.content) answer += delta.content;
          return next();
        });
      }
      return next();
    }
    if (stream && stream.choices && stream.choices[0]) {
      var c0 = stream.choices[0];
      return Promise.resolve((c0.message && c0.message.content) || c0.text || "");
    }
    return Promise.reject(new Error("无法解析模型返回内容。"));
  }

  function callModelWithRetry(imageDataUrl) {
    var attempt = 0;
    function run() {
      return withTimeout(
        callModelOnce(imageDataUrl),
        CONFIG.TIMEOUT_MS,
        "识别超时（超过" + (CONFIG.TIMEOUT_MS / 1000) + "秒）。"
      ).catch(function (err) {
        if (attempt < CONFIG.MAX_RETRIES) {
          attempt++;
          return run();
        }
        throw err;
      });
    }
    return run();
  }

  /* ---------------- 主入口 ---------------- */

  /**
   * 识别学习截图
   * @param {File} file      图片文件（PNG/JPG/JPEG/WEBP，≤10MB）
   * @param {string} userId  用户标识，演示期固定 "demo_zhang"，C 原样透传不做逻辑
   * @returns {Promise<Object>} 接口 v1.1 标准对象，任何情况下都不抛异常
   */
  function recognizeScreenshot(file, userId) {
    var uid = userId || "demo_zhang";
    var startAt = Date.now();

    function finish(result) {
      result.user_id = uid;
      if (!result.recognition || typeof result.recognition !== "object") {
        result.recognition = {};
      }
      result.recognition.recognized_at = nowISO();
      if (typeof result.recognition.confidence !== "number") {
        result.recognition.confidence = toNum(result.recognition.confidence);
      }
      if (result.recognition.confidence === null) result.recognition.confidence = 0;

      // 识别失败、或完全没有可判断的数据时，不给出等级，避免前端凭空出话术。
      // 契约自洽：level == "" 必须等价于带 NOT_A_STUDY_SCREENSHOT，
      // 否则前端只认 warning 的分支会漏判（A 模块 P1）。
      var noData = result.accuracy === null && result.duration_minutes === null;
      if (noData) {
        addWarning(result, "NOT_A_STUDY_SCREENSHOT", "这张图片没有识别到学习数据");
      }
      if (hasWarning(result, "NOT_A_STUDY_SCREENSHOT")) {
        result.encouragement = { level: "" };
      } else {
        result.encouragement = { level: calcLevel(result.accuracy, result.duration_minutes) };
      }

      result._elapsed_ms = Date.now() - startAt; // 调试字段：本次识别耗时（毫秒），非契约字段，可删
      return normalizeFieldOrder(result);
    }

    // 入参校验：不合规图片也返回标准对象，不崩（A 模块 v1.1 第四节第 3 条）
    if (!file) {
      var r0 = emptyResult(uid);
      addWarning(r0, "NOT_A_STUDY_SCREENSHOT", "没有收到图片文件");
      return Promise.resolve(finish(r0));
    }
    if (file.type && CONFIG.OK_TYPES.indexOf(file.type) === -1) {
      var r1 = emptyResult(uid);
      r1.warnings = [{ code: "NOT_A_STUDY_SCREENSHOT", message: "不支持的图片格式：" + file.type }];
      return Promise.resolve(finish(r1));
    }
    if (file.size && file.size > CONFIG.MAX_FILE_BYTES) {
      var r2 = emptyResult(uid);
      r2.warnings = [{ code: "NOT_A_STUDY_SCREENSHOT", message: "图片超过10MB上限" }];
      return Promise.resolve(finish(r2));
    }

    return fileToBase64(file)
      .then(callModelWithRetry)
      .then(function (parsed) {
        if (!parsed || typeof parsed !== "object") {
          throw new Error("模型返回内容不是合法 JSON 对象。");
        }
        var result = emptyResult(uid);
        result.warnings = [];               // 清空默认 warning，交由本地校验重新判定
        result.source_app = parsed.source_app == null ? null : String(parsed.source_app);
        result.event_date = parsed.event_date == null ? null : String(parsed.event_date);
        result.event_time = parsed.event_time == null ? null : String(parsed.event_time);
        result.duration_minutes = toNum(parsed.duration_minutes);
        result.total_questions = toNum(parsed.total_questions);
        result.accuracy = toNum(parsed.accuracy);
        result.modules = Array.isArray(parsed.modules) ? parsed.modules : [];
        if (parsed.recognition && typeof parsed.recognition.confidence !== "undefined") {
          result.recognition.confidence = toNum(parsed.recognition.confidence);
        } else {
          result.recognition.confidence = 0.7;
        }
        applyLocalValidation(result);
        return finish(result);
      })
      .catch(function (err) {
        // 任何失败都返回标准对象 + NOT_A_STUDY_SCREENSHOT，不抛异常
        var rf = emptyResult(uid);
        var msg = err && err.message ? err.message : String(err);
        rf.warnings = [{ code: "NOT_A_STUDY_SCREENSHOT", message: "识别失败：" + msg }];
        return finish(rf);
      });
  }

  global.recognizeScreenshot = recognizeScreenshot;
  global.recognizeScreenshotConfig = CONFIG;

  // 给 C 模块自己页面用的辅助方法（A 模块无需关心）
  global.__recognizeInternals = {
    calcLevel: calcLevel,
    applyLocalValidation: applyLocalValidation,
    emptyResult: emptyResult,
    hasWarning: hasWarning,
    validModules: validModules
  };

  // ---- r6：内嵌云服务 SDK（与 CDN 上的是同一份代码）----
  // 来源：@tencent-ai/workbuddy-cloud-sdk@0.1.4-dev.ca27990.202610161713/lib/index.global.js
  // 目的：CDN 不可达时（现场网络/代理限制）仍能识别，消除唯一的网络单点依赖。
  function __embeddedSdk() {
var WorkBuddyCloud=(()=>{var ie=Object.defineProperty;var _t=Object.getOwnPropertyDescriptor;var Tt=Object.getOwnPropertyNames;var Ot=Object.prototype.hasOwnProperty;var a=(r,e)=>ie(r,"name",{value:e,configurable:!0});var At=(r,e)=>{for(var t in e)ie(r,t,{get:e[t],enumerable:!0})},Rt=(r,e,t,s)=>{if(e&&typeof e=="object"||typeof e=="function")for(let n of Tt(e))!Ot.call(r,n)&&n!==t&&ie(r,n,{get:()=>e[n],enumerable:!(s=_t(e,n))||s.enumerable});return r};var $t=r=>Rt(ie({},"__esModule",{value:!0}),r);var nr={};At(nr,{AuthModule:()=>D,CLOUD_MODULE_PATHS:()=>R,CLOUD_PATH_PREFIX:()=>j,CloudOpenAIError:()=>x,CloudStoragePathError:()=>w,DEFAULT_SIGNED_URL_TTL_SECONDS:()=>ge,LlmModule:()=>M,MAX_SIGNED_URL_TTL_SECONDS:()=>ye,PUBLISHABLE_KEY_HEADER:()=>be,RUNTIME_STORAGE_BUCKET:()=>W,WorkBuddyCloudClient:()=>se,WorkBuddyCloudConfigError:()=>T,WorkBuddyDatabaseModule:()=>J,WorkBuddyStorageBucket:()=>H,WorkBuddyStorageDownload:()=>te,WorkBuddyStorageModule:()=>re,anonymousTokenProvider:()=>oe,createMemoryStorage:()=>ke,createWorkBuddyCloud:()=>vt,getModelCapability:()=>Oe,getModelDisplayName:()=>Te,shouldClearCredentials:()=>Pt});var T=class extends Error{static{a(this,"WorkBuddyCloudConfigError")}constructor(e){super(e),this.name="WorkBuddyCloudConfigError"}};var Ut=/^wbpk_/;function Le(r,e){if(typeof r!="string"||r.trim()==="")throw new T(`${e} is required and must be a non-empty string.`);let t=r.trim(),s;try{s=new URL(t)}catch{throw new T(`${e} must be an absolute URL, received: ${t}`)}if(s.protocol!=="https:"&&s.protocol!=="http:")throw new T(`${e} must use http(s), received protocol: ${s.protocol}`);return t.replace(/\/+$/,"")}a(Le,"normalizeHttpUrl");function It(r){if(r!=null&&r!=="")return Le(r,"endpoint");let e=globalThis.location?.origin;if(typeof e!="string"||e==="")throw new T("endpoint is required outside browsers (no location.origin to fall back to).");return e.replace(/\/+$/,"")}a(It,"resolveEndpoint");function Ct(r){if(typeof r!="string"||r.trim()==="")throw new T("publishableKey is required and must be a non-empty string.");let e=r.trim();if(!Ut.test(e))throw new T('publishableKey must start with "wbpk_".');return e}a(Ct,"normalizePublishableKey");function Lt(r){if(r)return r;if(typeof globalThis.fetch!="function")throw new T("Global fetch is unavailable in this runtime; pass options.fetch explicitly.");return globalThis.fetch.bind(globalThis)}a(Lt,"resolveFetch");function je(r){if(!r||typeof r!="object")throw new T("createWorkBuddyCloud requires publishableKey.");return Object.freeze({endpoint:It(r.endpoint),oauthRelayBaseUrl:r.oauthRelayBaseUrl?Le(r.oauthRelayBaseUrl,"oauthRelayBaseUrl"):"",publishableKey:Ct(r.publishableKey),fetch:Lt(r.fetch)})}a(je,"resolveRuntimeConfig");var be="x-wb-webapp-access-key";function we(r,e){return async(t,s)=>{let n=new Headers(s?.headers);if(n.set(be,r.publishableKey),!n.has("Authorization")){let i=await e();i&&n.set("Authorization",`Bearer ${i}`)}return r.fetch(t,{...s,headers:n})}}a(we,"createCloudFetch");var oe=a(()=>Promise.resolve(void 0),"anonymousTokenProvider");var j="/.cloud",R=Object.freeze({auth:`${j}/auth`,database:`${j}/database/rest`,storage:`${j}/storage`,llm:`${j}/llm`});var jt="workbuddy-cloud.pkce.workbuddy.",Bt="workbuddy-cloud.pkce-done.workbuddy.";function Be(r){let e="";for(let t of r)e+=String.fromCharCode(t);return btoa(e).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"")}a(Be,"base64UrlEncode");function De(){let r=globalThis.crypto;return typeof r?.getRandomValues=="function"&&typeof r?.subtle?.digest=="function"&&typeof globalThis.btoa=="function"}a(De,"hasWebCrypto");function Ne(){let r=new Uint8Array(32);return globalThis.crypto.getRandomValues(r),Be(r)}a(Ne,"createCodeVerifier");async function Me(r){let e=new TextEncoder().encode(r),t=await globalThis.crypto.subtle.digest("SHA-256",e);return Be(new Uint8Array(t))}a(Me,"computeS256Challenge");var ae=class{static{a(this,"WorkBuddyPkceStore")}verifierKey;consumedKey;constructor(e){this.verifierKey=jt+e,this.consumedKey=Bt+e}usable(){let e=this.storage();if(!e)return!1;try{let t=`${this.verifierKey}.probe`;return e.setItem(t,"1"),e.removeItem(t),!0}catch{return!1}}saveVerifier(e){try{let t=this.storage();return t?(t.setItem(this.verifierKey,e),t.removeItem(this.consumedKey),!0):!1}catch{return!1}}readVerifier(){try{return this.storage()?.getItem(this.verifierKey)??null}catch{return null}}clearVerifier(){try{this.storage()?.removeItem(this.verifierKey)}catch{}}markConsumed(e){try{this.storage()?.setItem(this.consumedKey,e)}catch{}}isConsumed(e){try{return!!e&&this.storage()?.getItem(this.consumedKey)===e}catch{return!1}}storage(){try{return globalThis.sessionStorage??null}catch{return null}}};var b={signUp:"/v1/signup",signIn:"/v1/signin",signInWithProvider:"/v1/signin/with/provider",token:"/v1/token",loginWechat:"/v1/login-wechat",loginWechatWeb:"/v1/login-wechat-web",loginWorkBuddy:"/v1/login-workbuddy",loginWorkBuddyMiniProgram:"/v1/login-workbuddy-miniprogram",signOut:"/v1/user/signout",userMe:"/v1/user/me",verification:"/v1/verification",verificationVerify:"/v1/verification/verify",resetPassword:"/v1/reset",sudo:"/v1/user/sudo",userPassword:"/v1/user/password"};function Se(r,e){let t=r??{},s=typeof t.access_token=="string"?t.access_token:"";if(!s)throw Mt("response has no access_token");let n=typeof t.refresh_token=="string"?t.refresh_token:"",i=typeof t.expires_in=="number"?t.expires_in:0;return{accessToken:s,refreshToken:n,expiresAt:e+i*1e3,user:Dt(t)}}a(Se,"parseSession");function Dt(r){let e=r.is_anonymous===!0;return{id:typeof r.sub=="string"?r.sub:"",name:O(r.name),avatarUrl:O(r.avatar_url),isAnonymous:e,raw:r}}a(Dt,"userFromSessionPayload");function Fe(r){let e=r??{},t=typeof e.sub=="string"?e.sub:typeof e.uid=="string"?e.uid:"",s=e.user_metadata??{};return{id:t,email:O(e.email)??O(s.email),phone:O(e.phone_number)??O(e.phone),name:O(e.name),avatarUrl:O(e.avatar_url),isAnonymous:e.is_anonymous===!0||e.scope==="anonymous",raw:e}}a(Fe,"parseUser");function O(r){return typeof r=="string"&&r!==""?r:void 0}a(O,"pickString");function qe(r,e){let t=e??{},s=typeof t.error=="string"?t.error:void 0,n=O(t.error_description)??O(t.message)??O(t.msg)??`HTTP ${r}`;return{kind:Nt(r,s),message:n,status:r,code:s,cause:e}}a(qe,"normalizeHttpError");function Nt(r,e){if(e==="invalid_grant")return"unauthenticated";switch(r){case 400:return"invalid-request";case 401:return"unauthenticated";case 403:return"permission-denied";case 404:return"not-found";case 429:return"rate-limited";case 501:return"unimplemented";case 503:return"backend-unavailable";default:return r>=500?"backend-unavailable":"unknown"}}a(Nt,"errorKind");function K(r){return{kind:"network",message:`request failed before a response was received: ${r instanceof Error?r.message:String(r)}`,status:0,cause:r}}a(K,"normalizeNetworkError");function Mt(r){let e=new Error(`workbuddy-cloud auth: ${r}`);return e.kind="unknown",e.status=0,e}a(Mt,"sessionShapeError");var ce=class{static{a(this,"SessionManager")}store;refresh;emit;isCredentialsRejected;now;inflight=null;signOutEpoch=0;lastFailure=null;constructor(e){this.store=e.store,this.refresh=e.refresh,this.emit=e.emit,this.isCredentialsRejected=e.isCredentialsRejected,this.now=e.now??Date.now}peek(){return this.store.read()}async ensure(){let e=this.store.read();return e?this.isExpiring(e)?e.refreshToken?this.refreshOnce(e):this.abandon():e:null}async forceRefresh(){let e=this.store.read();return e?.refreshToken?this.refreshOnce(e,{ignoreCooldown:!0}):null}commitSignIn(e){return this.lastFailure=null,this.store.write(e),this.emit("SIGNED_IN",e),e}commitUserUpdate(e){return this.store.write(e),this.emit("USER_UPDATED",e),e}clear(){this.signOutEpoch+=1,this.lastFailure=null,this.inflight=null,this.store.clear(),this.emit("SIGNED_OUT",null)}isExpiring(e){return typeof e.expiresAt!="number"?!0:e.expiresAt-this.now()<9e4}refreshOnce(e,t={}){if(this.inflight)return this.inflight;if(!t.ignoreCooldown&&this.inCooldown(e.refreshToken))return Promise.resolve(null);let s=this.doRefresh(e).finally(()=>{this.inflight=null});return this.inflight=s,s}inCooldown(e){let t=this.lastFailure;return t!==null&&t.token===e&&this.now()-t.at<6e4}async doRefresh(e){let t=this.signOutEpoch,s=e.refreshToken,n;try{n=await this.refresh(s)}catch(o){return this.onRefreshFailed(s,o)}if(this.signOutEpoch!==t)return this.store.clear(),null;let i=this.store.read();return i&&i.refreshToken!==s?i:(this.lastFailure=null,this.store.write(n),this.emit("TOKEN_REFRESHED",n),n)}onRefreshFailed(e,t){return this.isCredentialsRejected(t)?this.abandon():(this.lastFailure={token:e,at:this.now()},null)}abandon(){return this.store.clear(),this.lastFailure=null,this.emit("SIGNED_OUT",null),null}};var Ft="workbuddy-cloud.session.";function ke(){let r=new Map;return{getItem:a(e=>r.get(e)??null,"getItem"),setItem:a((e,t)=>{r.set(e,t)},"setItem"),removeItem:a(e=>{r.delete(e)},"removeItem")}}a(ke,"createMemoryStorage");function We(r){if(r)return r;try{let e="__workbuddy_probe__";return globalThis.localStorage.setItem(e,"1"),globalThis.localStorage.removeItem(e),globalThis.localStorage}catch{return ke()}}a(We,"resolveStorage");var ue=class{static{a(this,"SessionStore")}storage;key;constructor(e,t){this.storage=e,this.key=Ft+t}read(){let e;try{e=this.storage.getItem(this.key)}catch{return null}if(!e)return null;try{let t=JSON.parse(e);return qt(t)?t:this.discard()}catch{return this.discard()}}write(e){try{this.storage.setItem(this.key,JSON.stringify(e))}catch{}}clear(){try{this.storage.removeItem(this.key)}catch{}}discard(){return this.clear(),null}};function qt(r){if(!r||typeof r!="object")return!1;let e=r;return typeof e.accessToken=="string"&&e.accessToken!==""&&typeof e.refreshToken=="string"&&typeof e.expiresAt=="number"&&!!e.user&&typeof e.user=="object"}a(qt,"isStoredSession");function B(r,e){let t=r.email??"",s=r.phone??"";return!!t==!!s?{data:null,error:{kind:"invalid-request",message:`${e} requires exactly one of email or phone`,status:0}}:{data:t?{kind:"email",value:t,username:t}:{kind:"phone",value:s,username:Wt(s)},error:null}}a(B,"resolveAuthIdentifier");function Wt(r){let t=r.replace(/\D/g,"");return t.startsWith("0086")?t=t.slice(4):t.startsWith("86")&&t.length===13&&(t=t.slice(2)),/^1\d{10}$/.test(t)?`+86 ${t}`:r}a(Wt,"normalizePhone");var He="wx907c65e5e107ddcf",Ht="subpackages/secondary/oauth-authorize/index";var de=class{static{a(this,"WorkBuddyMiniProgramAuth")}storage;platform;exchange;key;starting;exchanges=new Map;constructor(e,t,s,n){this.storage=t,this.platform=s,this.exchange=n,this.key=`workbuddy-cloud.miniprogram-workbuddy.${e}`}async signIn(e){if(this.starting)return this.starting;let t=this.start(e);this.starting=t;try{return await t}finally{this.starting=void 0}}async start(e){if(typeof e?.redirectPath!="string"||!e.redirectPath.trim())return P("invalid_request","WorkBuddy login requires redirectPath");let t=this.platform.applicationId;if(typeof t!="string"||!t.trim())return P("invalid_request","WorkBuddy login requires publicConfig.workBuddyOAuthClientId");try{let s=this.platform.getEnvVersion?.(),n=await this.platform.createState(),i={state:n,appId:He,expiresAt:Date.now()+6e5},o=JSON.stringify(i);if(this.storage.setItem(this.key,o),this.storage.getItem(this.key)!==o)return P("storage_unavailable","Could not persist WorkBuddy login; sign in again");let c=await this.platform.navigate({appId:He,path:`${Ht}?client_id=${encodeURIComponent(t)}&redirect_uri=${encodeURIComponent(e.redirectPath)}&state=${encodeURIComponent(n)}`+(s?`&envVersion=${s}`:""),envVersion:"release"});return c.error&&this.storage.removeItem(this.key),c}catch(s){return P("miniprogram_login_failed",xe(s))}}async handleCallback(e){let t=e?.referrerInfo,s=Ke(t?.extraData);if(!s||!s.code&&!s.error)return{data:null,error:null};let n=typeof s.state=="string"?this.exchanges.get(s.state):void 0;if(n)return t?.appId===n.appId?n.task:P("invalid_request","WorkBuddy callback does not match the login source");let i;try{i=this.readPending()}catch(c){return P("storage_unavailable",xe(c))}if(!i)return{data:null,error:null};if(typeof s.state!="string"||!s.state)return P("invalid_request","WorkBuddy callback requires state");if(t?.appId!==i.appId||s.state!==i.state)return P("invalid_request","WorkBuddy callback does not match the login source or state");if(!(typeof s.code=="string"&&s.code)&&!(typeof s.error=="string"&&s.error))return P("invalid_request","WorkBuddy callback has no authorization code");if(!s.error&&(typeof s.redirect_uri!="string"||!s.redirect_uri.trim()))return P("invalid_request","WorkBuddy callback requires redirect_uri");try{if(this.storage.removeItem(this.key),this.storage.getItem(this.key)!==null)return P("storage_unavailable","Could not consume WorkBuddy login; sign in again")}catch(c){return P("storage_unavailable",xe(c))}if(i.expiresAt<=Date.now())return P("invalid_grant","WorkBuddy login expired; sign in again","unauthenticated");if(s.error)return P(String(s.error),typeof s.error_description=="string"?s.error_description:"WorkBuddy authorization was not completed","permission-denied");let o=this.exchange({code:s.code,state:i.state,shortlink:s.redirect_uri});this.exchanges.set(i.state,{appId:i.appId,task:o});try{return await o}finally{this.exchanges.delete(i.state)}}readPending(){let e=this.storage.getItem(this.key);if(!e)return null;let t=Ke(JSON.parse(e));if(!t||typeof t.state!="string"||typeof t.appId!="string"||typeof t.expiresAt!="number")throw new Error("Invalid saved WorkBuddy login; sign in again");return t}};function Ke(r){return r!==null&&typeof r=="object"&&!Array.isArray(r)?r:null}a(Ke,"record");function P(r,e,t="invalid-request"){return{data:null,error:{kind:t,code:r,message:e,status:0}}}a(P,"failure");function xe(r){return r instanceof Error?r.message:String(r)}a(xe,"describe");var Ge=200;function Je(r,e){let t=Array.from(r);return t.length<=e?r:`${t.slice(0,e).join("")}\u2026`}a(Je,"truncateMessage");function Ee(r){let e=r.get("error");if(!e)return null;let t=r.get("error_description"),s=t?`oauth provider rejected the request: ${e}: ${t}`:`oauth provider rejected the request: ${e}`;return Je(s,Ge)}a(Ee,"oauthProviderRejectMessage");var D=class{static{a(this,"AuthModule")}fetch;baseUrl;sessions;storage;oauthRelayBaseUrl;workBuddyPkce;workBuddyMiniProgram;workBuddyExchanges=new Map;listeners=new Map;nextListenerId=1;constructor(e,t,s={}){this.fetch=t,this.baseUrl=`${e.endpoint}${R.auth}`,this.oauthRelayBaseUrl=e.oauthRelayBaseUrl,this.storage=We(s.storage),this.workBuddyPkce=new ae(e.publishableKey),this.sessions=new ce({store:new ue(this.storage,e.publishableKey),refresh:a(n=>this.exchangeRefreshHandle(n),"refresh"),emit:a((n,i)=>this.notify(n,i),"emit"),isCredentialsRejected:a(n=>le(n)&&Ve(n),"isCredentialsRejected")}),s.workBuddyMiniProgram&&(this.workBuddyMiniProgram=new de(e.publishableKey,this.storage,s.workBuddyMiniProgram,n=>this.postForSession(b.loginWorkBuddyMiniProgram,n)))}async getAccessToken(){return(await this.sessions.ensure())?.accessToken}async signInWithWorkBuddyMiniProgram(e){return this.workBuddyMiniProgram?this.workBuddyMiniProgram.signIn(e):h({kind:"unimplemented",status:0,message:"Use createMiniProgramWorkBuddyCloud for WorkBuddy mini program login"})}async handleWorkBuddyMiniProgramCallback(e){return this.workBuddyMiniProgram?this.workBuddyMiniProgram.handleCallback(e):h({kind:"unimplemented",status:0,message:"Use createMiniProgramWorkBuddyCloud for WorkBuddy mini program login"})}async signInWithPassword(e){if(!e.password)return h(p("signInWithPassword requires a password"));let t=B(e,"signInWithPassword");return t.error?h(t.error):this.postForSession(b.signIn,{username:t.data.username,password:e.password})}async signInWithWechat(e,t){return e?t?this.postForSession(b.loginWechat,{code:e,appid:t}):h(p("signInWithWechat requires appid")):h(p("signInWithWechat requires code"))}async signUp(e){let t=B(e,"signUp");if(t.error)return h(t.error);if(!e.verificationToken)return h(p("signUp requires a verificationToken; run sendOtp + verifyOtp first (the provider rejects username+password-only signup)"));let s={verification_token:e.verificationToken};return t.data.kind==="phone"?s.phone_number=t.data.username:s.email=t.data.username,e.password&&(s.password=e.password),this.postForSession(b.signUp,s)}async sendOtp(e){let t=B(e,"sendOtp");if(t.error)return h(t.error);let s={};t.data.kind==="phone"?(s.phone_number=t.data.username,s.target="ANY"):(s.email=t.data.username,s.usage="email",e.emailRedirectTo&&(s.email_redirect_to=e.emailRedirectTo));let n=await this.request(b.verification,{method:"POST",body:s});if(n.error)return h(n.error);let i=n.data??{},o=typeof i.verification_id=="string"?i.verification_id:"";return o?S({verificationId:o,isExistingUser:i.is_user===!0}):h(p("provider returned no verification_id"))}async signInWithOtp(e){let t=B(e,"signInWithOtp");if(t.error)return h(t.error);let s=await this.sendOtp(e);if(s.error)return h(s.error);let{verificationId:n,isExistingUser:i}=s.data,o=t.data.kind==="phone"?{phone:t.data.username}:{email:t.data.username};return S({verificationId:n,isExistingUser:i,isUser:i,verify:a(({token:c,password:u})=>this.verifyOtp({verificationId:n,token:c,...o,isExistingUser:i,password:u}),"verify")})}async verifyOtp(e){let t=B(e,"verifyOtp");if(t.error)return h(t.error);if(!e.verificationId||!e.token)return h(p("verifyOtp requires verificationId and token"));let s=await this.request(b.verificationVerify,{method:"POST",body:{verification_id:e.verificationId,verification_code:e.token}});if(s.error)return h(s.error);let n=s.data??{},i=typeof n.verification_token=="string"?n.verification_token:"";if(!i)return h(p("provider returned no verification_token"));if(e.isExistingUser)return this.postForSession(b.signIn,{username:t.data.username,verification_token:i});let o=t.data.kind==="phone"?{phone:t.data.value,password:e.password}:{email:t.data.value,password:e.password};return this.signUp({...o,verificationToken:i})}async signInWithOAuth(e){if(!this.oauthRelayBaseUrl)return h(p("signInWithOAuth requires oauthRelayBaseUrl"));if(e.provider!=="google"&&e.provider!=="wechat"&&e.provider!=="workbuddy")return h(p("\u5F53\u524D SDK \u4E0D\u652F\u6301\u8BE5\u767B\u5F55\u65B9\u5F0F\uFF0C\u8BF7\u68C0\u67E5 SDK \u7248\u672C\u4E0E\u767B\u5F55\u914D\u7F6E\u3002"));let t=e.redirectTo??zt();return t?this.startRelayOAuth(e,t):h(p("signInWithOAuth requires redirectTo outside a browser environment"))}parseCallbackQuery(e){try{let t=/^https?:\/\//i.test(e)?new URL(e).search:e;return S(new URLSearchParams(t))}catch{return h(p("oauth callback URL is invalid"))}}async handleOAuthCallback(e){let t=this.parseCallbackQuery(e??ve());if(t.error||!t.data)return h(t.error??p("oauth callback URL is invalid"));let s=t.data,n=Ee(s);if(n)return h({kind:"unauthenticated",message:n,status:0});let i=s.get("code");if(!i)return S(null);let o=s.get("state")??"";if(!o)return h(p("oauth callback requires state"));let c=s.get("provider_id");if(c!=="custom-oauth")return h(p("oauth callback requires provider_id=custom-oauth"));let u={provider_id:c,provider_code:i,state:o,provider_params:{state:o}};return this.postForSession(b.signInWithProvider,u)}async handleWechatWebCallback(e){let t=this.parseCallbackQuery(e??ve());if(t.error||!t.data)return h(t.error??p("oauth callback URL is invalid"));let s=t.data,n=Ee(s);if(n)return h({kind:"unauthenticated",message:n,status:0});let i=s.get("code");if(!i)return S(null);let o=s.get("state")??"";if(!o)return h(p("oauth callback requires state"));let c=s.get("provider");return c&&c!=="wechat"?h(p("wechat callback requires provider=wechat")):s.get("provider_id")==="custom-oauth"?h(p("wechat callback must not use provider_id=custom-oauth")):this.postForSession(b.loginWechatWeb,{code:i,state:o})}async handleWorkBuddyCallback(e){let t=this.parseCallbackQuery(e??ve());if(t.error||!t.data)return h(t.error??p("oauth callback URL is invalid"));let s=t.data,n=s.get("provider");if(n&&n!=="workbuddy")return S(null);let i=Ee(s);if(i)return this.workBuddyPkce.clearVerifier(),h({kind:"unauthenticated",message:i,status:0});let o=s.get("code");if(!o)return S(null);let c=s.get("state")??"";if(!c)return h(p("workbuddy callback requires state"));if(s.get("provider_id")==="custom-oauth")return h(p("workbuddy callback must not use provider_id=custom-oauth"));if(this.workBuddyPkce.isConsumed(c))return S(null);let u=this.workBuddyExchanges.get(c);if(u)return u;let d=this.workBuddyPkce.readVerifier();if(!d)return h(p("workbuddy callback has no local PKCE verifier; sign in again in this tab"));this.workBuddyPkce.clearVerifier();let l=this.exchangeWorkBuddyCode(o,c,d);this.workBuddyExchanges.set(c,l);try{return await l}finally{this.workBuddyExchanges.delete(c)}}async exchangeWorkBuddyCode(e,t,s){let n=await this.postForSession(b.loginWorkBuddy,{code:e,state:t,code_verifier:s});return n.data&&this.workBuddyPkce.markConsumed(t),n}async resetPasswordForEmail(e){if(!e)return h(p("resetPasswordForEmail requires email"));let t=await this.request(b.verification,{method:"POST",body:{email:e,usage:"PASSWORD_RESET",target:"USER"}});if(t.error)return h(t.error);let s=t.data??{},n=typeof s.verification_id=="string"?s.verification_id:"";return n?S({updateUser:a(async({nonce:i,password:o})=>{let c=await this.request(b.verificationVerify,{method:"POST",body:{verification_id:n,verification_code:i}});if(c.error)return h(c.error);let u=c.data??{},d=typeof u.verification_token=="string"?u.verification_token:"";if(!d)return h(p("provider returned no verification_token"));let l=await this.request(b.resetPassword,{method:"POST",body:{email:e,new_password:o,verification_token:d}});if(l.error)return h(l.error);let f=await this.signInWithPassword({email:e,password:o});return f.error||this.notify("PASSWORD_RECOVERY",f.data),f},"updateUser")}):h(p("provider returned no verification_id"))}async resetPasswordForOld(e){let t=await this.getAccessToken();if(!t)return h({kind:"unauthenticated",message:"no active session",status:0});let s=await this.request(b.sudo,{method:"POST",token:t,body:{password:e.oldPassword}});if(s.error)return h(s.error);let n=s.data??{},i=typeof n.sudo_token=="string"?n.sudo_token:"";if(!i)return h(p("provider returned no sudo_token"));let o=await this.request(b.userPassword,{method:"PATCH",token:t,body:{sudo_token:i,new_password:e.newPassword}});if(o.error)return h(o.error);let c=await this.getSession();return c.data?(this.notify("USER_UPDATED",c.data),S(c.data)):h(c.error??{kind:"unauthenticated",message:"no active session",status:0})}async getSession(){try{return S(await this.sessions.ensure())}catch(e){return h(le(e)?e:K(e))}}async refreshSession(){try{return S(await this.sessions.forceRefresh())}catch(e){return h(le(e)?e:K(e))}}async getUser(){let e=await this.getAccessToken();if(!e)return h({kind:"unauthenticated",message:"no active session",status:0});let t=await this.request(b.userMe,{method:"GET",token:e});return t.error?(Ve(t.error)&&this.sessions.clear(),h(t.error)):S(Fe(t.data))}async signOut(){let e=this.sessions.peek();return e?.accessToken&&await this.request(b.signOut,{method:"POST",body:{},token:e.accessToken}),this.sessions.clear(),S(null)}onAuthStateChange(e){let t=this.nextListenerId++;return this.listeners.set(t,e),ze(e,"INITIAL_SESSION",this.sessions.peek()),()=>{this.listeners.delete(t)}}async startRelayOAuth(e,t){let s;try{s=new URL(t)}catch{return h(p("signInWithOAuth requires an absolute redirectTo URL"))}let n=new URL(`${this.oauthRelayBaseUrl}/authorize`);if(n.searchParams.set("provider",e.provider),n.searchParams.set("callback_url",s.toString()),e.provider==="workbuddy"){let i=await this.createWorkBuddyProof();if(i.error||!i.data)return h(i.error??p("signInWithOAuth could not create PKCE"));n.searchParams.set("code_challenge",i.data),n.searchParams.set("code_challenge_method","S256")}return S({url:n.toString()})}async createWorkBuddyProof(){if(!De())return h(p("workbuddy sign-in requires WebCrypto; it is unavailable in this runtime (an insecure http:// origin disables it \u2014 serve the app over https)"));if(!this.workBuddyPkce.usable())return h(p("workbuddy sign-in requires sessionStorage to keep the PKCE verifier across the redirect; it is unavailable in this runtime"));let e,t;try{e=Ne(),t=await Me(e)}catch(s){return h(p(`workbuddy sign-in could not create a PKCE proof: ${Kt(s)}`))}return this.workBuddyPkce.saveVerifier(e)?S(t):h(p("workbuddy sign-in could not persist the PKCE verifier"))}async exchangeRefreshHandle(e){let t=await this.request(b.token,{method:"POST",body:{grant_type:"refresh_token",refresh_token:e}});if(t.error)throw t.error;return Se(t.data,Date.now())}async postForSession(e,t,s={}){let n=await this.request(e,{method:"POST",body:t,headers:s.headers});if(n.error)return h(n.error);try{return S(this.sessions.commitSignIn(Se(n.data,Date.now())))}catch(i){return h(le(i)?i:K(i))}}async request(e,t){let s={...t.headers};t.body!==void 0&&(s["Content-Type"]="application/json"),t.token&&(s.Authorization=`Bearer ${t.token}`);let n;try{n=await this.fetch(this.baseUrl+e,{method:t.method,headers:s,body:t.body===void 0?void 0:JSON.stringify(t.body)})}catch(o){return h(K(o))}let i=await Vt(n);return n.ok?S(i):h(qe(n.status,i))}notify(e,t){for(let s of this.listeners.values())ze(s,e,t)}};function S(r){return{data:r,error:null}}a(S,"ok");function h(r){return{data:null,error:r}}a(h,"fail");function p(r){return{kind:"invalid-request",message:r,status:0}}a(p,"badRequest");function Kt(r){return Je(r instanceof Error?r.message:String(r),Ge)}a(Kt,"describeError");function le(r){return!!r&&typeof r=="object"&&typeof r.kind=="string"}a(le,"isCloudError");function Ve(r){return r.kind==="unauthenticated"||r.code==="invalid_grant"}a(Ve,"rejectedCredentials");async function Vt(r){let e=await r.text();if(!e)return null;try{return JSON.parse(e)}catch{return{message:e}}}a(Vt,"readBody");function ze(r,e,t){try{r(e,t)}catch{}}a(ze,"safeInvoke");function zt(){let r=globalThis.location;return r?r.origin+r.pathname:""}a(zt,"currentPageUrl");function ve(){return globalThis.location?.search??""}a(ve,"currentPageSearch");var Pe=a(r=>Math.min(1e3*2**r,3e4),"getRetryDelay"),Ye=[520,503],_e=["GET","HEAD","OPTIONS"];var I=class extends Error{static{a(this,"PostgrestError")}details;hint;code;constructor(e){super(e.message),this.name="PostgrestError",this.details=e.details,this.hint=e.hint,this.code=e.code}toJSON(){return{name:this.name,message:this.message,details:this.details,hint:this.hint,code:this.code}}};function Xe(r,e){return new Promise(t=>{if(e?.aborted){t();return}let s=setTimeout(()=>{e?.removeEventListener("abort",n),t()},r);function n(){clearTimeout(s),t()}a(n,"onAbort"),e?.addEventListener("abort",n)})}a(Xe,"sleep");function Gt(r,e,t,s){return!(!s||t>=3||!_e.includes(r)||!Ye.includes(e))}a(Gt,"shouldRetry");var V=class{static{a(this,"PostgrestBuilder")}method;url;headers;schema;body;shouldThrowOnError=!1;signal;fetch;isMaybeSingle;shouldStripNulls;urlLengthLimit;retryEnabled=!0;constructor(e){this.method=e.method,this.url=e.url,this.headers=new Headers(e.headers),this.schema=e.schema,this.body=e.body,this.shouldThrowOnError=e.shouldThrowOnError??!1,this.signal=e.signal,this.isMaybeSingle=e.isMaybeSingle??!1,this.shouldStripNulls=e.shouldStripNulls??!1,this.urlLengthLimit=e.urlLengthLimit??8e3,this.retryEnabled=e.retry??!0,e.fetch?this.fetch=e.fetch:this.fetch=fetch}throwOnError(){return this.shouldThrowOnError=!0,this}stripNulls(){if(this.headers.get("Accept")==="text/csv")throw new Error("stripNulls() cannot be used with csv()");return this.shouldStripNulls=!0,this}setHeader(e,t){return this.headers=new Headers(this.headers),this.headers.set(e,t),this}retry(e){return this.retryEnabled=e,this}then(e,t){if(this.schema===void 0||(["GET","HEAD"].includes(this.method)?this.headers.set("Accept-Profile",this.schema):this.headers.set("Content-Profile",this.schema)),this.method!=="GET"&&this.method!=="HEAD"&&this.headers.set("Content-Type","application/json"),this.shouldStripNulls){let o=this.headers.get("Accept");o==="application/vnd.pgrst.object+json"?this.headers.set("Accept","application/vnd.pgrst.object+json;nulls=stripped"):(!o||o==="application/json")&&this.headers.set("Accept","application/vnd.pgrst.array+json;nulls=stripped")}let s=this.fetch,i=a(async()=>{let o=0;for(;;){let c={};this.headers.forEach((d,l)=>{c[l]=d}),o>0&&(c["X-Retry-Count"]=String(o));let u;try{u=await s(this.url.toString(),{method:this.method,headers:c,body:JSON.stringify(this.body,(d,l)=>typeof l=="bigint"?l.toString():l),signal:this.signal})}catch(d){if(d?.name==="AbortError"||d?.code==="ABORT_ERR"||!_e.includes(this.method))throw d;if(this.retryEnabled&&o<3){let l=Pe(o);o++,await Xe(l,this.signal);continue}throw d}if(Gt(this.method,u.status,o,this.retryEnabled)){let d=u.headers?.get("Retry-After")??null,l=d!==null?Math.max(0,parseInt(d,10)||0)*1e3:Pe(o);await u.text(),o++,await Xe(l,this.signal);continue}return await this.processResponse(u)}},"executeWithRetry")();return this.shouldThrowOnError||(i=i.catch(o=>{let c="",u="",d="",l=o?.cause;if(l){let g=l?.message??"",y=l?.code??"";c=`${o?.name??"FetchError"}: ${o?.message}`,c+=`
    
    Caused by: ${l?.name??"Error"}: ${g}`,y&&(c+=` (${y})`),l?.stack&&(c+=`
    ${l.stack}`)}else c=o?.stack??"";let f=this.url.toString().length;return o?.name==="AbortError"||o?.code==="ABORT_ERR"?(d="",u="Request was aborted (timeout or manual cancellation)",f>this.urlLengthLimit&&(u+=`. Note: Your request URL is ${f} characters, which may exceed server limits. If selecting many fields, consider using views. If filtering with large arrays (e.g., .in('id', [many IDs])), consider using an RPC function to pass values server-side.`)):(l?.name==="HeadersOverflowError"||l?.code==="UND_ERR_HEADERS_OVERFLOW")&&(d="",u="HTTP headers exceeded server limits (typically 16KB)",f>this.urlLengthLimit&&(u+=`. Your request URL is ${f} characters. If selecting many fields, consider using views. If filtering with large arrays (e.g., .in('id', [200+ IDs])), consider using an RPC function instead.`)),{success:!1,error:{message:`${o?.name??"FetchError"}: ${o?.message}`,details:c,hint:u,code:d},data:null,count:null,status:0,statusText:""}})),i.then(e,t)}async processResponse(e){let t=null,s=null,n=null,i=e.status,o=e.statusText;if(e.ok){if(this.method!=="HEAD"){let d=await e.text();if(d!=="")if(this.headers.get("Accept")==="text/csv")s=d;else if(this.headers.get("Accept")&&this.headers.get("Accept")?.includes("application/vnd.pgrst.plan+text"))s=d;else try{s=JSON.parse(d)}catch{if(t={message:d},s=null,this.shouldThrowOnError)throw new I({message:d,details:"",hint:"",code:""})}}let c=this.headers.get("Prefer")?.match(/count=(exact|planned|estimated)/),u=e.headers.get("content-range")?.split("/");if(c&&u&&u.length>1&&(n=parseInt(u[1])),this.isMaybeSingle&&Array.isArray(s))if(s.length>1){if(t={code:"PGRST116",details:`Results contain ${s.length} rows, application/vnd.pgrst.object+json requires 1 row`,hint:null,message:"JSON object requested, multiple (or no) rows returned"},s=null,n=null,i=406,o="Not Acceptable",this.shouldThrowOnError)throw new I({...t,hint:t.hint??""})}else s.length===1?s=s[0]:s=null}else{let c=await e.text();try{t=JSON.parse(c),Array.isArray(t)&&e.status===404&&(s=[],t=null,i=200,o="OK")}catch{e.status===404&&c===""?(i=204,o="No Content"):t={message:c}}if(t&&this.shouldThrowOnError)throw new I(t)}return{success:t===null,error:t,data:s,count:n,status:i,statusText:o}}returns(){return this}overrideTypes(){return this}};var z=class extends V{static{a(this,"PostgrestTransformBuilder")}throwOnError(){return super.throwOnError()}select(e){let t=!1,s=(e??"*").split("").map(n=>/\s/.test(n)&&!t?"":(n==='"'&&(t=!t),n)).join("");return this.url.searchParams.set("select",s),this.headers.append("Prefer","return=representation"),this}order(e,{ascending:t=!0,nullsFirst:s,foreignTable:n,referencedTable:i=n}={}){let o=i?`${i}.order`:"order",c=this.url.searchParams.get(o);return this.url.searchParams.set(o,`${c?`${c},`:""}${e}.${t?"asc":"desc"}${s===void 0?"":s?".nullsfirst":".nullslast"}`),this}limit(e,{foreignTable:t,referencedTable:s=t}={}){let n=typeof s>"u"?"limit":`${s}.limit`;return this.url.searchParams.set(n,`${e}`),this}range(e,t,{foreignTable:s,referencedTable:n=s}={}){let i=typeof n>"u"?"offset":`${n}.offset`,o=typeof n>"u"?"limit":`${n}.limit`;return this.url.searchParams.set(i,`${e}`),this.url.searchParams.set(o,`${t-e+1}`),this}abortSignal(e){return this.signal=e,this}single(){return this.headers.set("Accept","application/vnd.pgrst.object+json"),this}maybeSingle(){return this.isMaybeSingle=!0,this}csv(){return this.headers.set("Accept","text/csv"),this}geojson(){return this.headers.set("Accept","application/geo+json"),this}explain({analyze:e=!1,verbose:t=!1,settings:s=!1,buffers:n=!1,wal:i=!1,format:o="text"}={}){let c=[e?"analyze":null,t?"verbose":null,s?"settings":null,n?"buffers":null,i?"wal":null].filter(Boolean).join("|"),u=this.headers.get("Accept")??"application/json";return this.headers.set("Accept",`application/vnd.pgrst.plan+${o}; for="${u}"; options=${c};`),o==="json"?this:this}rollback(){return this.headers.append("Prefer","tx=rollback"),this}returns(){return this}maxAffected(e){return this.headers.append("Prefer","handling=strict"),this.headers.append("Prefer",`max-affected=${e}`),this}};var Ze=new RegExp("[,()]"),A=class extends z{static{a(this,"PostgrestFilterBuilder")}throwOnError(){return super.throwOnError()}eq(e,t){return this.url.searchParams.append(e,`eq.${t}`),this}neq(e,t){return this.url.searchParams.append(e,`neq.${t}`),this}gt(e,t){return this.url.searchParams.append(e,`gt.${t}`),this}gte(e,t){return this.url.searchParams.append(e,`gte.${t}`),this}lt(e,t){return this.url.searchParams.append(e,`lt.${t}`),this}lte(e,t){return this.url.searchParams.append(e,`lte.${t}`),this}like(e,t){return this.url.searchParams.append(e,`like.${t}`),this}likeAllOf(e,t){return this.url.searchParams.append(e,`like(all).{${t.join(",")}}`),this}likeAnyOf(e,t){return this.url.searchParams.append(e,`like(any).{${t.join(",")}}`),this}ilike(e,t){return this.url.searchParams.append(e,`ilike.${t}`),this}ilikeAllOf(e,t){return this.url.searchParams.append(e,`ilike(all).{${t.join(",")}}`),this}ilikeAnyOf(e,t){return this.url.searchParams.append(e,`ilike(any).{${t.join(",")}}`),this}regexMatch(e,t){return this.url.searchParams.append(e,`match.${t}`),this}regexIMatch(e,t){return this.url.searchParams.append(e,`imatch.${t}`),this}is(e,t){return this.url.searchParams.append(e,`is.${t}`),this}isDistinct(e,t){return this.url.searchParams.append(e,`isdistinct.${t}`),this}in(e,t){let s=Array.from(new Set(t)).map(n=>typeof n=="string"&&Ze.test(n)?`"${n}"`:`${n}`).join(",");return this.url.searchParams.append(e,`in.(${s})`),this}notIn(e,t){let s=Array.from(new Set(t)).map(n=>typeof n=="string"&&Ze.test(n)?`"${n}"`:`${n}`).join(",");return this.url.searchParams.append(e,`not.in.(${s})`),this}contains(e,t){return typeof t=="string"?this.url.searchParams.append(e,`cs.${t}`):Array.isArray(t)?this.url.searchParams.append(e,`cs.{${t.join(",")}}`):this.url.searchParams.append(e,`cs.${JSON.stringify(t)}`),this}containedBy(e,t){return typeof t=="string"?this.url.searchParams.append(e,`cd.${t}`):Array.isArray(t)?this.url.searchParams.append(e,`cd.{${t.join(",")}}`):this.url.searchParams.append(e,`cd.${JSON.stringify(t)}`),this}rangeGt(e,t){return this.url.searchParams.append(e,`sr.${t}`),this}rangeGte(e,t){return this.url.searchParams.append(e,`nxl.${t}`),this}rangeLt(e,t){return this.url.searchParams.append(e,`sl.${t}`),this}rangeLte(e,t){return this.url.searchParams.append(e,`nxr.${t}`),this}rangeAdjacent(e,t){return this.url.searchParams.append(e,`adj.${t}`),this}overlaps(e,t){return typeof t=="string"?this.url.searchParams.append(e,`ov.${t}`):this.url.searchParams.append(e,`ov.{${t.join(",")}}`),this}textSearch(e,t,{config:s,type:n}={}){let i="";n==="plain"?i="pl":n==="phrase"?i="ph":n==="websearch"&&(i="w");let o=s===void 0?"":`(${s})`;return this.url.searchParams.append(e,`${i}fts${o}.${t}`),this}match(e){return Object.entries(e).filter(([t,s])=>s!==void 0).forEach(([t,s])=>{this.url.searchParams.append(t,`eq.${s}`)}),this}not(e,t,s){return this.url.searchParams.append(e,`not.${t}.${s}`),this}or(e,{foreignTable:t,referencedTable:s=t}={}){let n=s?`${s}.or`:"or";return this.url.searchParams.append(n,`(${e})`),this}filter(e,t,s){return this.url.searchParams.append(e,`${t}.${s}`),this}};var G=class{static{a(this,"PostgrestQueryBuilder")}url;headers;schema;signal;fetch;urlLengthLimit;retry;constructor(e,{headers:t={},schema:s,fetch:n,urlLengthLimit:i=8e3,retry:o}){this.url=e,this.headers=new Headers(t),this.schema=s,this.fetch=n,this.urlLengthLimit=i,this.retry=o}cloneRequestState(){return{url:new URL(this.url.toString()),headers:new Headers(this.headers)}}select(e,t){let{head:s=!1,count:n}=t??{},i=s?"HEAD":"GET",o=!1,c=(e??"*").split("").map(l=>/\s/.test(l)&&!o?"":(l==='"'&&(o=!o),l)).join(""),{url:u,headers:d}=this.cloneRequestState();return u.searchParams.set("select",c),n&&d.append("Prefer",`count=${n}`),new A({method:i,url:u,headers:d,schema:this.schema,fetch:this.fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}insert(e,{count:t,defaultToNull:s=!0}={}){let n="POST",{url:i,headers:o}=this.cloneRequestState();if(t&&o.append("Prefer",`count=${t}`),s||o.append("Prefer","missing=default"),Array.isArray(e)){let c=e.reduce((u,d)=>u.concat(Object.keys(d)),[]);if(c.length>0){let u=[...new Set(c)].map(d=>`"${d}"`);i.searchParams.set("columns",u.join(","))}}return new A({method:n,url:i,headers:o,schema:this.schema,body:e,fetch:this.fetch??fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}upsert(e,{onConflict:t,ignoreDuplicates:s=!1,count:n,defaultToNull:i=!0}={}){let o="POST",{url:c,headers:u}=this.cloneRequestState();if(u.append("Prefer",`resolution=${s?"ignore":"merge"}-duplicates`),t!==void 0&&c.searchParams.set("on_conflict",t),n&&u.append("Prefer",`count=${n}`),i||u.append("Prefer","missing=default"),Array.isArray(e)){let d=e.reduce((l,f)=>l.concat(Object.keys(f)),[]);if(d.length>0){let l=[...new Set(d)].map(f=>`"${f}"`);c.searchParams.set("columns",l.join(","))}}return new A({method:o,url:c,headers:u,schema:this.schema,body:e,fetch:this.fetch??fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}update(e,{count:t}={}){let s="PATCH",{url:n,headers:i}=this.cloneRequestState();return t&&i.append("Prefer",`count=${t}`),new A({method:s,url:n,headers:i,schema:this.schema,body:e,fetch:this.fetch??fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}delete({count:e}={}){let t="DELETE",{url:s,headers:n}=this.cloneRequestState();return e&&n.append("Prefer",`count=${e}`),new A({method:t,url:s,headers:n,schema:this.schema,fetch:this.fetch??fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}};var N=class r{static{a(this,"PostgrestClient")}url;headers;schemaName;fetch;urlLengthLimit;retry;constructor(e,{headers:t={},schema:s,fetch:n,timeout:i,urlLengthLimit:o=8e3,retry:c}={}){this.url=e,this.headers=new Headers(t),this.schemaName=s,this.urlLengthLimit=o;let u=n??globalThis.fetch;i!==void 0&&i>0?this.fetch=(d,l)=>{let f=new AbortController,g=setTimeout(()=>f.abort(),i),y=l?.signal;if(y){if(y.aborted)return clearTimeout(g),u(d,l);let ne=a(()=>{clearTimeout(g),f.abort()},"abortHandler");return y.addEventListener("abort",ne,{once:!0}),u(d,{...l,signal:f.signal}).finally(()=>{clearTimeout(g),y.removeEventListener("abort",ne)})}return u(d,{...l,signal:f.signal}).finally(()=>clearTimeout(g))}:this.fetch=u,this.retry=c}from(e){if(!e||typeof e!="string"||e.trim()==="")throw new Error("Invalid relation name: relation must be a non-empty string.");let t=new URL(`${this.url}/${e}`);return new G(t,{headers:new Headers(this.headers),schema:this.schemaName,fetch:this.fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}schema(e){return new r(this.url,{headers:this.headers,schema:e,fetch:this.fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}rpc(e,t={},{head:s=!1,get:n=!1,count:i}={}){let o,c=new URL(`${this.url}/rpc/${e}`),u,d=a(g=>g!==null&&typeof g=="object"&&(!Array.isArray(g)||g.some(d)),"_isObject"),l=s&&Object.values(t).some(d);l?(o="POST",u=t):s||n?(o=s?"HEAD":"GET",Object.entries(t).filter(([g,y])=>y!==void 0).map(([g,y])=>[g,Array.isArray(y)?`{${y.join(",")}}`:`${y}`]).forEach(([g,y])=>{c.searchParams.append(g,y)})):(o="POST",u=t);let f=new Headers(this.headers);return l?f.set("Prefer",i?`count=${i},return=minimal`:"return=minimal"):i&&f.set("Prefer",`count=${i}`),new A({method:o,url:c,headers:f,schema:this.schemaName,body:u,fetch:this.fetch??fetch,urlLengthLimit:this.urlLengthLimit,retry:this.retry})}};var J=class{static{a(this,"WorkBuddyDatabaseModule")}client;constructor(e,t){this.client=new N(`${e.endpoint}${R.database}`,{fetch:t}),this.from=this.client.from.bind(this.client),this.rpc=this.client.rpc.bind(this.client)}from;rpc;get url(){return this.client.url}};function et(r,e){return new J(r,e)}a(et,"createDatabaseModule");var x=class extends Error{static{a(this,"CloudOpenAIError")}error;status;requestId;retryAfterMs;constructor(e,t={}){let s=typeof e=="string"?{message:e,type:"server_error",param:null,code:null}:e;super(s.message),this.name="CloudOpenAIError",this.error=s,this.status=t.status,this.requestId=t.requestId,this.retryAfterMs=t.retryAfterMs,t.cause!==void 0&&("cause"in this||Object.defineProperty(this,"cause",{value:t.cause,writable:!1,enumerable:!1,configurable:!1}))}};function tt(r){if(!r)return;let e=r.trim(),t=Number(e);if(!isNaN(t)&&t>=0&&Number.isInteger(t))return t*1e3;let s=Date.parse(e);if(!isNaN(s)){let n=s-Date.now();return n>0?n:0}}a(tt,"parseRetryAfter");function m(...r){return r.find(e=>typeof e=="string"&&e.length>0)}a(m,"stringField");function k(...r){return r.find(e=>typeof e=="number"&&Number.isFinite(e))}a(k,"numberField");function E(...r){return r.find(e=>typeof e=="boolean")}a(E,"booleanField");function rt(...r){for(let e of r){if(typeof e=="number"&&Number.isFinite(e))return e;if(e!==null&&typeof e=="object"&&!Array.isArray(e))return Jt(e)}}a(rt,"contextWindowField");function Jt(r){let e={};for(let[t,s]of Object.entries(r)){if(t==="supportedLengths"){Array.isArray(s)&&(e.supportedLengths=s.filter(n=>typeof n=="number"&&Number.isFinite(n)));continue}if(t==="defaultLength"){typeof s=="number"&&Number.isFinite(s)&&(e.defaultLength=s);continue}Object.defineProperty(e,t,{value:s,writable:!0,enumerable:!0,configurable:!0})}return e}a(Jt,"normalizeContextWindowObject");function st(r){if(!r||typeof r!="object")return;let e=r,t=Array.isArray(e.input)?e.input.filter(n=>typeof n=="string"):void 0,s=Array.isArray(e.output)?e.output.filter(n=>typeof n=="string"):void 0;return t?.length||s?.length?{...t?.length?{input:t}:{},...s?.length?{output:s}:{}}:void 0}a(st,"modalitiesField");function nt(r){if(!r||typeof r!="object")return;let t=Object.entries(r).filter(([,s])=>typeof s=="boolean");return t.length?Object.fromEntries(t):void 0}a(nt,"capabilitiesField");function it(r){if(!r||typeof r!="object")return;let e=r,t={...m(e.currency)?{currency:e.currency}:{},...k(e.inputPerMillionTokens)!==void 0?{inputPerMillionTokens:e.inputPerMillionTokens}:{},...k(e.outputPerMillionTokens)!==void 0?{outputPerMillionTokens:e.outputPerMillionTokens}:{},...m(e.displayText)?{displayText:e.displayText}:{}};return Object.keys(t).length?t:void 0}a(it,"pricingField");function ot(r){if(!r||typeof r!="object")return;let e=r,t={},s=m(e.effort);s!==void 0&&(t.effort=s);let n=m(e.defaultEffort);n!==void 0&&(t.defaultEffort=n),Array.isArray(e.supportedEfforts)&&(t.supportedEfforts=e.supportedEfforts.filter(c=>typeof c=="string"));let i=m(e.summary);i!==void 0&&(i==="auto"||i==="concise"||i==="detailed")&&(t.summary=i);let o=E(e.canDisableThinking);return o!==void 0&&(t.canDisableThinking=o),Object.keys(t).length>0?t:void 0}a(ot,"reasoningField");function Yt(r){let e=m(r.id,r.ID);if(!e)return null;let t=E(r.enabled,r.Enabled),s=E(r.disabled,r.Disabled),n,i;return t!==void 0?(n=t,s!==void 0&&(i=s)):s!==void 0?(i=s,n=!s):n=!0,{id:e,name:m(r.name,r.Name)??e,...m(r.provider,r.Provider)?{provider:m(r.provider,r.Provider)}:{},...m(r.vendor,r.Vendor)?{vendor:m(r.vendor,r.Vendor)}:{},...m(r.family,r.Family)?{family:m(r.family,r.Family)}:{},...m(r.version,r.Version)?{version:m(r.version,r.Version)}:{},...m(r.description,r.Description)?{description:m(r.description,r.Description)}:{},...m(r.descriptionZh,r.DescriptionZh)?{descriptionZh:m(r.descriptionZh,r.DescriptionZh)}:{},...m(r.descriptionEn,r.DescriptionEn)?{descriptionEn:m(r.descriptionEn,r.DescriptionEn)}:{},...m(r.iconUrl,r.IconURL)?{iconUrl:m(r.iconUrl,r.IconURL)}:{},...rt(r.contextWindow,r.ContextWindow)!==void 0?{contextWindow:rt(r.contextWindow,r.ContextWindow)}:{},...k(r.maxInputTokens,r.MaxInputTokens)!==void 0?{maxInputTokens:k(r.maxInputTokens,r.MaxInputTokens)}:{},...k(r.maxOutputTokens,r.MaxOutputTokens)!==void 0?{maxOutputTokens:k(r.maxOutputTokens,r.MaxOutputTokens)}:{},...st(r.modalities??r.Modalities)?{modalities:st(r.modalities??r.Modalities)}:{},...nt(r.capabilities??r.Capabilities)?{capabilities:nt(r.capabilities??r.Capabilities)}:{},enabled:n,...i!==void 0?{disabled:i}:{},...E(r.isDefault,r.IsDefault)!==void 0?{isDefault:E(r.isDefault,r.IsDefault)}:{},...k(r.sortOrder,r.SortOrder)!==void 0?{sortOrder:k(r.sortOrder,r.SortOrder)}:{},...it(r.pricing??r.Pricing)?{pricing:it(r.pricing??r.Pricing)}:{},...m(r.credits,r.Credits)?{credits:m(r.credits,r.Credits)}:{},...k(r.maxAllowedSize,r.MaxAllowedSize)!==void 0?{maxAllowedSize:k(r.maxAllowedSize,r.MaxAllowedSize)}:{},...E(r.disabledMultimodal,r.DisabledMultimodal)!==void 0?{disabledMultimodal:E(r.disabledMultimodal,r.DisabledMultimodal)}:{},...E(r.supportsImages,r.SupportsImages)!==void 0?{supportsImages:E(r.supportsImages,r.SupportsImages)}:{},...E(r.supportsToolCall,r.SupportsToolCall)!==void 0?{supportsToolCall:E(r.supportsToolCall,r.SupportsToolCall)}:{},...E(r.supportsReasoning,r.SupportsReasoning)!==void 0?{supportsReasoning:E(r.supportsReasoning,r.SupportsReasoning)}:{},...E(r.onlyReasoning,r.OnlyReasoning)!==void 0?{onlyReasoning:E(r.onlyReasoning,r.OnlyReasoning)}:{},...ot(r.reasoning??r.Reasoning)?{reasoning:ot(r.reasoning??r.Reasoning)}:{},...k(r.temperature,r.Temperature)!==void 0?{temperature:k(r.temperature,r.Temperature)}:{},...k(r.top_k,r.Top_K)!==void 0?{top_k:k(r.top_k,r.Top_K)}:{},...k(r.top_p,r.Top_P)!==void 0?{top_p:k(r.top_p,r.Top_P)}:{},...k(r.repetition_penalty,r.Repetition_Penalty)!==void 0?{repetition_penalty:k(r.repetition_penalty,r.Repetition_Penalty)}:{}}}a(Yt,"normalizeModel");function Te(r){return r.name||r.id}a(Te,"getModelDisplayName");function Oe(r,e){return r.capabilities?.[e]}a(Oe,"getModelCapability");var he=class{static{a(this,"ModelsAPI")}baseUrl;fetch;constructor(e,t){this.baseUrl=e,this.fetch=t}async list(e){let t;try{t=await this.fetch(`${this.baseUrl}/models`,{method:"GET",headers:{Accept:"application/json"},signal:e})}catch(c){throw c instanceof Error&&c.name==="AbortError"?c:new x({message:`Network error: ${c?.message??"unknown"}`,type:"server_error",param:null,code:"gateway_network_error"},{cause:c})}if(!t.ok)throw await Ae(t);let s=await t.text(),n;try{n=JSON.parse(s)}catch{throw new x({message:"Failed to parse models response: invalid JSON",type:"server_error",param:null,code:"gateway_invalid_response"})}let i=Array.isArray(n)?n:Array.isArray(n?.data)?n.data:[],o=[];for(let c of i){let u=Yt(c);u&&o.push(u)}return o}};async function Ae(r){let e=await r.text().catch(()=>""),t;try{let i=JSON.parse(e);if(i&&typeof i=="object"&&i.error){let o=i.error;t={message:typeof o.message=="string"?o.message:`HTTP ${r.status}`,type:typeof o.type=="string"?o.type:"server_error",param:o.param===void 0?null:o.param,code:o.code===void 0?null:o.code}}else t={message:typeof i=="string"?i:`HTTP ${r.status}`,type:"server_error",param:null,code:null}}catch{t={message:e||`HTTP ${r.status}`,type:"server_error",param:null,code:null}}let s=r.headers.get("x-request-id")??void 0,n=tt(r.headers.get("retry-after"));return new x(t,{status:r.status,requestId:s,retryAfterMs:n})}a(Ae,"httpError");var fe=class{static{a(this,"Utf8Decoder")}codePoint=0;bytesNeeded=0;bytesSeen=0;lowerBoundary=128;upperBoundary=191;bomSeen=!1;streaming=!1;resetSequence(){this.codePoint=0,this.bytesNeeded=0,this.bytesSeen=0,this.lowerBoundary=128,this.upperBoundary=191}decode(e=new Uint8Array,t={}){this.streaming||(this.resetSequence(),this.bomSeen=!1),this.streaming=t.stream===!0;let s="",n=a(i=>{!this.bomSeen&&(this.bomSeen=!0,i===65279)||(s+=String.fromCodePoint(i))},"emit");for(let i=0;i<e.length;i++){let o=e[i];if(this.bytesNeeded===0){o<=127?n(o):o>=194&&o<=223?(this.bytesNeeded=1,this.codePoint=o&31):o>=224&&o<=239?(this.bytesNeeded=2,this.codePoint=o&15,o===224&&(this.lowerBoundary=160),o===237&&(this.upperBoundary=159)):o>=240&&o<=244?(this.bytesNeeded=3,this.codePoint=o&7,o===240&&(this.lowerBoundary=144),o===244&&(this.upperBoundary=143)):n(65533);continue}if(o<this.lowerBoundary||o>this.upperBoundary){this.resetSequence(),n(65533),i--;continue}this.lowerBoundary=128,this.upperBoundary=191,this.codePoint=this.codePoint<<6|o&63,this.bytesSeen++,this.bytesSeen===this.bytesNeeded&&(n(this.codePoint),this.resetSequence())}return!this.streaming&&this.bytesNeeded>0&&(n(65533),this.resetSequence()),s}};var Xt=class{static{a(this,"SSEDecoder")}event=null;dataParts=[];decode(e){let t=e;if(t.endsWith("\r")&&(t=t.slice(0,-1)),t===""){if(this.event===null&&this.dataParts.length===0)return null;let o={event:this.event,data:this.dataParts.join(`
    `)};return this.event=null,this.dataParts=[],o}if(t.startsWith(":"))return null;let s=t.indexOf(":"),n,i;if(s===-1)n=t,i="";else{n=t.slice(0,s);let o=t.slice(s+1);o.startsWith(" ")&&(o=o.slice(1)),i=o}return n==="event"?this.event=i:n==="data"&&this.dataParts.push(i),null}flush(){if(this.event===null&&this.dataParts.length===0)return null;let e={event:this.event,data:this.dataParts.join(`
    `)};return this.event=null,this.dataParts=[],e}},Qt=class{static{a(this,"LineDecoder")}buffer=new Uint8Array;decoder;constructor(){this.decoder=typeof TextDecoder>"u"?new fe:new TextDecoder("utf-8")}decode(e){let t=new Uint8Array(this.buffer.length+e.length);t.set(this.buffer),t.set(e,this.buffer.length),this.buffer=t;let s=[],n=0;for(let i=0;i<this.buffer.length;i++)if(this.buffer[i]===10||this.buffer[i]===13){let o=this.buffer.subarray(n,i),c=this.decoder.decode(o,{stream:!0});s.push(c),this.buffer[i]===13&&i+1<this.buffer.length&&this.buffer[i+1]===10&&i++,n=i+1}return n>0&&(this.buffer=this.buffer.slice(n)),s}flush(){if(this.buffer.length===0){let t=this.decoder.decode();return t?[t]:[]}let e=this.decoder.decode(this.buffer,{stream:!1});return this.buffer=new Uint8Array,e?[e]:[]}},at="[DONE]";async function*ct(r,e){let t=new Xt,s=new Qt,n=r.getReader(),i=!1,o=a(()=>{i=!0,n.cancel().catch(()=>{})},"onAbort");if(e){if(e.aborted)return;e.addEventListener("abort",o,{once:!0})}try{for(;;){if(i)return;let u;try{u=await n.read()}catch(f){if(i||f instanceof Error&&f.name==="AbortError")return;throw f}let{done:d,value:l}=u;if(d)break;for(let f of s.decode(l)){let g=t.decode(f);g&&(yield g)}}for(let u of s.flush()){let d=t.decode(u);d&&(yield d)}let c=t.flush();c&&(yield c)}finally{e&&e.removeEventListener("abort",o);try{n.releaseLock()}catch{}}}a(ct,"iterSSEEvents");function Zt(r,e){let t=e?{requestId:e}:{};try{let s=JSON.parse(r);if(s&&typeof s=="object"){let n=s.error??s;if(n&&typeof n=="object")return new x({message:typeof n.message=="string"?n.message:"Stream error",type:typeof n.type=="string"?n.type:"server_error",param:n.param===void 0?null:n.param,code:n.code===void 0?null:n.code},t)}}catch{}return new x({message:r||"Stream error",type:"server_error",param:null,code:null},t)}a(Zt,"extractSSEError");var pe=class{static{a(this,"ChatCompletionsAPI")}baseUrl;fetch;constructor(e,t){this.baseUrl=e,this.fetch=t}create(e){if(e.stream!==!0)throw new x({message:"stream must be true; non-streaming chat completions are not supported",type:"invalid_request_error",param:"stream",code:"request_stream_required"});return this.createStreaming(e)}async*createStreaming(e){let{signal:t,conversationId:s,...n}=e;n.stream=!0;let i;try{i=await this.fetch(`${this.baseUrl}/chat/completions`,{method:"POST",headers:{Accept:"text/event-stream","Content-Type":"application/json",...s!==void 0?{"X-Conversation-ID":s}:{}},body:JSON.stringify(n),signal:t})}catch(d){if(d instanceof Error&&d.name==="AbortError")return;throw new x({message:`Network error: ${d?.message??"unknown"}`,type:"server_error",param:null,code:"gateway_network_error"},{cause:d})}if(!i.ok)throw await Ae(i);if(!i.body)throw new x({message:"Response body is empty \u2014 streaming not supported",type:"server_error",param:null,code:"gateway_invalid_response"},{requestId:i.headers.get("x-request-id")??void 0});let o=i.headers.get("x-request-id")??void 0,c=!1,u=!1;try{for await(let d of ct(i.body,t)){if(d.event==="error")throw u=!0,Zt(d.data,o);if(d.event===null||d.event===""){if(d.data===at){c=!0;return}if(!d.data)continue;let l;try{l=JSON.parse(d.data)}catch{throw u=!0,new x({message:`Failed to parse SSE data: ${d.data}`,type:"server_error",param:null,code:"gateway_invalid_response"},{requestId:o})}if(l&&typeof l=="object"&&"error"in l){u=!0;let f=l.error;throw new x({message:typeof f?.message=="string"?f.message:"Stream error",type:typeof f?.type=="string"?f.type:"server_error",param:f?.param===void 0?null:f.param,code:f?.code===void 0?null:f.code},{requestId:o})}yield l}}}catch(d){if(d instanceof Error&&d.name==="AbortError")return;throw u=!0,d}if(!c&&!u&&!t?.aborted)throw new x({message:"\u6D41\u5F0F\u54CD\u5E94\u4E2D\u65AD\u3002",type:"server_error",param:null,code:"gateway_stream_interrupted"},{requestId:o})}};var M=class{static{a(this,"LlmModule")}fetch;baseUrl;models;chat;constructor(e,t){this.fetch=t,this.baseUrl=`${e.endpoint}${R.llm}`,this.models=new he(this.baseUrl,this.fetch),this.chat={completions:new pe(this.baseUrl,this.fetch)}}};var F=class extends Error{static{a(this,"StorageError")}__isStorageError=!0;namespace;status;statusCode;constructor(e,t="storage",s,n){super(e),this.namespace=t,this.name=t==="vectors"?"StorageVectorsError":"StorageError",this.status=s,this.statusCode=n}toJSON(){return{name:this.name,message:this.message,status:this.status,statusCode:this.statusCode}}};function U(r){return typeof r=="object"&&r!==null&&"__isStorageError"in r}a(U,"isStorageError");var C=class extends F{static{a(this,"StorageApiError")}status;statusCode;code;constructor(e,t,s,n="storage",i){super(e,n,t,s),this.name=n==="vectors"?"StorageVectorsApiError":"StorageApiError",this.status=t,this.statusCode=s,this.code=i}toJSON(){return{...super.toJSON(),code:this.code}}},q=class extends F{static{a(this,"StorageUnknownError")}originalError;constructor(e,t,s="storage"){super(e,s),this.name=s==="vectors"?"StorageVectorsUnknownError":"StorageUnknownError",this.originalError=t}};function L(r,e,t){let s={...r},n=e.toLowerCase();for(let i of Object.keys(s))i.toLowerCase()===n&&delete s[i];return s[n]=t,s}a(L,"setHeader");function ut(r){let e={};for(let[t,s]of Object.entries(r))e[t.toLowerCase()]=s;return e}a(ut,"normalizeHeaders");var dt=a(r=>r?(...e)=>r(...e):(...e)=>fetch(...e),"resolveFetch");var lt=a(r=>{if(typeof r!="object"||r===null)return!1;let e=Object.getPrototypeOf(r);return(e===null||e===Object.prototype||Object.getPrototypeOf(e)===null)&&!(Symbol.toStringTag in r)&&!(Symbol.iterator in r)},"isPlainObject"),me=a(r=>{if(Array.isArray(r))return r.map(t=>me(t));if(typeof r=="function"||r!==Object(r))return r;let e={};return Object.entries(r).forEach(([t,s])=>{let n=t.replace(/([-_][a-z])/gi,i=>i.toUpperCase().replace(/[-_]/g,""));e[n]=me(s)}),e},"recursiveToCamel");var ht=a(r=>r.split("/").map(encodeURIComponent).join("/"),"encodeStoragePath");var ft=a(r=>{if(typeof r=="object"&&r!==null){let e=r;if(typeof e.msg=="string")return e.msg;if(typeof e.message=="string")return e.message;if(typeof e.error_description=="string")return e.error_description;if(typeof e.error=="string")return e.error;if(typeof e.error=="object"&&e.error!==null){let t=e.error;if(typeof t.message=="string")return t.message}}return JSON.stringify(r)},"_getErrorMessage"),er=a(async(r,e,t,s)=>{if(r!==null&&typeof r=="object"&&"json"in r&&typeof r.json=="function"){let i=r,o=parseInt(String(i.status),10);Number.isFinite(o)||(o=500),i.json().then(c=>{let u=c?.statusCode||c?.code||o+"";e(new C(ft(c),o,u,s,c?.code))}).catch(()=>{let c=o+"",u=i.statusText||`HTTP ${o} error`;e(new C(u,o,c,s))})}else e(new q(ft(r),r,s))},"handleError"),tr=a((r,e,t,s)=>{let n={method:r,headers:e?.headers||{}};if(r==="GET"||r==="HEAD"||!s)return{...n,...t};if(lt(s)){let i=e?.headers||{},o;for(let[c,u]of Object.entries(i))c.toLowerCase()==="content-type"&&(o=u);n.headers=L(i,"Content-Type",o??"application/json"),n.body=JSON.stringify(s)}else n.body=s;return e?.duplex&&(n.duplex=e.duplex),{...n,...t}},"_getRequestParams");async function Y(r,e,t,s,n,i,o){return new Promise((c,u)=>{r(t,tr(e,s,n,i)).then(d=>{if(!d.ok)throw d;if(s?.noResolveJson)return d;if(o==="vectors"){let l=d.headers.get("content-type");if(d.headers.get("content-length")==="0"||d.status===204)return{};if(!l||!l.includes("application/json"))return{}}return d.json()}).then(d=>c(d)).catch(d=>er(d,u,s,o))})}a(Y,"_handleRequest");function pt(r="storage"){return{get:a(async(e,t,s,n)=>Y(e,"GET",t,s,n,void 0,r),"get"),post:a(async(e,t,s,n,i)=>Y(e,"POST",t,n,i,s,r),"post"),put:a(async(e,t,s,n,i)=>Y(e,"PUT",t,n,i,s,r),"put"),head:a(async(e,t,s,n)=>Y(e,"HEAD",t,{...s,noResolveJson:!0},n,void 0,r),"head"),remove:a(async(e,t,s,n,i)=>Y(e,"DELETE",t,n,i,s,r),"remove")}}a(pt,"createFetchApi");var rr=pt("storage"),{get:Re,post:$,put:$e,head:mt,remove:Ue}=rr,Ms=pt("vectors");var X=class{static{a(this,"BaseApiClient")}url;headers;fetch;shouldThrowOnError=!1;namespace;constructor(e,t={},s,n="storage"){this.url=e,this.headers=ut(t),this.fetch=dt(s),this.namespace=n}throwOnError(){return this.shouldThrowOnError=!0,this}setHeader(e,t){return this.headers=L(this.headers,e,t),this}async handleOperation(e){try{return{data:await e(),error:null}}catch(t){if(this.shouldThrowOnError)throw t;if(U(t))return{data:null,error:t};throw t}}};var Q=class{static{a(this,"StreamDownloadBuilder")}downloadFn;shouldThrowOnError;[Symbol.toStringTag]="StreamDownloadBuilder";promise=null;constructor(e,t){this.downloadFn=e,this.shouldThrowOnError=t}then(e,t){return this.getPromise().then(e,t)}catch(e){return this.getPromise().catch(e)}finally(e){return this.getPromise().finally(e)}getPromise(){return this.promise||(this.promise=this.execute()),this.promise}async execute(){try{return{data:(await this.downloadFn()).body,error:null}}catch(e){if(this.shouldThrowOnError)throw e;if(U(e))return{data:null,error:e};throw e}}};var Z=class{static{a(this,"BlobDownloadBuilder")}downloadFn;shouldThrowOnError;[Symbol.toStringTag]="BlobDownloadBuilder";promise=null;constructor(e,t){this.downloadFn=e,this.shouldThrowOnError=t}asStream(){return new Q(this.downloadFn,this.shouldThrowOnError)}then(e,t){return this.getPromise().then(e,t)}catch(e){return this.getPromise().catch(e)}finally(e){return this.getPromise().finally(e)}getPromise(){return this.promise||(this.promise=this.execute()),this.promise}async execute(){try{return{data:await(await this.downloadFn()).blob(),error:null}}catch(e){if(this.shouldThrowOnError)throw e;if(U(e))return{data:null,error:e};throw e}}};var Ie={limit:100,offset:0,sortBy:{column:"name",order:"asc"}},gt={cacheControl:"3600",contentType:"text/plain;charset=UTF-8",upsert:!1},ee=class extends X{static{a(this,"StorageFileApi")}bucketId;constructor(e,t={},s,n){super(e,t,n,"storage"),this.bucketId=s}async uploadOrUpdate(e,t,s,n){return this.handleOperation(async()=>{let i,o={...gt,...n},c={...this.headers,...e==="POST"&&{"x-upsert":String(o.upsert)}},u=o.metadata;if(typeof Blob<"u"&&s instanceof Blob?(i=new FormData,i.append("cacheControl",o.cacheControl),u&&i.append("metadata",this.encodeMetadata(u)),i.append("",s)):typeof FormData<"u"&&s instanceof FormData?(i=s,i.has("cacheControl")||i.append("cacheControl",o.cacheControl),u&&!i.has("metadata")&&i.append("metadata",this.encodeMetadata(u))):(i=s,c["cache-control"]=`max-age=${o.cacheControl}`,c["content-type"]=o.contentType,u&&(c["x-metadata"]=this.toBase64(this.encodeMetadata(u))),(typeof ReadableStream<"u"&&i instanceof ReadableStream||i&&typeof i=="object"&&"pipe"in i&&typeof i.pipe=="function")&&!o.duplex&&(o.duplex="half")),n?.headers)for(let[g,y]of Object.entries(n.headers))c=L(c,g,y);let d=this._removeEmptyFolders(t),l=this._getFinalPath(d),f=await(e=="PUT"?$e:$)(this.fetch,`${this.url}/object/${l}`,i,{headers:c,...o?.duplex?{duplex:o.duplex}:{}});return{path:d,id:f.Id,fullPath:f.Key}})}async upload(e,t,s){return this.uploadOrUpdate("POST",e,t,s)}async uploadToSignedUrl(e,t,s,n){let i=this._removeEmptyFolders(e),o=this._getFinalPath(i),c=new URL(this.url+`/object/upload/sign/${o}`);return c.searchParams.set("token",t),this.handleOperation(async()=>{let u,d={...gt,...n},l={...this.headers,"x-upsert":String(d.upsert)},f=d.metadata;if(typeof Blob<"u"&&s instanceof Blob?(u=new FormData,u.append("cacheControl",d.cacheControl),f&&u.append("metadata",this.encodeMetadata(f)),u.append("",s)):typeof FormData<"u"&&s instanceof FormData?(u=s,u.has("cacheControl")||u.append("cacheControl",d.cacheControl),f&&!u.has("metadata")&&u.append("metadata",this.encodeMetadata(f))):(u=s,l["cache-control"]=`max-age=${d.cacheControl}`,l["content-type"]=d.contentType,f&&(l["x-metadata"]=this.toBase64(this.encodeMetadata(f))),(typeof ReadableStream<"u"&&u instanceof ReadableStream||u&&typeof u=="object"&&"pipe"in u&&typeof u.pipe=="function")&&!d.duplex&&(d.duplex="half")),n?.headers)for(let[y,ne]of Object.entries(n.headers))l=L(l,y,ne);let g=await $e(this.fetch,c.toString(),u,{headers:l,...d?.duplex?{duplex:d.duplex}:{}});return{path:i,fullPath:g.Key}})}async createSignedUploadUrl(e,t){return this.handleOperation(async()=>{let s=this._getFinalPath(e),n={...this.headers};t?.upsert&&(n["x-upsert"]="true");let i=await $(this.fetch,`${this.url}/object/upload/sign/${s}`,{},{headers:n}),o=new URL(this.url+i.url),c=o.searchParams.get("token");if(!c)throw new F("No token returned by API");return{signedUrl:o.toString(),path:e,token:c}})}async update(e,t,s){return this.uploadOrUpdate("PUT",e,t,s)}async move(e,t,s){return this.handleOperation(async()=>await $(this.fetch,`${this.url}/object/move`,{bucketId:this.bucketId,sourceKey:e,destinationKey:t,destinationBucket:s?.destinationBucket},{headers:this.headers}))}async copy(e,t,s){return this.handleOperation(async()=>({path:(await $(this.fetch,`${this.url}/object/copy`,{bucketId:this.bucketId,sourceKey:e,destinationKey:t,destinationBucket:s?.destinationBucket},{headers:this.headers})).Key}))}async createSignedUrl(e,t,s){return this.handleOperation(async()=>{let n=this._getFinalPath(e),i=typeof s?.transform=="object"&&s.transform!==null&&Object.keys(s.transform).length>0,o=await $(this.fetch,`${this.url}/object/sign/${n}`,{expiresIn:t,...i?{transform:s.transform}:{}},{headers:this.headers}),c=new URLSearchParams;s?.download&&c.set("download",s.download===!0?"":s.download),s?.cacheNonce!=null&&c.set("cacheNonce",String(s.cacheNonce));let u=c.toString();return{signedUrl:encodeURI(`${this.url}${o.signedURL}${u?`&${u}`:""}`)}})}async createSignedUrls(e,t,s){return this.handleOperation(async()=>{let n=await $(this.fetch,`${this.url}/object/sign/${this.bucketId}`,{expiresIn:t,paths:e},{headers:this.headers}),i=new URLSearchParams;s?.download&&i.set("download",s.download===!0?"":s.download),s?.cacheNonce!=null&&i.set("cacheNonce",String(s.cacheNonce));let o=i.toString();return n.map(c=>({...c,signedUrl:c.signedURL?encodeURI(`${this.url}${c.signedURL}${o?`&${o}`:""}`):null}))})}download(e,t,s){let i=typeof t?.transform=="object"&&t.transform!==null&&Object.keys(t.transform).length>0?"render/image/authenticated":"object",o=new URLSearchParams;t?.transform&&this.applyTransformOptsToQuery(o,t.transform),t?.cacheNonce!=null&&o.set("cacheNonce",String(t.cacheNonce));let c=o.toString(),u=this._getFinalPath(e),d=a(()=>Re(this.fetch,`${this.url}/${i}/${u}${c?`?${c}`:""}`,{headers:this.headers,noResolveJson:!0},s),"downloadFn");return new Z(d,this.shouldThrowOnError)}async info(e){let t=this._getFinalPath(e);return this.handleOperation(async()=>{let s=await Re(this.fetch,`${this.url}/object/info/${t}`,{headers:this.headers});return me(s)})}async exists(e){let t=this._getFinalPath(e);try{return await mt(this.fetch,`${this.url}/object/${t}`,{headers:this.headers}),{data:!0,error:null}}catch(s){if(this.shouldThrowOnError)throw s;if(U(s)){let n=s instanceof C?s.status:s instanceof q?s.originalError?.status:void 0;if(n!==void 0&&[400,404].includes(n))return{data:!1,error:s}}throw s}}getPublicUrl(e,t){let s=this._getFinalPath(e),n=new URLSearchParams;t?.download&&n.set("download",t.download===!0?"":t.download),t?.transform&&this.applyTransformOptsToQuery(n,t.transform),t?.cacheNonce!=null&&n.set("cacheNonce",String(t.cacheNonce));let i=n.toString(),c=typeof t?.transform=="object"&&t.transform!==null&&Object.keys(t.transform).length>0?"render/image":"object";return{data:{publicUrl:encodeURI(`${this.url}/${c}/public/${s}`)+(i?`?${i}`:"")}}}async remove(e){return this.handleOperation(async()=>await Ue(this.fetch,`${this.url}/object/${this.bucketId}`,{prefixes:e},{headers:this.headers}))}async purgeCache(e,t,s){return this.handleOperation(async()=>{let n=ht(this._getFinalPath(e)),i=new URLSearchParams;t?.transformations&&i.set("transformations","true");let o=i.toString();return await Ue(this.fetch,`${this.url}/cdn/${n}${o?`?${o}`:""}`,{},{headers:this.headers},s)})}async list(e,t,s){return this.handleOperation(async()=>{let n=t?.sortBy?{...Ie.sortBy,...t.sortBy}:Ie.sortBy,i={...Ie,...t,sortBy:n,prefix:e||""};return await $(this.fetch,`${this.url}/object/list/${this.bucketId}`,i,{headers:this.headers},s)})}async listV2(e,t){return this.handleOperation(async()=>{let s={...e};return await $(this.fetch,`${this.url}/object/list-v2/${this.bucketId}`,s,{headers:this.headers},t)})}encodeMetadata(e){return JSON.stringify(e)}toBase64(e){return typeof Buffer<"u"?Buffer.from(e).toString("base64"):btoa(e)}_getFinalPath(e){return`${this.bucketId}/${e.replace(/^\/+/,"")}`}_removeEmptyFolders(e){return e.replace(/^\/|\/$/g,"").replace(/\/+/g,"/")}applyTransformOptsToQuery(e,t){return t.width&&e.set("width",t.width.toString()),t.height&&e.set("height",t.height.toString()),t.resize&&e.set("resize",t.resize),t.format&&e.set("format",t.format),t.quality&&e.set("quality",t.quality.toString()),e}};var yt="2.112.3";var bt={"X-Client-Info":`storage-js/${yt}`};var W="runtime",ge=600,ye=3600,w=class extends Error{static{a(this,"CloudStoragePathError")}constructor(e){super(e),this.name="CloudStoragePathError"}},te=class{static{a(this,"WorkBuddyStorageDownload")}blob;stream;[Symbol.toStringTag]="WorkBuddyStorageDownload";constructor(e,t){this.blob=e,this.stream=t}asStream(){return this.stream()}then(e,t){return this.blob().then(e,t)}catch(e){return this.blob().catch(e)}finally(e){return this.blob().finally(e)}},H=class{static{a(this,"WorkBuddyStorageBucket")}fileApi;constructor(e){this.fileApi=e}upload(e,t,s){return _(this.fileApi.upload(v(e),t,s))}update(e,t,s){return _(this.fileApi.update(v(e),t,s))}list(e="",t){return _(this.fileApi.list(St(e),t))}listPage(e){return _(this.fileApi.listV2({...e,prefix:St(e?.prefix??"")}))}info(e){return _(this.fileApi.info(v(e)))}async exists(e){let t=await this.fileApi.exists(v(e));return t.error?{data:null,error:Et(t.error)}:{data:t.data,error:null}}download(e){let t=this.fileApi.download(v(e));return new te(()=>_(t),()=>_(t.asStream()))}remove(e){if(e.length===0)throw new w("remove requires at least one object path.");return _(this.fileApi.remove(e.map(v)))}copy(e,t){return _(this.fileApi.copy(v(e),v(t)))}move(e,t){return _(this.fileApi.move(v(e),v(t)))}createSignedUrl(e,t=ge){return _(this.fileApi.createSignedUrl(v(e),kt(t)))}createSignedUrls(e,t=ge){if(e.length===0)throw new w("createSignedUrls requires at least one object path.");return _(this.fileApi.createSignedUrls(e.map(v),kt(t)))}createSignedUploadUrl(e,t){return _(this.fileApi.createSignedUploadUrl(v(e),{upsert:t?.upsert??!1}))}uploadToSignedUrl(e,t,s,n){if(!t)throw new w("signed upload token is required.");return _(this.fileApi.uploadToSignedUrl(v(e),t,s,n))}},re=class extends H{static{a(this,"WorkBuddyStorageModule")}runtime;constructor(e){let s=e.from(W);super(s),this.runtime=new H(s)}from(e=W){if(e!==W)throw new w(`Only the "${W}" storage bucket is available.`);return this.runtime}userPath(e,t){return wt("users",e,t)}sharedPath(e,t){return wt("shared",e,t)}};function xt(r,e){let t={from:a(s=>new ee(`${r.endpoint}${R.storage}`,bt,s,e),"from")};return new re(t)}a(xt,"createStorageModule");function wt(r,e,t){let s=sr(e,"owner/user id"),n=Ce(t,!1);return v(`${r}/${s}/${n}`)}a(wt,"scopedPath");function v(r){let e=Ce(r,!1);if(!e.includes("/"))throw new w("Object paths must use users/<uid>/... or shared/<ownerUid>/....");let[t,s,...n]=e.split("/");if(t!=="users"&&t!=="shared"||!s||n.length===0)throw new w("Object paths must use users/<uid>/... or shared/<ownerUid>/....");return e}a(v,"validateObjectPath");function St(r){if(r==="")return"";let e=Ce(r,!0),[t,s]=e.split("/");if(t==="shared"&&!s)return"shared";if(t!=="users"&&t!=="shared"||!s)throw new w("List prefixes must start with users/<uid> or shared/<ownerUid>.");return e}a(St,"validateObjectPrefix");function Ce(r,e){if(typeof r!="string"||r.trim()==="")throw new w("Storage path must be a non-empty relative path.");let t=r.trim();for(let i=0;i<3;i+=1)try{let o=decodeURIComponent(t);if(o===t)break;t=o}catch{throw new w("Storage path contains invalid URL encoding.")}if(t.startsWith("/")||t.includes("\\")||t.includes("\0")||t.includes("//")||!e&&t.endsWith("/"))throw new w("Storage path is not a safe relative object path.");let s=e?t.replace(/\/+$/,""):t;if(s.split("/").some(i=>i===""||i==="."||i===".."))throw new w("Storage path traversal is not allowed.");return s}a(Ce,"validatePath");function sr(r,e){if(!r)throw new w(`${e} is not a valid storage path segment.`);let t=r;for(let s=0;s<3;s+=1)try{let n=decodeURIComponent(t);if(n===t)break;t=n}catch{throw new w(`${e} contains invalid URL encoding.`)}if(t.includes("/")||t.includes("\\")||t.includes("\0")||t==="."||t==="..")throw new w(`${e} is not a valid storage path segment.`);return t}a(sr,"validatePathSegment");function kt(r){if(!Number.isInteger(r)||r<=0||r>ye)throw new w(`Signed URL expiry must be an integer between 1 and ${ye} seconds.`);return r}a(kt,"validateSignedURLTTL");async function _(r){let e=await r;return e.error?{data:null,error:Et(e.error)}:e.data===null?{data:null,error:{name:"CloudStorageResponseError",message:"Storage API returned neither data nor an error."}}:{data:e.data,error:null}}a(_,"mapStorageResult");function Et(r){if(r instanceof Error){let e=r;return{name:e.name,message:e.message,status:e.status,statusCode:e.statusCode,code:e.code,cause:r}}return{name:"CloudStorageError",message:String(r),cause:r}}a(Et,"normalizeStorageError");var se=class{static{a(this,"WorkBuddyCloudClient")}config;database;auth;storage;llm;constructor(e,t={}){this.config=e,this.auth=new D(e,we(e,oe),{storage:t.storage,workBuddyMiniProgram:t.workBuddyMiniProgram});let s=we(e,()=>this.auth.getAccessToken());this.database=et(e,s),this.storage=xt(e,s),this.llm=new M(e,s)}get endpoint(){return this.config.endpoint}get oauthRelayBaseUrl(){return this.config.oauthRelayBaseUrl}};function vt(r){return new se(je(r),{storage:r.storage})}a(vt,"createWorkBuddyCloud");function Pt(r){return r.kind==="unauthenticated"||r.code==="invalid_grant"}a(Pt,"shouldClearCredentials");return $t(nr);})();
    return WorkBuddyCloud;
  }
})(window);
