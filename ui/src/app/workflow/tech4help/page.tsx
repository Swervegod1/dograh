'use client';

import { ArrowLeft, ArrowRight, HeartHandshake, Loader2, Monitor } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';

import { createWorkflowApiV1WorkflowCreateDefinitionPost } from '@/client/sdk.gen';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import catalog from '@/lib/tech4help/catalog.json';
import { type LocalRuntime, tech4HelpConfiguration } from '@/lib/tech4help/configuration';

import WorkflowLayout from '../WorkflowLayout';

const setupGuide = 'https://github.com/Swervegod1/dograh/blob/main/examples/tech4help/README.md';

export default function Tech4HelpPage() {
    const router = useRouter();
    const { user, loading, getAccessToken } = useAuth();
    const [runtime, setRuntime] = useState<LocalRuntime>('docker');
    const [creating, setCreating] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const inFlight = useRef(false);

    async function createAgent(starter: typeof catalog.starters[number]) {
        if (loading || !user || inFlight.current) return;
        inFlight.current = true;
        setCreating(starter.id);
        setError(null);
        try {
            const token = await getAccessToken();
            if (!token) throw new Error('Sign in again to create an agent.');
            const response = await createWorkflowApiV1WorkflowCreateDefinitionPost({
                body: {
                    ...starter.workflow,
                    workflow_configurations: tech4HelpConfiguration(runtime),
                },
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!response.data?.id) {
                throw new Error('The agent could not be created. Check your connection and AI settings, then try again.');
            }
            router.push(`/workflow/${response.data.id}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unable to create the agent. Please try again.');
            inFlight.current = false;
            setCreating(null);
        }
    }

    return (
        <WorkflowLayout showFeaturesNav>
            <div className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-8">
                <Link href="/workflow" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
                    <ArrowLeft className="h-4 w-4" /> All agents
                </Link>
                <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-emerald-950 sm:p-10 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-50">
                    <p className="mb-3 text-sm font-semibold uppercase tracking-widest">Tech4Help · Voice intake</p>
                    <h1 className="max-w-2xl text-3xl font-semibold leading-tight sm:text-4xl">Make the first conversation count.</h1>
                    <p className="mt-4 max-w-2xl text-base leading-relaxed">Give equipment donors and IT-service customers a clear place to start. Collect the details, confirm the summary, and leave the decisions to your team.</p>
                    <p className="mt-5 text-sm">Powered by local AI. No metered AI API required; hardware, hosting and phone service may cost extra.</p>
                </section>

                <section aria-labelledby="setup-heading" className="rounded-xl border p-5">
                    <h2 id="setup-heading" className="text-lg font-semibold">Start with your local models</h2>
                    <p className="mt-2 text-sm text-muted-foreground">Run the setup and model checks before testing a conversation. These agents use Qwen3 via Ollama, Whisper for listening and Kokoro for speech via Speaches.</p>
                    <div className="mt-4 flex flex-wrap items-end gap-4">
                        <div className="space-y-2">
                            <label htmlFor="tech4help-runtime" className="block text-sm font-medium">Where is the Dograh API running?</label>
                            <select id="tech4help-runtime" value={runtime} disabled={creating !== null}
                                onChange={(event) => setRuntime(event.target.value as LocalRuntime)}
                                className="h-10 rounded-md border bg-background px-3 text-sm">
                                <option value="docker">Tech4Help Docker stack</option>
                                <option value="native">On this computer, outside Docker</option>
                            </select>
                        </div>
                        <Button variant="outline" asChild>
                            <a href={setupGuide} target="_blank" rel="noopener noreferrer">Setup guide <ArrowRight className="ml-2 h-4 w-4" /></a>
                        </Button>
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">The selection sets these agents’ AI endpoints. Existing agents keep their settings.</p>
                </section>

                {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</p>}
                {!loading && !user && <p role="status" className="text-sm">Sign in to create your Tech4Help agents.</p>}
                <div className="grid gap-5 md:grid-cols-2">
                    {catalog.starters.map((starter, index) => {
                        const Icon = index === 0 ? HeartHandshake : Monitor;
                        return (
                            <section key={starter.id} className="flex flex-col rounded-xl border bg-card p-6">
                                <Icon className="mb-5 h-8 w-8 text-emerald-600" aria-hidden="true" />
                                <h2 className="text-xl font-semibold">{starter.title}</h2>
                                <p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">{starter.description}</p>
                                <p className="mb-6 mt-4 text-xs text-muted-foreground">AI disclosure · Optional follow-up contact · Structured summary</p>
                                <Button onClick={() => createAgent(starter)} disabled={loading || !user || creating !== null}>
                                    {creating === starter.id ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Creating agent…</> : <>Create {index === 0 ? 'donation' : 'IT-service'} agent <ArrowRight className="ml-2 h-4 w-4" /></>}
                                </Button>
                            </section>
                        );
                    })}
                </div>
                <section className="border-t pt-6 text-sm text-muted-foreground">
                    <h2 className="font-semibold text-foreground">After creating an agent</h2>
                    <p className="mt-2">Review the prompts in the editor, test with fictional details, then review the run transcript and extracted fields. The starters record intake for your team; email, booking and phone connections need separate setup.</p>
                </section>
            </div>
        </WorkflowLayout>
    );
}
