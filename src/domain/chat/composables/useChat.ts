import { ref } from 'vue'
import type { Ref } from 'vue'
import type { ChatState } from '../models'

export const useChat = (): {
  state: Ref<ChatState>
} => {
  const state: Ref<ChatState> = ref({
    messages: [],
    isLoading: false,
  })

  return {
    state,
  }
}
