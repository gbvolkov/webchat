<script lang="ts" setup>
import { TTagVariant } from '@/ui/common/tag/types'

interface Props {
  variant: TTagVariant
}

const props = defineProps<Props>()
</script>
<template>
  <a-tag
      :class="['tag', `tag_${props.variant}`]"
  >
    <slot />
  </a-tag>
</template>
<style lang="css" scoped>
.tag {
  composes: aiRobotoMedium from global;
  border: initial;
}

.tag_orange {
  color: var(--orange_text);
  background-color: var(--orange_bg);
}

.tag_blue {
  color: var(--blue_text);
  background-color: var(--blue_bg);
}

.tag_purple {
  color: var(--purple_text);
  background-color: var(--purple_bg);
}

.tag_pink {
  color: var(--pink_text);
  background-color: var(--pink_bg);
}
</style>