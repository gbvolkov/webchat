import dayjs from 'dayjs'

export const isToday = (date: string) => dayjs(date).isToday()