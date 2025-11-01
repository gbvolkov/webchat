export enum ChatHistoryTab {
    All= 'All',
    Documents= 'Documents',
    CreativeProcesses= 'CreativeProcesses',
    Products= 'Products',
}

export const CHAT_HISTORY_TABS: Record<ChatHistoryTab, string> = {
    [ChatHistoryTab.All]: 'Все чаты',
    [ChatHistoryTab.Documents]: 'Документы и отчеты',
    [ChatHistoryTab.CreativeProcesses]: 'Креативные процессы',
    [ChatHistoryTab.Products]: 'Продукты',
}