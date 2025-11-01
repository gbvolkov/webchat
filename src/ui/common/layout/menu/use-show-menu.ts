import {useToggle} from '@/utils/use-toggle'

const IS_SHOW_MENU_KEY = 'is_show_menu'

export const useShowMenu = () => {
    const getDefaultIsShowMenu = () => {
        try {
            return JSON.parse(localStorage.getItem(IS_SHOW_MENU_KEY) || '') || false
        } catch (e) {
            return false
        }
    }
    const {
        isActive: isShowMenu,
        toggleHandler: toggleMenu
    } = useToggle(getDefaultIsShowMenu())

    const handleToggleMenu = () => {
        localStorage.setItem(IS_SHOW_MENU_KEY, JSON.stringify(!isShowMenu.value))
        toggleMenu()
    }

    return {
        isShowMenu,
        handleToggleMenu,
    }
}