export type Entries<T> = {
    [K in keyof T]: [K, T[K]]
}[keyof T][]

export const entries = <T extends object>(state: T): Entries<T> => {
    return Object.entries(state) as Entries<T>
}

export const keys = <T extends object>(state: T): (keyof T)[] => {
    return Object.keys(state) as (keyof T)[]
}

export const values = <T extends object>(state: T): T[keyof T][] => {
    return Object.values(state) as T[keyof T][]
}