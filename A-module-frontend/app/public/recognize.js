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
    sdkPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = CONFIG.SDK_URL;
      s.onload = function () {
        if (global.WorkBuddyCloud) resolve(global.WorkBuddyCloud);
        else reject(new Error("云服务 SDK 加载后未挂载全局对象。"));
      };
      s.onerror = function () { reject(new Error("云服务 SDK 加载失败，请检查网络后重试。")); };
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
    "6. 只输出JSON，不要有多余解释"
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
})(window);
