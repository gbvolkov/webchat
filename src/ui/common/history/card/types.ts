import {TTagVariant} from "@/ui/common/tag/types";

export interface Props {
    tagType: TTagVariant
    tagLabel: string
    text: string
    date: string
    whenClickExport: () => void
    whenClickDelete: () => void
}