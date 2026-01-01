/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Stone Garden (Light Mode)
                garden: {
                    base: '#f8f6f1',
                    taupe: '#8e8071',
                    ash: '#a79a8f',
                },
                // Stone Night (Dark Mode)
                night: {
                    base: '#242423',
                    taupe: '#9a8c83',
                    basalt: '#5e5e5b',
                },
                brand: {
                    primary: 'var(--brand-color)',
                    secondary: 'var(--accent-green)',
                    contrast: 'var(--text-on-brand)',
                },
                'app-bg': 'var(--bg-color)',
                'app-surface': 'var(--surface-color)',
                'app-border': 'var(--border-color)',
            },
            borderRadius: {
                'soul': '1.5rem',
            }
        },
    },
    plugins: [
        require('@tailwindcss/typography'),
    ],
    corePlugins: {
        preflight: false,
    },
}
