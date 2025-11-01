import 'vue/jsx'

declare global {
    namespace JSX {
        interface IntrinsicElements {
            div: any
            span: any
            button: any
            input: any
            label: any
            form: any
            select: any
            option: any
            textarea: any
            img: any
            a: any
            p: any
            h1: any
            h2: any
            h3: any
            h4: any
            h5: any
            h6: any
            ul: any
            li: any
            // добавьте другие HTML элементы по необходимости
        }
    }
}