/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'logos-primary': '#6366f1',
                'logos-dark': '#1e1b4b',
                'logos-surface': '#111827',
                'logos-surface-alt': '#1f2937',
            },
        },
    },
    plugins: [],
    corePlugins: {
        preflight: false, // Disable to avoid conflicts with Naive UI
    },
}
