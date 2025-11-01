export interface ModelOption {
    id: string
    label: string
}

const rawFallbackModels = import.meta.env.VITE_OPENAI_FALLBACK_MODELS as string | undefined

const parsedFallback = (rawFallbackModels ?? 'gpt-4o-mini')
    .split(',')
    .map((model) => model.trim())
    .filter((model) => model.length > 0)

export const FALLBACK_MODELS: ModelOption[] = (parsedFallback.length > 0 ? parsedFallback : ['gpt-4o-mini']).map(
    (id) => ({ id, label: id }),
)
export const FALLBACK_DEFAULT_MODEL = FALLBACK_MODELS[0]?.id ?? 'gpt-4o-mini'
