export enum ScreenSize {
    MOBILE = 'mobile',
    TABLET = 'tablet',
    DESKTOP_SMALL = 'desktop-small',
    DESKTOP_LARGE = 'desktop-large',
    DESKTOP_XL = 'desktop-xl'
}

export const SCREEN_BREAKPOINTS = {
    [ScreenSize.MOBILE]: 767,
    [ScreenSize.TABLET]: 1023,
    [ScreenSize.DESKTOP_SMALL]: 1280,
    [ScreenSize.DESKTOP_LARGE]: 1440,
    [ScreenSize.DESKTOP_XL]: 1920
} as const

export function getCurrentScreenSize(width: number = window.innerWidth): ScreenSize {
    if (width <= SCREEN_BREAKPOINTS[ScreenSize.MOBILE]) {
        return ScreenSize.MOBILE
    } else if (width > SCREEN_BREAKPOINTS[ScreenSize.MOBILE] && width <= SCREEN_BREAKPOINTS[ScreenSize.TABLET]) {
        return ScreenSize.TABLET
    } else if (width > SCREEN_BREAKPOINTS[ScreenSize.TABLET] && width <= SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_SMALL]) {
        return ScreenSize.DESKTOP_SMALL
    } else if (width > SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_SMALL] && width <= SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_LARGE]) {
        return ScreenSize.DESKTOP_LARGE
    } else {
        return ScreenSize.DESKTOP_XL
    }
}

import { ref, onMounted, onUnmounted, computed } from 'vue'

export const useScreenSize = ()  => {
    const windowWidth = ref(window.innerWidth)

    const updateWidth = () => {
        windowWidth.value = window.innerWidth
    }

    onMounted(() => {
        window.addEventListener('resize', updateWidth)
    })

    onUnmounted(() => {
        window.removeEventListener('resize', updateWidth)
    })

    const IS_MOBILE = computed(() => windowWidth.value <= SCREEN_BREAKPOINTS[ScreenSize.MOBILE])

    const IS_TABLET = computed(() => windowWidth.value > SCREEN_BREAKPOINTS[ScreenSize.MOBILE] && windowWidth.value <= SCREEN_BREAKPOINTS[ScreenSize.TABLET])

    const IS_DESKTOP_SMALL = computed(() => windowWidth.value > SCREEN_BREAKPOINTS[ScreenSize.TABLET] && windowWidth.value <= SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_SMALL])

    const IS_DESKTOP_LARGE = computed(() => windowWidth.value > SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_SMALL] && windowWidth.value <= SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_LARGE])

    const IS_DESKTOP_XL = computed(() => windowWidth.value > SCREEN_BREAKPOINTS[ScreenSize.DESKTOP_LARGE])

    const screenSize = computed((): ScreenSize => getCurrentScreenSize(windowWidth.value))

    return {
        windowWidth,
        screenSize,
        IS_MOBILE,
        IS_TABLET,
        IS_DESKTOP_SMALL,
        IS_DESKTOP_LARGE,
        IS_DESKTOP_XL
    }
}