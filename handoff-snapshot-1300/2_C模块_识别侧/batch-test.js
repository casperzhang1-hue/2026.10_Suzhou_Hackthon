/*
 * 监督小宠 · C 模块 跑批测试脚本（Node 环境）
 * ------------------------------------------------------------
 * 用途：批量跑学习截图，验证 recognize.js 输出的 JSON v1.1 是否合法。
 * 验收口径（对齐任务卡）：6 张里至少 5 张能出合法 JSON。
 *
 * 用法：
 *   node batch-test.js                    # 扫描默认目录（工作空间/testshots、桌面、下载）
 *   node batch-test.js "D:/我的截图"      # 指定一个目录
 *   node batch-test.js "a.png" "b.jpg"    # 指定若干张图
 *
 * 判定为「合法 JSON」需同时满足：
 *   1. schema_version === "1.1"
 *   2. v1.1 全部字段存在（不缺 key）
 *   3. warnings 是数组且每项含 code + message
 *   4. encouragement 只有 level 一个字段（v1.1 契约）
 *   5. 鼓励等级属于约定枚举（low/normal/good/excellent）或空串（非学习图片）
 *   6. accuracy 若在 [0,1] 区间外则判非法
 *
 * 非学习图片（level === ""）单独归类，不计入「识别成功」，但也不算报错。
 */

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const WORKDIR = __dirname;
const RECOGNIZE_PATH = path.join(WORKDIR, "recognize.js");

const DEFAULT_DIRS = [
  path.join(WORKDIR, "testshots"),
  path.join(process.env.USERPROFILE || "C:/Users/Lenovo", "Desktop"),
  path.join(process.env.USERPROFILE || "C:/Users/Lenovo", "Downloads"),
];

const IMAGE_EXT = [".png", ".jpg", ".jpeg", ".webp"];
const MIME = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };

/* ---------- 1. 收集待测图片 ---------- */

function collectImages(args) {
  const files = [];
  const explicit = args.filter((a) => IMAGE_EXT.includes(path.extname(a).toLowerCase()));

  if (explicit.length > 0) {
    explicit.forEach((p) => {
      if (fs.existsSync(p)) files.push(p);
      else console.log("  [跳过] 文件不存在: " + p);
    });
    return files;
  }

  const dirs = args.length > 0 ? args : DEFAULT_DIRS;
  dirs.forEach((dir) => {
    if (!fs.existsSync(dir)) return;
    let entries = [];
    try {
      entries = fs.readdirSync(dir);
    } catch (e) {
      return;
    }
    entries.forEach((name) => {
      const full = path.join(dir, name);
      if (IMAGE_EXT.includes(path.extname(name).toLowerCase())) files.push(full);
    });
  });
  return files;
}

/* ---------- 2. 在 Node 里装出浏览器环境 ---------- */

async function setupEnv() {
  const src = fs.readFileSync(RECOGNIZE_PATH, "utf8");
  const SDK_URL = (src.match(/SDK_URL:\s*"([^"]+)"/) || [])[1];
  if (!SDK_URL) throw new Error("未能从 recognize.js 中读取 SDK_URL。");

  // 拉真实 SDK，在沙箱里执行（等价于浏览器 <script> 加载）
  const res = await fetch(SDK_URL);
  if (!res.ok) throw new Error("SDK 下载失败，HTTP " + res.status);
  const code = await res.text();

  const sandbox = {
    console, fetch, Headers, Request, Response, AbortController,
    setTimeout, clearTimeout, setInterval, clearInterval,
    URL, TextEncoder, TextDecoder, Buffer, process, btoa, atob, crypto,
  };
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  const ctx = vm.createContext(sandbox);
  vm.runInContext(code, ctx, { timeout: 30000 });
  if (!sandbox.WorkBuddyCloud) throw new Error("SDK 执行后未挂载 WorkBuddyCloud。");

  // FileReader polyfill：直接读本地文件转 data URL
  sandbox.FileReader = function () {
    const self = this;
    this.readAsDataURL = function (file) {
      setTimeout(function () {
        try {
          const buf = fs.readFileSync(file._path);
          self.result = "data:" + file.type + ";base64," + buf.toString("base64");
          self.onload && self.onload();
        } catch (e) {
          self.onerror && self.onerror(e);
        }
      }, 0);
    };
  };

  const win = {};
  win.WorkBuddyCloud = sandbox.WorkBuddyCloud;
  const doc = { head: { appendChild: function () {} }, createElement: function () { return {}; } };

  const W = new Function("window", "document", "FileReader", src + "; return window;")(
    win, doc, sandbox.FileReader
  );
  return { api: W, sdkUrl: SDK_URL };
}

/* ---------- 3. 单张图的合法性校验 ---------- */

const REQUIRED_FIELDS = [
  "schema_version", "user_id", "recognition",
  "source_app", "event_date", "event_time", "duration_minutes",
  "modules", "total_questions", "accuracy", "warnings", "encouragement",
];
const VALID_LEVELS = ["low", "normal", "good", "excellent", ""];

function validate(r) {
  const errs = [];
  if (!r || typeof r !== "object") return ["返回值不是对象"];

  if (r.schema_version !== "1.1") errs.push("schema_version=" + JSON.stringify(r.schema_version) + "（应为 1.1）");

  const missing = REQUIRED_FIELDS.filter((k) => !(k in r));
  if (missing.length) errs.push("缺字段: " + missing.join(", "));

  if (!Array.isArray(r.warnings)) errs.push("warnings 不是数组");
  else {
    r.warnings.forEach((w, i) => {
      if (!w || typeof w.code !== "string" || typeof w.message !== "string") {
        errs.push("warnings[" + i + "] 缺 code 或 message");
      }
    });
  }

  if (!r.encouragement || typeof r.encouragement !== "object") errs.push("encouragement 不是对象");
  else {
    const keys = Object.keys(r.encouragement);
    if (keys.length !== 1 || keys[0] !== "level") {
      errs.push("encouragement 应只含 level，实际: " + JSON.stringify(keys));
    } else if (!VALID_LEVELS.includes(r.encouragement.level)) {
      errs.push("level 值非法: " + JSON.stringify(r.encouragement.level));
    }
  }

  if (r.accuracy !== null && r.accuracy !== undefined) {
    if (typeof r.accuracy !== "number" || r.accuracy < 0 || r.accuracy > 1) {
      errs.push("accuracy 越界: " + JSON.stringify(r.accuracy));
    }
  }
  return errs;
}

/* ---------- 4. 主流程 ---------- */

(async function main() {
  const args = process.argv.slice(2);
  const images = collectImages(args);

  console.log("=== 监督小宠 C 模块 · 跑批测试 ===");
  console.log("识别模块: " + RECOGNIZE_PATH);
  console.log("待测图片: " + images.length + " 张\n");

  if (images.length === 0) {
    console.log("没有找到图片。可以：");
    console.log("  1. 把学习截图放进 " + path.join(WORKDIR, "testshots"));
    console.log("  2. 或 node batch-test.js \"完整路径/图片.png\"");
    return;
  }

  let env;
  try {
    env = await setupEnv();
  } catch (e) {
    console.log("环境初始化失败: " + e.message);
    return;
  }
  console.log("SDK: " + env.sdkUrl.replace(/^https:\/\//, ""));
  console.log("配置: 超时 " + env.api.recognizeScreenshotConfig.TIMEOUT_MS + "ms / 重试 " +
    env.api.recognizeScreenshotConfig.MAX_RETRIES + " 次\n");

  const rows = [];
  for (const p of images) {
    const name = path.basename(p);
    const ext = path.extname(p).toLowerCase();
    const file = { name: name, type: MIME[ext] || "image/png", size: fs.statSync(p).size, _path: p };

    let r = null, err = null;
    try {
      r = await env.api.recognizeScreenshot(file, "demo_zhang");
    } catch (e) {
      err = e.message;
    }

    if (err) {
      rows.push({ name, ok: false, kind: "error", detail: err, ms: null });
      console.log("  ✗ " + name + " → 调用异常: " + err);
      continue;
    }

    const errs = validate(r);
    const lv = r.encouragement ? r.encouragement.level : null;
    const ms = r._elapsed_ms;
    const codes = (r.warnings || []).map((w) => w.code);

    if (errs.length) {
      rows.push({ name, ok: false, kind: "invalid", detail: errs.join("; "), ms });
      console.log("  ✗ " + name + " → JSON 非法: " + errs.join("; "));
    } else if (lv === "") {
      rows.push({ name, ok: true, kind: "notstudy", detail: codes.join(",") || "(无)", ms });
      console.log("  ○ " + name + " → 非学习图片（已正确拒绝） warnings=[" + (codes.join(",") || "无") + "] " + ms + "ms");
    } else {
      const brief = [
        r.source_app || "App未知",
        r.event_date || "日期未知",
        r.duration_minutes != null ? r.duration_minutes + "分" : "时长未知",
        r.total_questions != null ? r.total_questions + "题" : "题量未知",
        r.accuracy != null ? Math.round(r.accuracy * 100) + "%" : "正确率未知",
      ].join(" · ");
      rows.push({ name, ok: true, kind: "study", detail: brief, ms, level: lv });
      console.log("  ✓ " + name + " → " + lv + " | " + brief + " | " + ms + "ms" +
        (codes.length ? " | warnings=[" + codes.join(",") + "]" : ""));
    }
  }

  /* 汇总 */
  const total = rows.length;
  const okCount = rows.filter((x) => x.ok).length;
  const studyCount = rows.filter((x) => x.kind === "study").length;
  const notStudy = rows.filter((x) => x.kind === "notstudy").length;
  const failed = rows.filter((x) => !x.ok);
  const mss = rows.filter((x) => x.ms != null).map((x) => x.ms);

  console.log("\n=== 汇总 ===");
  console.log("总图片数:      " + total);
  console.log("出合法 JSON:   " + okCount + " / " + total +
    (total > 0 ? "（" + Math.round((okCount / total) * 100) + "%）" : ""));
  console.log("  其中学习截图: " + studyCount);
  console.log("  非学习已拒绝: " + notStudy);
  console.log("  失败:         " + failed.length);
  if (mss.length) {
    console.log("耗时:          最快 " + Math.min.apply(null, mss) + "ms / 最慢 " +
      Math.max.apply(null, mss) + "ms / 平均 " +
      Math.round(mss.reduce((a, b) => a + b, 0) / mss.length) + "ms");
  }

  // 任务卡验收口径：以「学习截图」为准，非学习图片不计入分母
  if (studyCount + failed.length > 0) {
    const denom = studyCount + failed.length;
    console.log("\n任务卡验收口径（学习类 " + denom + " 张）: " + studyCount + "/" + denom +
      (studyCount / denom >= 5 / 6 ? "  ✓ 达标（≥5/6）" : "  ✗ 未达标"));
  } else {
    console.log("\n提示：本批没有学习截图，无法给出 5/6 验收结论。请放入真实学习截图后重跑。");
  }

  if (failed.length) {
    console.log("\n失败明细:");
    failed.forEach((f) => console.log("  - " + f.name + ": " + f.detail));
  }
})();
