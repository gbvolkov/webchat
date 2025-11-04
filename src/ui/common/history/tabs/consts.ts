export enum ChatHistoryTab {
    All= 'All',
    Documents= 'Documents',
    CreativeProcesses= 'CreativeProcesses',
    Products= 'Products',
}

export const CHAT_HISTORY_TABS: Record<ChatHistoryTab, string> = {
    [ChatHistoryTab.All]: 'pages.chatsHistory.tabs.all',
    [ChatHistoryTab.Documents]: 'pages.chatsHistory.tabs.documents',
    [ChatHistoryTab.CreativeProcesses]: 'pages.chatsHistory.tabs.creative',
    [ChatHistoryTab.Products]: 'pages.chatsHistory.tabs.products',
}
