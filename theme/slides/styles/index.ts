// Fonts ship with the theme (@fontsource, woff2 only — see setup/vite-plugins.ts), so builds and PDF
// exports never depend on Google Fonts or on whatever the machine has installed:
//   Chakra Petch 500/600/700   display (headings, labels, numerals)
//   Noto Sans SC 400/500/700   body text, and every CJK glyph of the display face
//   JetBrains Mono 400/500/700 data (Lean names, GIDs, numbers, page numbers)
//   TR Math                    KaTeX Main for arrows, operators and brackets none of the above has
//                              (registered below with a unicode-range, so it never replaces them)
// Colours come only from theme/generated/tokens.css (generated from theme/tokens.json).
import '@fontsource/chakra-petch/500.css'
import '@fontsource/chakra-petch/600.css'
import '@fontsource/chakra-petch/700.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/noto-sans-sc/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/700.css'
import '../../generated/tokens.css'
import './deck.css'
import './backdrop.css'
import katexMain from 'katex/dist/fonts/KaTeX_Main-Regular.woff2?url'
import katexMainBold from 'katex/dist/fonts/KaTeX_Main-Bold.woff2?url'

const MATH_RANGE = 'U+00AC, U+00B1, U+00D7, U+00F7, U+2016, U+2032-2037, U+2190-21FF, U+2200-22FF, U+2300-23FF, U+27E8-27EB'
if (typeof document !== 'undefined') {
  document.fonts.add(new FontFace('TR Math', `url(${katexMain}) format("woff2")`, { unicodeRange: MATH_RANGE, weight: '100 600' }))
  document.fonts.add(new FontFace('TR Math', `url(${katexMainBold}) format("woff2")`, { unicodeRange: MATH_RANGE, weight: '700 900' }))
}
