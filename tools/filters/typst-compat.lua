--[[
typst-compat.lua — keeps formulas faithful on the way from TeX to Typst. Loaded by tr-book.lua (formulas in
the text) and tr-env.lua (formulas in environment titles); used only for Typst output.

Pandoc's Typst writer (texmath) and Typst itself differ from TeX (and from KaTeX, which sets the HTML
edition) in ways that either fail the PDF or silently print something else. Each is fixed here, either in
the TeX source before the conversion (M.tex) or in the Typst code after it (M.rename):

1. Symbol names the pinned Typst (requirements.txt) no longer knows: a single `\cap` fails the whole PDF
   ("unknown variable: sect"). Long arrows come out short, `\backslash` as the set difference.
2. Spaces. The writer only knows thin, medium and quad: `\;` comes out as `#h(0em)`, `\!` as `#h(-1em)`;
   `\thinspace`, `\mkern`, `\kern`, … do not convert at all, and the formula is printed as TeX source.
   Typst, in turn, lets an explicit space replace the automatic space of the atoms next to it, where TeX
   adds the two: `a \;=\; b` would be set like `a = b`.
3. Bars. `\|` comes out as the relation ∥ (relation spacing, a superscript stacked above it); single bars
   are "fences" that keep the blanks of the source: `| ψ⟩`, `| x |²`.
4. Operator names and text. `\operatorname{Tr}(ρ)` is written as a bare string, which Typst sets as text
   with a word space after it: "Tr (ρ)". Blanks next to `\text{…}` are set as spaces too; inside it the
   writer swallows the blank after `\&`, `\%`, … and drops `\^{}`.
5. Sized delimiters. `\bigl(` is written as a scaled box: no room is reserved for it, it is spaced like a
   word and it forgets whether it opens or closes. `\bigm`, `\Bigm` do not convert at all.
6. Groups the writer flattens or drops: `\tfrac`/`\dfrac` (size), `\mathbin{…}` and its relatives (class),
   `\overset`/`\underset`/`\stackrel` (set beside the base), `\xrightarrow{…}` (does not stretch),
   `\left. … \right|` (the bar stays small), `\pmod`/`\bmod` (spacing).
7. Matrices. `smallmatrix`, `matrix` and `array` outside `\left…\right` are written as bare rows (an
   inline matrix breaks over two lines); `vmatrix` gets a delimiter Typst rejects.

Facts the writer loses are carried through it: widths as `\hspace{<5000 + n>em}`, everything else as
private-use characters, which it passes on unchanged. A formula the writer cannot convert after the rewrite
is converted as the author wrote it.

tools/tests/test_pandoc.py compiles every symbol KaTeX renders through Pandoc, these filters and Typst, so a
new rename shows up as a failing test; tools/tests/test_pdf_math.py measures the results as laid out. The
theme must not define names Typst's math uses (it is imported whole into the document); the same test
checks that.
]]

local M = {}

-- {name Pandoc writes, name Typst knows}; matched as whole names (a longer name is not touched), and the
-- modifiers that follow (sect.big → inter.big) are kept.
M.RENAMES = {
  { "sect", "inter" },             -- \cap \Cap \bigcap \sqcap: sect, sect.double, sect.big, sect.sq
  { "dot.circle", "dot.o" },       -- \odot \bigodot
  { "times.circle", "times.o" },   -- \otimes \bigotimes
  { "minus.circle", "minus.o" },   -- \ominus
  { "dash.circle", "dash.o" },     -- \circleddash
}

-- ------------------------------------------------------------------ TeX, before the conversion

-- Widths are carried through the writer as \hspace{<SPACE_BASE + n>em}, n in 18ths of an em (1 mu).
local SPACE_BASE, SPACE_SPAN = 5000, 2000

-- Spaces the writer drops, distorts or cannot read. Thin (\,), medium (\: \> \ ) and quad convert correctly.
local SPACES = {
  [";"] = 5, ["!"] = -3,
  thickspace = 5, medspace = 4, thinspace = 3, enspace = 9,
  negthinspace = -3, negmedspace = -4, negthickspace = -5,
}

-- Commands followed by a dimension, and the units they take (in 18ths of an em; 10pt to the em).
local DIMENSIONS = { hspace = true, hskip = true, kern = true, mkern = true, mskip = true }
local UNITS = { em = 18, mu = 1, ex = 7.75, pt = 1.8, bp = 1.8, pc = 21.6, mm = 5.12, cm = 51.2, ["in"] = 130.1 }

-- Their argument is text, not math.
local TEXT = {
  text = true, textrm = true, textbf = true, textit = true, texttt = true, textsf = true,
  textnormal = true, textup = true, mbox = true, hbox = true,
}

-- Facts the writer loses are carried through it by private-use characters, which it passes on unchanged as
-- separate tokens; M.rename turns them into Typst.
local MARK_OPEN_BAR = utf8.char(0xE000)      -- \lvert: an opening bar
local MARK_CLOSE_BAR = utf8.char(0xE001)     -- \rvert: a closing bar
local MARK_LIMITS = utf8.char(0xE002)        -- \operatorname*: limits above and below in display style
local MARK_BIG = 0xE010                      -- + 4 * size + side: \big \bigl \bigr \bigm … \Biggm
local MARK_SYMBOL = 0xE100                   -- + index in SYMBOLS: a symbol the writer has no name for
local MARK_GROUP = 0xE040                    -- + index in GROUPS: the \overline{…} after it carries that group
local MARK_TOKEN = 0xE060                    -- + index in TOKENS: applies to the token after it
-- Groups the writer flattens or drops. M.tex wraps their content in \overline{…}, which the writer turns
-- into the call overline(…) whatever is inside; M.rename then renames the call. { Typst function, first
-- argument }.
local GROUPS = {
  { "inline" }, { "display" }, { "class", '"binary"' }, { "class", '"relation"' }, { "class", '"large"' },
  { "class", '"normal"' }, { "class", '"opening"' }, { "class", '"closing"' }, { "class", '"punctuation"' },
  { "limits" }, { "lr" }, { "frac" }, { "inline", nil, "frac" }, { "display", nil, "frac" },
}
local GROUP = {
  tbinom = 1, dbinom = 2, mathbin = 3, mathrel = 4, mathop = 5, mathord = 6, mathopen = 7,
  mathclose = 8, mathpunct = 9, limits = 10, lr = 11, frac = 12, tfrac = 13, dfrac = 14, cfrac = 14,
}
local TOKEN = { stretch = 1, matrix = 2, smallmatrix = 3, vmatrix = 4, Vmatrix = 5, limits = 6, nolimits = 7 }
-- Matrix environments the writer sets as bare rows (or, for the bars, with a delimiter Typst rejects): they
-- are converted as pmatrix and get their own delimiter afterwards.
local MATRIX = { matrix = "#none", smallmatrix = "#none", array = "#none", vmatrix = "bar.v",
                 Vmatrix = "bar.v.double" }
local MATRIX_DELIMITER = { [2] = "#none", [3] = "#none", [4] = "bar.v", [5] = "bar.v.double" }
local BIG_SIZE = { big = 0, Big = 1, bigg = 2, Bigg = 3 }
local BIG_SIDE = { [""] = 0, l = 1, r = 2, m = 3 }
local BIG_PERCENT = { [0] = 120, 180, 240, 300 }
local BIG_CLASS = { [0] = "normal", "opening", "closing", "relation" }

-- Symbols the writer sets as a different one (the long arrows come out short). { TeX name, Typst name,
-- thick space on both sides (TeX defines \iff and its relatives with it) }.
local SYMBOLS = {
  { "longrightarrow", "arrow.r.long" }, { "longleftarrow", "arrow.l.long" },
  { "longleftrightarrow", "arrow.l.r.long" }, { "Longrightarrow", "arrow.r.double.long" },
  { "Longleftarrow", "arrow.l.double.long" }, { "Longleftrightarrow", "arrow.l.r.double.long" },
  { "longmapsto", "arrow.r.long.bar" },
  { "implies", "arrow.r.double.long", true }, { "impliedby", "arrow.l.double.long", true },
  { "iff", "arrow.l.r.double.long", true },
  { "backslash", 'class("normal", backslash)' },   -- the writer sets the set difference
  -- A brace the writer leaves bare is paired and sized by Typst like \left\{…\right\}; by name it is not.
  { "lbrace", "brace.l" }, { "rbrace", "brace.r" }, { "{", "brace.l" }, { "}", "brace.r" },
  { "&", "amp" },                            -- the writer leaves "&": an alignment point, nothing is printed
  -- The writer sets the curly variants (those of \succcurlyeq, \preccurlyeq).
  { "succeq", "succ.eq" }, { "preceq", "prec.eq" },
}
local SYMBOL_INDEX = {}
for index, symbol in ipairs(SYMBOLS) do SYMBOL_INDEX[symbol[1]] = index end

local function skip_blank(s, i)
  while s:sub(i, i):match("%s") do i = i + 1 end
  return i
end

-- s:sub(i, i) is "{": the index of its closing brace (the end of s when it is not closed).
local function group_end(s, i)
  local depth, n = 0, #s
  while i <= n do
    local c = s:sub(i, i)
    if c == "\\" then
      i = i + 2
    else
      if c == "{" then
        depth = depth + 1
      elseif c == "}" then
        depth = depth - 1
        if depth == 0 then return i end
      end
      i = i + 1
    end
  end
  return n
end

-- The dimension at s[i…] (after \hspace, \kern, …): its width in 18ths of an em and the index after it.
local function dimension(s, i)
  local j = skip_blank(s, i)
  if s:sub(j, j) == "*" then j = skip_blank(s, j + 1) end
  local braced = s:sub(j, j) == "{"
  if braced then j = skip_blank(s, j + 1) end
  local number, unit, k = s:match("^([+-]?%d*%.?%d+)%s*(%a%a)()", j)
  if not number or not UNITS[unit] then return nil end
  if braced then
    k = skip_blank(s, k)
    if s:sub(k, k) ~= "}" then return nil end
    k = k + 1
  end
  return tonumber(number) * UNITS[unit], k
end

-- Whether tex[i…] starts a space the writer mishandles: its width (18ths of an em) and the index after it.
local function space_at(tex, i)
  local word, j = tex:match("^\\(%a+)()", i)
  if not word then
    local width = SPACES[tex:sub(i + 1, i + 1)]
    if width then return width, i + 2 end
    return nil
  end
  if SPACES[word] then return SPACES[word], j end
  if DIMENSIONS[word] then return dimension(tex, j) end
  return nil
end

-- The bar command at tex[k…] and the index after it: "double" for \| \lVert \rVert \Vert, "single" for
-- \lvert \rvert \vert; nil for anything else.
local function bar_at(tex, k)
  if tex:sub(k, k + 1) == "\\|" then return "double", k + 2 end
  local word, e = tex:match("^\\(%a+)()", k)
  if word == "lVert" or word == "rVert" or word == "Vert" then return "double", e end
  if word == "lvert" or word == "rvert" or word == "vert" then return "single", e end
  return nil
end

-- The argument at tex[k…] (after blanks): a brace group, a control sequence or one character. Returns the
-- indices of its content and the index after it.
local function argument(tex, k)
  k = skip_blank(tex, k)
  local c = tex:sub(k, k)
  if c == "{" then
    local close = group_end(tex, k)
    return k + 1, close - 1, close + 1
  elseif c == "\\" then
    local _, e = tex:match("^\\(%a+)()", k)
    e = e or k + 2
    return k, e - 1, e
  elseif c == "" then
    return k, k - 1, k
  end
  local e = utf8.offset(tex, 2, k) or #tex + 1
  return k, e - 1, e
end

-- The \right that closes the \left whose delimiter ends before tex[k]: its index, or nil.
local function matching_right(tex, k)
  local level, n = 0, #tex
  while k <= n do
    if tex:sub(k, k) == "\\" then
      local word, e = tex:match("^\\(%a+)()", k)
      if word == "left" then
        level = level + 1
      elseif word == "right" then
        if level == 0 then return k end
        level = level - 1
      elseif word == "middle" and level == 0 then
        return nil                           -- \middle needs its \left and \right
      end
      k = e or k + 2
    else
      k = k + 1
    end
  end
  return nil
end

-- TeX math rewritten so that the writer converts it faithfully (see the head of this file). `display` says
-- whether the formula is displayed (\pmod is set wider there).
function M.tex(tex, display)
  local out, i, n = {}, 1, #tex
  local depth, bars = 0, {}                  -- brace depth; unmatched opening \| as { depth, index in out }
  local function emit(piece) out[#out + 1] = piece end
  local function space(width)
    local v = math.floor(width + 0.5)
    v = math.max(-SPACE_SPAN + 1, math.min(SPACE_SPAN - 1, v))
    if v ~= 0 then emit(string.format("\\hspace{%dem}", SPACE_BASE + v)) end
  end
  local function mark(base, index) return " " .. utf8.char(base + index) .. " " end
  -- The content of a group, rewritten like the formula itself.
  local function inner(first, last) return M.tex(tex:sub(first, last), display) end
  -- A group the writer would flatten: its content inside the carrier \overline{…}.
  local function group(kind, content)
    emit(mark(MARK_GROUP, GROUP[kind]) .. "\\overline{" .. content .. "}")
  end
  -- A \| left without a partner at this depth (or deeper) is an ordinary bar, not an opening delimiter.
  local function close_bars(d)
    while #bars > 0 and bars[#bars].depth >= d do
      out[bars[#bars].at] = "\\Vert "
      bars[#bars] = nil
    end
  end
  -- The delimiter at tex[k…] after \left, \right, \middle or a \big command, as the writer needs it there
  -- (the double bar as \Vert; nothing else changed), and the index after it.
  local function delimiter(k)
    k = skip_blank(tex, k)
    local kind, e = bar_at(tex, k)
    if kind == "double" then return "\\Vert ", e, kind end
    if kind == "single" then return tex:sub(k, e - 1), e, kind end
    local first, last, after = argument(tex, k)
    if tex:sub(k, k) == "{" then return "", k, nil end   -- not a delimiter: leave the group alone
    return tex:sub(first, last), after, nil
  end
  -- \text{…} and its relatives: the argument is text. A space command directly inside it still reaches the
  -- writer as a math space, so the text is split around it: \text{a\;b} → \text{a}<space>\text{b}. The writer
  -- also swallows the blank after an escaped character (\& \% \# \$ \_) and drops \^{} and \~{}.
  local function text_group(command, open)
    local close = group_end(tex, open)
    emit(command .. "{")
    local k, level = open + 1, 0
    while k < close do
      local c = tex:sub(k, k)
      if c == "\\" then
        local width, after = nil, nil
        if level == 0 then width, after = space_at(tex, k) end
        local symbol = tex:sub(k + 1, k + 1)
        if width then
          emit("}")
          space(width)
          emit(command .. "{")
          k = after
        elseif (symbol == "^" or symbol == "~") and tex:sub(k + 2, k + 3) == "{}" then
          emit(symbol == "^" and "\\textasciicircum{}" or "\\textasciitilde{}")
          k = k + 4
        elseif symbol:match("[&%%#$_]") and tex:sub(k + 2, k + 2):match("%s") then
          emit(tex:sub(k, k + 1) .. "{}")
          k = k + 2
        else
          local _, e = tex:match("^\\(%a+)()", k)
          e = e or k + 2
          emit(tex:sub(k, e - 1))
          k = e
        end
      else
        if c == "{" then level = level + 1 elseif c == "}" then level = level - 1 end
        emit(c)
        k = k + 1
      end
    end
    emit("}")
    return close + 1
  end
  while i <= n do
    local c = tex:sub(i, i)
    if c ~= "\\" then
      if c == "{" then
        depth = depth + 1
      elseif c == "}" then
        close_bars(depth)
        depth = depth - 1
      elseif c == "&" then
        close_bars(depth)
      end
      emit(c)
      i = i + 1
    else
      local word, j = tex:match("^\\(%a+)()", i)
      local width, after = space_at(tex, i)
      if width then
        space(width)
        i = after
      elseif not word then                   -- a control symbol: \| \\ \{ \, …
        local symbol = tex:sub(i + 1, i + 1)
        if symbol == "|" then
          if #bars > 0 and bars[#bars].depth == depth then
            bars[#bars] = nil
            emit("\\rVert ")
          else
            emit("\\lVert ")
            bars[#bars + 1] = { depth = depth, at = #out }
          end
        elseif SYMBOL_INDEX[symbol] then     -- \{ \}
          emit(mark(MARK_SYMBOL, SYMBOL_INDEX[symbol]))
        else
          if symbol == "\\" then close_bars(depth) end
          emit(tex:sub(i, i + 1))
        end
        i = i + 2
      elseif TEXT[word] then
        local k = skip_blank(tex, j)
        if tex:sub(k, k) == "{" then
          i = text_group("\\" .. word, k)
        else
          emit(tex:sub(i, j - 1))
          i = j
        end
      elseif word == "left" then
        local left, body = delimiter(j)
        local right = matching_right(tex, body)
        local close, after = nil, nil
        if right then close, after = delimiter(right + #"\\right") end
        if right and (left == "." or close == ".") and not (left == "." and close == ".") then
          -- A group with one delimiter (an evaluation bar, a brace on one side): the writer drops the group
          -- and sets the delimiter at its normal size.
          local function plain(d) return d == "." and "" or " " .. M.tex(d, display) .. " " end
          group("lr", plain(left) .. inner(body, right - 1) .. plain(close))
          i = after
        else
          -- The writer sizes \left…\right itself.
          emit("\\left" .. left)
          i = body
        end
      elseif word == "right" or word == "middle" then
        local d, e = delimiter(j)
        emit("\\" .. word .. d)
        i = e
      elseif BIG_SIZE[word:match("^[bB]igg?")] and BIG_SIDE[word:gsub("^[bB]igg?", "", 1)] then
        -- \big \Bigl \biggr …: the writer scales a box without reserving room for it and forgets the side.
        local size = BIG_SIZE[word:match("^[bB]igg?")]
        local side = BIG_SIDE[(word:gsub("^[bB]igg?", "", 1))]
        local d, e, kind = delimiter(j)
        emit(utf8.char(MARK_BIG + 4 * size + side))
        emit(kind == "single" and "|" or (d == "" and " " or " " .. d .. " "))
        i = e
      elseif word == "lvert" then
        emit(" " .. MARK_OPEN_BAR .. " ")
        i = j
      elseif word == "rvert" then
        emit(" " .. MARK_CLOSE_BAR .. " ")
        i = j
      elseif SYMBOL_INDEX[word] then
        local index = SYMBOL_INDEX[word]
        if SYMBOLS[index][3] then space(5) end
        emit(mark(MARK_SYMBOL, index))
        if SYMBOLS[index][3] then space(5) end
        i = j
      elseif word == "operatorname" and tex:sub(j, j) == "*" then
        emit(" " .. MARK_LIMITS .. " \\operatorname*")
        i = j + 1
      elseif word == "frac" or word == "tfrac" or word == "dfrac" or word == "cfrac" then
        -- The writer sets a fraction of two single items as "a / b", which Typst reads from the left:
        -- \frac{1}{\frac{1}{2}} would become (1/1)/2 and \frac{a}{b}^2 would become a/(b^2). It also ignores
        -- the size: \tfrac in a display would be set as large as \frac. As a group, the fraction keeps both.
        local a1, a2, after1 = argument(tex, j)
        local b1, b2, after2 = argument(tex, after1)
        group(word, "\\frac{" .. inner(a1, a2) .. "}{" .. inner(b1, b2) .. "}")
        i = after2
      elseif word == "tbinom" or word == "dbinom" then
        local a1, a2, after1 = argument(tex, j)   -- the writer does not know the sized forms
        local b1, b2, after2 = argument(tex, after1)
        group(word, "\\binom{" .. inner(a1, a2) .. "}{" .. inner(b1, b2) .. "}")
        i = after2
      elseif word == "limits" or word == "nolimits" then
        emit(mark(MARK_TOKEN, TOKEN[word]))    -- the writer ignores them
        i = j
      elseif GROUP[word] and word:match("^math") then
        -- \mathbin{…}, \mathrel{…}, …: the writer drops the class.
        local a1, a2, after1 = argument(tex, j)
        group(word, inner(a1, a2))
        i = after1
      elseif word == "overset" or word == "underset" or word == "stackrel" then
        -- The writer attaches the first argument as a script, which Typst sets beside an ordinary base.
        local a1, a2, after1 = argument(tex, j)
        local b1, b2, after2 = argument(tex, after1)
        emit("\\" .. word .. "{" .. inner(a1, a2) .. "}{")
        group("limits", inner(b1, b2))
        emit("}")
        i = after2
      elseif word:match("^x%a+arrow$") or word == "xmapsto" then
        emit(mark(MARK_TOKEN, TOKEN.stretch) .. "\\" .. word)   -- the arrow has to grow with its label
        i = j
      elseif word == "pmod" then
        -- TeX: 18mu (8mu in the text) before the parenthesis and 6mu after "mod"; the writer sets 4mu.
        local a1, a2, after1 = argument(tex, j)
        space(display and 18 or 8)
        emit("(\\mathrm{mod}")
        space(6)
        emit(inner(a1, a2) .. ")")
        i = after1
      elseif word == "bmod" then
        space(5)                             -- TeX: a binary "mod" with 5mu on each side
        emit("\\mathrm{mod}")
        space(5)
        i = j
      elseif word == "begin" or word == "end" then
        close_bars(depth)
        local name, e = tex:match("^%s*{(%a+%*?)}()", j)
        if name and MATRIX[name] then
          if word == "begin" then
            emit(mark(MARK_TOKEN, TOKEN[name] or TOKEN.matrix) .. "\\begin{pmatrix}")
            if name == "array" then          -- the column specification
              local _, _, after1 = argument(tex, e)
              e = after1
            end
          else
            emit("\\end{pmatrix}")
          end
          i = e
        else
          emit(tex:sub(i, j - 1))
          i = j
        end
      else
        emit(tex:sub(i, j - 1))
        i = j
      end
    end
  end
  close_bars(0)
  return table.concat(out)
end

-- ------------------------------------------------------------------ Typst, after the conversion

-- Typst reads the Typst code the writer produced differently from the way TeX reads the source in three
-- respects, all fixed here on the token level:
--   * a bare string is text, not an operator name: \operatorname{Tr}(ρ) comes out as "Tr" \( rho \) and is
--     set "Tr (ρ)". An operator name is op("Tr");
--   * white space in the source is kept next to text and next to bars ("spaced" fragments), so every token
--     the writer separates with a blank gets a visible space there: | ψ⟩, | x |², "if  x". TeX ignores
--     blanks in math; here the bars get an explicit class and the blanks next to text become comments;
--   * explicit space replaces the automatic space between the atoms next to it instead of adding to it:
--     a \;=\; b would be set like a = b, and ", \quad x" would lose the thin space after the comma. A space
--     is therefore written as an empty box of that width, which leaves the automatic spacing alone;
--   * the markers and codes M.tex left behind are turned into Typst.

local function pattern(name)
  -- %f[%w.]: not preceded by a letter, digit or dot (so x.sect and intersect stay); %f[^%w]: a whole name
  return "%f[%w.]" .. name:gsub("%.", "%%.") .. "%f[^%w]"
end

-- The width M.tex encoded, as Typst writes it ("#h(5005em)"), turned into the real width.
local function decode_space(code)
  local v = tonumber(code)
  if not v or v <= SPACE_BASE - SPACE_SPAN or v >= SPACE_BASE + SPACE_SPAN then return nil end
  local em = string.format("%.4f", (v - SPACE_BASE) / 18):gsub("0+$", ""):gsub("%.$", "")
  return "#h(" .. em .. "em)"
end

-- The index after the bracket group opening at code[i] (open/close are single characters); strings and
-- escaped characters inside are skipped.
local function balanced(code, i, open, close)
  local depth, n = 0, #code
  while i <= n do
    local c = code:sub(i, i)
    if c == "\\" then
      i = i + 2
    elseif c == '"' then
      i = i + 1
      while i <= n and code:sub(i, i) ~= '"' do
        if code:sub(i, i) == "\\" then i = i + 1 end
        i = i + 1
      end
      i = i + 1
    else
      if c == open then
        depth = depth + 1
      elseif c == close then
        depth = depth - 1
        if depth == 0 then return i + 1 end
      end
      i = i + 1
    end
  end
  return n + 1
end

-- Typst math code as tokens { kind, text }: ws (blanks), br ("\" before a blank: a line break), str ("…"),
-- esc (\x), code (#…(…)[…]), name (a.b.c) and char (any other single character).
local function lex(code)
  local tokens, i, n = {}, 1, #code
  local function push(kind, j)
    tokens[#tokens + 1] = { kind = kind, text = code:sub(i, j - 1) }
    i = j
  end
  while i <= n do
    local c = code:sub(i, i)
    if c:match("%s") then
      push("ws", code:match("^%s+()", i))
    elseif c == '"' then
      local j = i + 1
      while j <= n and code:sub(j, j) ~= '"' do
        if code:sub(j, j) == "\\" then j = j + 1 end
        j = j + 1
      end
      push("str", math.min(j, n) + 1)
    elseif c == "\\" then
      local after = code:sub(i + 1, i + 1)
      if after == "" or after:match("%s") then
        push("br", code:match("^%s*()", i + 1))
      else
        push("esc", utf8.offset(code, 2, i + 1) or n + 1)
      end
    elseif c == "#" then
      local j = code:match("^#[%a_][%w_%-]*()", i)
      if not j then
        push("char", i + 1)
      else
        while code:sub(j, j) == "." and code:sub(j + 1, j + 1):match("[%a_]") do
          j = code:match("^%.[%a_][%w_%-]*()", j)
        end
        if code:sub(j, j) == "(" then j = balanced(code, j, "(", ")") end
        if code:sub(j, j) == "[" then j = balanced(code, j, "[", "]") end
        push("code", j)
      end
    elseif c:match("%a") then
      local j = code:match("^%a%w*()", i)
      while code:sub(j, j) == "." and code:sub(j + 1, j + 1):match("%a") do
        j = code:match("^%.%a%w*()", j)
      end
      push("name", j)
    else
      push("char", utf8.offset(code, 2, i) or n + 1)
    end
  end
  return tokens
end

-- Functions whose string argument is text to keep as written, and those among them that set running text.
local KEEP_STRING = {
  upright = true, bold = true, italic = true, mono = true, sans = true, serif = true, frak = true, bb = true,
  cal = true, text = true, op = true, class = true, display = true, inline = true, script = true,
  sscript = true,
}
local TEXT_STYLE = { upright = true, bold = true, italic = true, mono = true, sans = true, serif = true }
-- Bars: Typst gives them the class "fence", which keeps the blanks of the source around them.
local BARS = { ["bar.v"] = true, ["bar.v.double"] = true, ["bar.v.triple"] = true }
-- Inside these a bar is an argument and already has its role.
local BAR_ROLE = { mid = true, class = true, stretch = true }
-- Spaces as the writer names them, in 18ths of an em.
local SPACE_NAMES = { thin = 3, med = 4, thick = 5, quad = 18, wide = 36 }
-- Signs that are binary after an operand and unary otherwise.
local SIGNS = { ["+"] = true, ["-"] = true, ["plus.minus"] = true, ["minus.plus"] = true }
-- What cannot end an operand: after these a sign is unary. Characters and escapes as the writer spells them,
-- and the first component of symbol names (relations, binary and large operators, named operators).
local NOT_OPERAND = {}
for c in ("= < > + - * / , ; : ( [ { & \\, \\; \\: \\( \\[ \\{ \\/"):gmatch("%S+") do NOT_OPERAND[c] = true end
local NOT_OPERAND_HEAD, OPERATOR, RELATION = {}, {}, {}
for name in ([[
  eq lt gt approx equiv tilde arrow arrows harpoon harpoons tack in subset supset prec succ prop parallel perp
  divides colon models forces asymp therefore because
]]):gmatch("%S+") do NOT_OPERAND_HEAD[name], RELATION[name] = true, true end
for name in ([[
  plus minus times div dot ast star union inter and or xor compose convolve without
]]):gmatch("%S+") do NOT_OPERAND_HEAD[name] = true end
for name in ([[
  sum product integral
  sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth exp log ln lg det dim ker hom deg gcd lcm
  max min sup inf lim limsup liminf arg Pr mod
]]):gmatch("%S+") do NOT_OPERAND_HEAD[name], OPERATOR[name] = true, true end
local OPERAND_CLASS = { normal = true, closing = true, fence = true, alphabetic = true }

-- Delimiters as the writer spells them, by name: as an argument of stretch() a bare bracket would be read as
-- an unclosed group.
local DELIMITER = {
  ["\\("] = "paren.l", ["\\)"] = "paren.r", ["\\["] = "bracket.l", ["\\]"] = "bracket.r",
  ["("] = "paren.l", [")"] = "paren.r", ["["] = "bracket.l", ["]"] = "bracket.r",
  ["{"] = "brace.l", ["}"] = "brace.r", ["\\{"] = "brace.l", ["\\}"] = "brace.r",
  ["|"] = "bar.v", ["\\|"] = "bar.v", ["/"] = "slash", ["\\/"] = "slash",
  [MARK_OPEN_BAR] = "bar.v", [MARK_CLOSE_BAR] = "bar.v",
}

-- Typst math code as the writer produced it, with the fixes described above and at the head of this file.
function M.rename(code)
  local t = lex(code)
  local n = #t
  local function next_solid(k)               -- the next token that is not blank
    k = k + 1
    while k <= n and t[k].kind == "ws" do k = k + 1 end
    return k <= n and k or nil
  end
  local function prev_solid(k)
    k = k - 1
    while k >= 1 and t[k].kind == "ws" do k = k - 1 end
    return k >= 1 and k or nil
  end
  -- Brackets: for every token the function call it sits in, and for "(" and ")" their partners.
  local stack = {}
  for k = 1, n do
    local tok = t[k]
    tok.out = tok.out or tok.text
    tok.call = stack[#stack]
    if tok.kind == "char" and tok.text == "(" then
      local name = k > 1 and t[k - 1].kind == "name" and t[k - 1].text or false
      -- A carrier M.tex put around a group: overline(…) after a group marker is that group's call.
      local m = name == "overline" and prev_solid(k - 1)
      local kind = m and t[m].kind == "char" and GROUPS[utf8.codepoint(t[m].text) - MARK_GROUP]
      if kind then
        name = kind[1]
        t[k - 1].out, t[k - 1].carrier = name, true
        tok.out = kind[2] and "(" .. kind[2] .. ", " or "("
        t[m].out = ""
        for w = m + 1, k - 2 do t[w].out = "" end
      end
      stack[#stack + 1] = { name = name, open = k, fraction = kind and (name == "frac" or kind[3]) or nil }
    elseif tok.kind == "char" and tok.text == ")" and #stack > 0 then
      local call = table.remove(stack)
      call.close = k
      tok.call = stack[#stack]
      tok.closes = call
      t[call.open].group = call
      if call.fraction then
        -- The carrier of a fraction holds "a / b" (the slash becomes the comma of frac(a, b)) or, for
        -- longer operands, frac(a, b) itself.
        local slash
        for a = call.open + 1, k - 1 do
          if t[a].kind == "char" and t[a].text == "/" and t[a].call == call then slash = a end
        end
        if slash then
          t[slash].out = ","
          if call.name ~= "frac" then
            t[call.open - 1].out, tok.out = call.name .. "(frac", "))"
          end
        elseif call.name == "frac" then
          t[call.open - 1].out, t[call.open].out, tok.out = "", "", ""
          call.name = false
        end
      end
    end
  end
  -- Whether the token at k is the first or the last thing inside lr(…): a delimiter lr sizes.
  local function lr_delimiter(k)
    local call = t[k].call
    return call and call.name == "lr" and call.close
      and (prev_solid(k) == call.open or next_solid(k) == call.close) or false
  end
  local text_spans = {}                      -- { first, last }: what is laid out as a frame (see below)
  for k = 1, n do
    local tok = t[k]
    if tok.carrier then
      -- the renamed carrier of a group: nothing else applies
    elseif tok.kind == "name" then
      for _, r in ipairs(M.RENAMES) do
        tok.out = tok.out:gsub(pattern(r[1]), r[2])
      end
      local open = t[k + 1]
      if BARS[tok.text] then
        if not lr_delimiter(k) and not (tok.call and BAR_ROLE[tok.call.name]) then
          tok.out = 'class("normal", ' .. tok.out .. ")"
        end
      elseif tok.text == "sans" and open and open.group and open.group.close then
        -- \mathsf is upright; Typst's sans keeps single letters italic.
        tok.out = "upright(sans"
        t[open.group.close].out = "))"
      elseif tok.text == "mid" and open and open.group and open.group.close then
        -- \middle| has no space around it in TeX; Typst spaces mid() like a relation.
        tok.out = 'class("normal", mid'
        t[open.group.close].out = "))"
      end
    elseif tok.kind == "code" and not tok.text:find("^#h%(") then
      -- texmath puts fixed-size delimiters in scale's markup body. Named symbols there are literal text
      -- unless explicitly interpolated (chevron.l, ceil.l, ...).
      tok.out = tok.out:gsub("(#scale%b())%[([%a][%w%.]*)%]", "%1[#sym.%2]")
      text_spans[#text_spans + 1] = { k, k }  -- #box(…), #hide[…], #scale(…)[…]
    elseif tok.kind == "code" then
      -- texmath puts fixed-size delimiters in scale's markup body. Named symbols there are literal text
      -- unless explicitly interpolated (chevron.l, ceil.l, ...).
      tok.out = tok.out:gsub("(#scale%b())%[([%a][%w%.]*)%]", "%1[#sym.%2]")
      tok.out = tok.out:gsub("^#h%((%d+)em%)$", decode_space)
    elseif tok.kind == "esc" and tok.text == "\\|" then
      tok.out = lr_delimiter(k) and "bar.v" or 'class("normal", bar.v)'
    elseif tok.kind == "char" and tok.text == "&" and tok.call and tok.call.name == "cases" then
      tok.out = "& quad "                    -- TeX separates the two columns of cases by a quad
    elseif tok.kind == "char" and SYMBOLS[utf8.codepoint(tok.text) - MARK_SYMBOL] then
      tok.out = SYMBOLS[utf8.codepoint(tok.text) - MARK_SYMBOL][2]
    elseif tok.kind == "char" and tok.text == MARK_OPEN_BAR then
      tok.out = lr_delimiter(k) and "bar.v" or 'class("opening", bar.v)'
    elseif tok.kind == "char" and tok.text == MARK_CLOSE_BAR then
      tok.out = lr_delimiter(k) and "bar.v" or 'class("closing", bar.v)'
    elseif tok.kind == "str" then
      local p = prev_solid(k)
      local call = tok.call
      if tok.text == '""' then
        text_spans[#text_spans + 1] = { k, k }  -- the empty base of {}^a: no operator, and no blanks
      elseif p and t[p].kind == "char" and t[p].text == ":" then
        -- a named argument (mat(delim: "(", …)): leave
      elseif call and call.name and KEEP_STRING[call.name] and p == call.open then
        if TEXT_STYLE[call.name] and call.close then
          text_spans[#text_spans + 1] = { call.open - 1, call.close }
        end
      else
        tok.out = "op(" .. tok.text .. ")"
        tok.operator = true
      end
    end
  end
  -- A relation with a subscript or superscript: Typst sets the script below or above it, as for a limit
  -- (E →_L E with the L under the arrow); TeX sets it beside. Not for \\xrightarrow, whose label belongs there.
  for k = 1, n - 1 do
    local tok, after = t[k], t[k + 1]
    if after.kind == "char" and (after.text == "_" or after.text == "^") and not tok.carrier then
      local symbol = tok.kind == "char" and SYMBOLS[utf8.codepoint(tok.text) - MARK_SYMBOL]
      local name = tok.kind == "name" and tok.text or symbol and symbol[2]
      local relation = name and RELATION[name:match("^%a+")] and not (tok.call and BAR_ROLE[tok.call.name])
        or tok.kind == "char" and (tok.text == "=" or tok.text == "<" or tok.text == ">")
      local p = prev_solid(k)
      local stretched = p and t[p].kind == "char" and utf8.codepoint(t[p].text) == MARK_TOKEN + TOKEN.stretch
      if relation and not stretched then tok.out = "scripts(" .. tok.out .. ")" end
    end
  end
  -- Markers that govern the token after them.
  for k = 1, n do
    local tok = t[k]
    local cp = tok.kind == "char" and utf8.codepoint(tok.text) or 0
    if tok.kind == "char" and tok.text == MARK_LIMITS then
      local d = next_solid(k)
      tok.out = ""
      if t[k + 1] and t[k + 1].kind == "ws" and d then t[k + 1].out = "" end
      if d and t[d].kind == "str" then
        t[d].out = "op(" .. t[d].text .. ", limits: #true)"
      end
    elseif cp >= MARK_BIG and cp < MARK_BIG + 16 then
      local size, side = (cp - MARK_BIG) // 4, (cp - MARK_BIG) % 4
      local d = next_solid(k)
      tok.out = ""
      if t[k + 1] and t[k + 1].kind == "ws" and d then t[k + 1].out = "" end
      if d then
        local delimiter = t[d]
        local glyph = DELIMITER[delimiter.text]
        if not glyph and delimiter.kind == "name" then
          glyph = delimiter.text
          for _, r in ipairs(M.RENAMES) do glyph = glyph:gsub(pattern(r[1]), r[2]) end
        end
        if delimiter.kind == "char" and delimiter.text == "." then
          delimiter.out = ""                 -- \bigl. : the empty delimiter
        elseif glyph then
          delimiter.out = string.format('class("%s", stretch(%s, size: #%d%%))',
            BIG_CLASS[side], glyph, BIG_PERCENT[size])
        end
      end
    elseif cp > MARK_TOKEN and cp <= MARK_TOKEN + 16 then
      local kind = cp - MARK_TOKEN
      local d = next_solid(k)
      tok.out = ""
      if t[k + 1] and t[k + 1].kind == "ws" and d then t[k + 1].out = "" end
      local call = d and t[d + 1] and t[d + 1].group
      local p = prev_solid(k)
      if kind == TOKEN.limits or kind == TOKEN.nolimits then
        -- \\sum\\nolimits_a^b: the scripts hang on the marker; the operator before it moves into its place.
        if p and (t[p].kind == "name" or t[p].kind == "str") then
          tok.out = (kind == TOKEN.limits and "limits(" or "scripts(") .. t[p].out .. ")"
          for w = p, k - 1 do t[w].out = "" end
        end
      elseif d and kind == TOKEN.stretch and t[d].kind == "name" then
        t[d].out = "stretch(" .. t[d].out .. ")"   -- \xrightarrow{f}: arrow.r^f
      elseif MATRIX_DELIMITER[kind] and call and call.close and t[d].text == "mat" then
        -- The delimiter is the string after "delim:".
        for a = call.open + 1, call.close - 1 do
          local p = t[a].kind == "str" and t[a].call == call and prev_solid(a)
          if p and t[p].text == ":" then
            t[a].out = MATRIX_DELIMITER[kind]
            break
          end
        end
        if kind == TOKEN.smallmatrix then
          t[d].out = "script(mat"
          t[call.close].out = "))"
        end
      end
    end
  end
  -- Explicit spaces. TeX adds them to the automatic space between the atoms on either side; Typst drops the
  -- automatic space next to h(). An empty box of the same width is an ordinary atom that leaves the spacing
  -- of its neighbours alone.
  local function width_of(tok)               -- of a space, in 18ths of an em
    if tok.kind == "name" then return SPACE_NAMES[tok.text] end
    if tok.kind == "code" then
      local em = tok.out:match("^#h%((%-?[%d%.]+)em%)$")
      return em and tonumber(em) * 18
    end
    return nil
  end
  local function atom_before(k)              -- the token before k that is neither blank nor a space
    local p = prev_solid(k)
    while p and width_of(t[p]) do p = prev_solid(p) end
    return p
  end
  local function atom_after(k)
    local q = next_solid(k)
    while q and width_of(t[q]) do q = next_solid(q) end
    return q
  end
  -- The class of the call a token belongs to when it is the name of class(...) or the ")" that closes it.
  local function call_class(call)
    if not call or call.name ~= "class" then return nil end
    local first = next_solid(call.open)
    return first and t[first].kind == "str" and t[first].text:sub(2, -2) or nil
  end
  -- Whether the token at p ends an operand (so that a sign after it is binary).
  local function ends_operand(p)
    if not p then return false end
    local tok = t[p]
    if tok.kind == "br" or tok.text == "$" or tok.text == MARK_OPEN_BAR or tok.operator then return false end
    if tok.kind == "char" and tok.text == ")" and tok.closes then
      local call = tok.closes
      if call.name == "op" then return false end
      local class = call_class(call)
      if class then return OPERAND_CLASS[class] or false end
      return true
    end
    if tok.kind == "char" or tok.kind == "esc" then return not NOT_OPERAND[tok.text] end
    if tok.kind == "name" then
      if tok.text:find("%.l%f[%W]") then return false end   -- an opening delimiter: paren.l, chevron.l.double
      return not NOT_OPERAND_HEAD[tok.text:match("^%a+")]
    end
    return true
  end
  -- Whether the token at q opens a delimited group, and whether p ends a large or named operator.
  local function opens(q)
    if not q then return false end
    local tok = t[q]
    if tok.text == "\\(" or tok.text == "\\[" or tok.text == "(" or tok.text == "[" or tok.text == "{"
      or tok.text == MARK_OPEN_BAR or tok.text == "lr" then
      return true
    end
    if tok.kind == "name" and tok.text == "class" then
      local open = next_solid(q)
      return open ~= nil and t[open].group ~= nil and call_class(t[open].group) == "opening"
    end
    return tok.kind == "name" and tok.text:find("%.l%f[%W]") ~= nil
  end
  local function ends_operator(p)
    if not p then return false end
    local tok = t[p]
    if tok.kind == "char" and tok.text == ")" and tok.closes then
      return tok.closes.name == "op" or call_class(tok.closes) == "large"
    end
    return tok.operator or (tok.kind == "name" and OPERATOR[tok.text]) or false
  end
  local function em(width)
    return (string.format("%.4f", width / 18):gsub("0+$", ""):gsub("%.$", ""))
  end
  for k = 1, n do
    local tok = t[k]
    local width = (not tok.call or tok.call.name ~= "class") and width_of(tok) or nil
    if width and width > 0 then
      local p, q = atom_before(k), atom_after(k)
      if ends_operator(p) and opens(q) then
        -- TeX sets nothing between an operator and an opening delimiter; h() does the same, a box would not.
        tok.out = "#h(" .. em(width) .. "em)"
      else
        tok.out = "#box(width: " .. em(width) .. "em)"
        -- A box takes the blanks of the source as word spaces; a comment separates tokens without one.
        if k > 2 and t[k - 1].kind == "ws" and t[k - 2].text ~= "$" and t[k - 2].kind ~= "br" then
          t[k - 1].out = "/**/"
        end
        if k + 2 <= n and t[k + 1].kind == "ws" and t[k + 2].text ~= "$" then
          t[k + 1].out = "/**/"
        elseif t[k + 1] and t[k + 1].kind ~= "ws" then
          tok.out = tok.out .. "/**/"         -- or a bracket after it would become its argument
        end
        -- After a box (an ordinary atom) Typst takes a sign for a binary operator.
        if q and SIGNS[t[q].text] and not t[q].signed and not ends_operand(p) then
          t[q].signed = true
          t[q].out = 'class("unary", ' .. t[q].out .. ")"
        end
      end
    elseif width and width < 0 then
      -- TeX puts a thin space before \left(…\right) that authors cancel with \!; Typst has no such space.
      local q = next_solid(k)
      local left = q and ((t[q].kind == "name" and t[q].text == "lr")
        or (t[q].kind == "char" and (t[q].text == "(" or t[q].text == "[")))
      if math.floor(width + 0.5) == -3 and left then
        tok.out = ""
        if t[k + 1] and t[k + 1].kind == "ws" then t[k + 1].out = "" end
      end
    end
  end
  -- Blanks next to running text would be set as spaces; a comment separates the tokens without one.
  for _, span in ipairs(text_spans) do
    local first, last = span[1], span[2]
    -- a style around a style (bold(upright("x"))) is one piece of text
    while first > 2 and last < n and t[first - 1].kind == "char" and t[first - 1].text == "("
      and t[first - 2].kind == "name" and TEXT_STYLE[t[first - 2].text]
      and t[last + 1].kind == "char" and t[last + 1].text == ")" do
      first, last = first - 2, last + 1
    end
    local before, after = t[first - 1], t[last + 1]
    if before and before.kind == "ws" and first > 2 and t[first - 2].text ~= "$" and t[first - 2].kind ~= "br" then
      before.out = "/**/"
    end
    if after and after.kind == "ws" and last + 2 <= n and t[last + 2].text ~= "$" then
      after.out = "/**/"
    end
  end
  -- A replacement that starts with a name must not run into a name before it (w\| → w class(…)).
  local out, last = {}, ""
  for k = 1, n do
    local piece = t[k].out
    if piece ~= "" then
      if last:find("[%w.]$") and piece:find("^%a") and piece ~= t[k].text then out[#out + 1] = " " end
      out[#out + 1] = piece
      last = piece
    end
  end
  return table.concat(out)
end

local function write(el)
  local typ = pandoc.write(pandoc.Pandoc({ pandoc.Plain({ el }) }), "typst", { wrap_text = "wrap-none" })
  return (typ:gsub("%s+$", ""))
end

-- A Math element written as Typst with the fixes above; nil (keep the element) when it needs none.
function M.math(el)
  local tex = M.tex(el.text, el.mathtype == "DisplayMath")
  local source = tex == el.text and el or pandoc.Math(el.mathtype, tex)
  local typ = write(source)
  -- A formula the writer cannot convert comes back as escaped TeX source ("\$…\$"), not as math. When the
  -- rewritten TeX is the reason, or the formula does not convert either way, keep what the author wrote.
  if source ~= el and typ:sub(1, 1) ~= "$" then
    source, typ = el, write(el)
  end
  if typ:sub(1, 1) ~= "$" then return nil end
  local fixed = M.rename(typ)
  if fixed == typ and source == el then return nil end
  return pandoc.RawInline("typst", fixed)
end

-- `inlines` with every formula that needs a fix replaced by raw Typst.
function M.inlines(inlines)
  return pandoc.Inlines(inlines):walk({ Math = M.math })
end

return M
