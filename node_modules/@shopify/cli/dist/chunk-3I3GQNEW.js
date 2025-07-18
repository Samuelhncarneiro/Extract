import {
  __commonJS,
  __require,
  init_cjs_shims
} from "./chunk-PKR7KJ6P.js";

// ../../node_modules/.pnpm/has-flag@4.0.0/node_modules/has-flag/index.js
var require_has_flag = __commonJS({
  "../../node_modules/.pnpm/has-flag@4.0.0/node_modules/has-flag/index.js"(exports, module) {
    "use strict";
    init_cjs_shims();
    module.exports = (flag, argv = process.argv) => {
      let prefix = flag.startsWith("-") ? "" : flag.length === 1 ? "-" : "--", position = argv.indexOf(prefix + flag), terminatorPosition = argv.indexOf("--");
      return position !== -1 && (terminatorPosition === -1 || position < terminatorPosition);
    };
  }
});

// ../../node_modules/.pnpm/supports-color@8.1.1/node_modules/supports-color/index.js
var require_supports_color = __commonJS({
  "../../node_modules/.pnpm/supports-color@8.1.1/node_modules/supports-color/index.js"(exports, module) {
    "use strict";
    init_cjs_shims();
    var os = __require("os"), tty = __require("tty"), hasFlag = require_has_flag(), { env } = process, flagForceColor;
    hasFlag("no-color") || hasFlag("no-colors") || hasFlag("color=false") || hasFlag("color=never") ? flagForceColor = 0 : (hasFlag("color") || hasFlag("colors") || hasFlag("color=true") || hasFlag("color=always")) && (flagForceColor = 1);
    function envForceColor() {
      if ("FORCE_COLOR" in env)
        return env.FORCE_COLOR === "true" ? 1 : env.FORCE_COLOR === "false" ? 0 : env.FORCE_COLOR.length === 0 ? 1 : Math.min(Number.parseInt(env.FORCE_COLOR, 10), 3);
    }
    function translateLevel(level) {
      return level === 0 ? !1 : {
        level,
        hasBasic: !0,
        has256: level >= 2,
        has16m: level >= 3
      };
    }
    function supportsColor(haveStream, { streamIsTTY, sniffFlags = !0 } = {}) {
      let noFlagForceColor = envForceColor();
      noFlagForceColor !== void 0 && (flagForceColor = noFlagForceColor);
      let forceColor = sniffFlags ? flagForceColor : noFlagForceColor;
      if (forceColor === 0)
        return 0;
      if (sniffFlags) {
        if (hasFlag("color=16m") || hasFlag("color=full") || hasFlag("color=truecolor"))
          return 3;
        if (hasFlag("color=256"))
          return 2;
      }
      if (haveStream && !streamIsTTY && forceColor === void 0)
        return 0;
      let min = forceColor || 0;
      if (env.TERM === "dumb")
        return min;
      if (process.platform === "win32") {
        let osRelease = os.release().split(".");
        return Number(osRelease[0]) >= 10 && Number(osRelease[2]) >= 10586 ? Number(osRelease[2]) >= 14931 ? 3 : 2 : 1;
      }
      if ("CI" in env)
        return ["TRAVIS", "CIRCLECI", "APPVEYOR", "GITLAB_CI", "GITHUB_ACTIONS", "BUILDKITE", "DRONE"].some((sign) => sign in env) || env.CI_NAME === "codeship" ? 1 : min;
      if ("TEAMCITY_VERSION" in env)
        return /^(9\.(0*[1-9]\d*)\.|\d{2,}\.)/.test(env.TEAMCITY_VERSION) ? 1 : 0;
      if (env.COLORTERM === "truecolor")
        return 3;
      if ("TERM_PROGRAM" in env) {
        let version = Number.parseInt((env.TERM_PROGRAM_VERSION || "").split(".")[0], 10);
        switch (env.TERM_PROGRAM) {
          case "iTerm.app":
            return version >= 3 ? 3 : 2;
          case "Apple_Terminal":
            return 2;
        }
      }
      return /-256(color)?$/i.test(env.TERM) ? 2 : /^screen|^xterm|^vt100|^vt220|^rxvt|color|ansi|cygwin|linux/i.test(env.TERM) || "COLORTERM" in env ? 1 : min;
    }
    function getSupportLevel(stream, options = {}) {
      let level = supportsColor(stream, {
        streamIsTTY: stream && stream.isTTY,
        ...options
      });
      return translateLevel(level);
    }
    module.exports = {
      supportsColor: getSupportLevel,
      stdout: getSupportLevel({ isTTY: tty.isatty(1) }),
      stderr: getSupportLevel({ isTTY: tty.isatty(2) })
    };
  }
});

export {
  require_has_flag,
  require_supports_color
};
//# sourceMappingURL=chunk-3I3GQNEW.js.map
