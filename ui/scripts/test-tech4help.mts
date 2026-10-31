import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const catalogPath = resolve(root, 'src/lib/tech4help/catalog.json');
const catalog = JSON.parse(readFileSync(catalogPath, 'utf8'));
const source = readFileSync(resolve(root, 'src/lib/tech4help/configuration.ts'), 'utf8');
const exports: { tech4HelpConfiguration?: (runtime: string) => { model_overrides: Record<string, unknown> } } = {};
runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
}).outputText, { exports, require: createRequire(catalogPath) });

for (const runtime of ['docker', 'native']) {
    const config = exports.tech4HelpConfiguration!(runtime);
    const overrides = config.model_overrides;
    assert.equal(overrides.is_realtime, false);
    for (const section of ['llm', 'stt', 'tts']) {
        const value = overrides[section] as { provider: string; model: string; api_key: string | null; base_url: string };
        assert.equal(value.provider, 'speaches');
        assert.equal(value.api_key, null);
        assert.equal(value.model, catalog.models[section]);
        const url = new URL(value.base_url);
        assert.equal(url.pathname, '/v1');
        assert.equal(url.hostname, runtime === 'native' ? '127.0.0.1' : section === 'llm' ? 'ollama' : 'speaches');
        assert.equal(url.port, section === 'llm' ? '11434' : runtime === 'native' ? '8001' : '8000');
    }
    const other = exports.tech4HelpConfiguration!(runtime);
    assert.notEqual(config.model_overrides, other.model_overrides);
    console.log(`PASS ${runtime}: all AI services use independent, keyless local settings`);
}
assert.equal(new Set(catalog.starters.map((starter: { id: string }) => starter.id)).size, 2);
console.log('PASS two distinct Tech4Help intake starters');

const nextConfigSource = readFileSync(resolve(root, 'next.config.ts'), 'utf8');
const nextExports: { default?: { output: string } } = {};
runInNewContext(ts.transpileModule(nextConfigSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, {
    exports: nextExports,
    process: { env: { ENABLE_TELEMETRY: 'false' } },
    require: () => ({ withSentryConfig: () => { throw new Error('Local builds must not initialize the Sentry build plugin'); } }),
});
assert.equal(nextExports.default?.output, 'standalone');
console.log('PASS telemetry-disabled build skips the Sentry build plugin');
