import catalog from './catalog.json';

export type LocalRuntime = 'docker' | 'native';

export function tech4HelpConfiguration(runtime: LocalRuntime) {
    const llmUrl = runtime === 'docker' ? 'http://ollama:11434/v1' : 'http://127.0.0.1:11434/v1';
    const speechUrl = runtime === 'docker' ? 'http://speaches:8000/v1' : 'http://127.0.0.1:8001/v1';
    return {
        max_call_duration: 600,
        max_user_idle_timeout: 30,
        turn_stop_strategy: 'transcription',
        model_overrides: {
            is_realtime: false,
            llm: { provider: 'speaches', model: catalog.models.llm, base_url: llmUrl, api_key: null },
            stt: { provider: 'speaches', model: catalog.models.stt, base_url: speechUrl, language: 'en', api_key: null },
            tts: { provider: 'speaches', model: catalog.models.tts, base_url: speechUrl, voice: catalog.models.voice, api_key: null },
        },
    };
}
