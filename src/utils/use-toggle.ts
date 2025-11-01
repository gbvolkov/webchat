import { ref } from 'vue'

export const useToggle = (isInitialActive = false) => {
    const isActive = ref(isInitialActive)

    const closeHandler = () => isActive.value = false

    const openHandler = () => isActive.value = true

    const toggleHandler = () => isActive.value = !isActive.value

    return {
        isActive,
        closeHandler,
        openHandler,
        toggleHandler,
    }

}