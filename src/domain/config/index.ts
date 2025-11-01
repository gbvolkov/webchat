export interface GwpChatConfig {
  apiUrl: string
  theme?: 'light' | 'dark' | 'auto'
}

export const defaultConfig: Partial<GwpChatConfig> = {
  theme: 'auto',
}
