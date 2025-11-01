<script lang='ts' setup>
import { ITextViewVariant, ITextViewColor } from '@/ui/common/text-view/types'

interface Props {
  variant: ITextViewVariant
  color?: ITextViewColor
}

const props = defineProps<Props>()
</script>

<template>
<div
    :class="[props.variant, props.color]"

>
  <slot />
</div>

</template>

<style lang="scss" scoped>

.roboto_36_bold {
  font-weight: 700;
  font-size: 36px;
  line-height: 100%;
}

.roboto_32_bold {
  font-weight: 700;
  font-size: 32px;
  line-height: 100%;
}

.roboto_28_bold {
  font-weight: 700;
  font-size: 28px;
  line-height: 100%;
}

.roboto_14_regular {
  font-family: sans-serif;
  font-weight: 400;
  font-style: normal;
  font-size: 14px;
  line-height: 100%;
}

.roboto_13_medium {
  font-family: sans-serif;
  font-weight: 500;
  font-style: normal;
  font-size: 13px;
  line-height: 100%;
}

.gray_60 {
  color: var(--gray_60);
}
</style>
