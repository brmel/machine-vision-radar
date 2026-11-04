import { Config } from "@remotion/cli/config";
import type { WebpackConfiguration } from "@remotion/bundler";
import { enableTailwind } from "@remotion/tailwind-v4";

export function studioWebpack(config: WebpackConfiguration): WebpackConfiguration {
  const rules = (config.module?.rules ?? []).map((rule) => {
    if (!rule || typeof rule !== "object" || !Array.isArray(rule.use)) return rule;
    const use =
      rule.use.map((step) => (step && typeof step === "object" && String(step.loader).includes("esbuild-loader")
      ? { ...step, options: { ...(typeof step.options === "object" ? step.options : {}), jsx: "automatic" } } : step));
    return { ...rule, use };
  });
  return enableTailwind({ ...config, module: { ...config.module, rules } });
}

Config.overrideWebpackConfig(studioWebpack);
