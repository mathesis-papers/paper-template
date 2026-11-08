--[[
tr-book.lua — book-level structure for the trureturing Pandoc pipeline (PDF and EPUB).

Run before tr-env.lua. tools/tbook/pandoc.py stages every chapter into one book.md and
marks each chapter title heading with `.tr-chapter` plus key-value attributes
(tr-section = prefix|numbered|suffix|back, tr-depth, tr-kicker); part titles from
SUMMARY.md become `# Part {.tr-part}` headings. This filter:

* every format — turns internal links `#id` whose target does not exist into plain text
  (with a warning on stderr), so a dangling anchor never breaks Typst compilation
  or EPUB validation;
* typst — replaces chapter and part headings with calls of `tr-chapter` / `tr-part`
  (theme/typst/book.typ draws the openers and keeps a real `heading` for the outline
  and running headers); replaces images Typst cannot load (remote URLs, missing files)
  with a link or their description; gives the verification-ledger tables fixed column
  widths; adds line-break opportunities to long inline code (Lean names);
  renders `.tr-media` divs as framed media panels;
* html / epub — marks media divs as figures for the stylesheet (theme/epub/book.css).
]]

local stringify = pandoc.utils.stringify

local function warn(msg)
  io.stderr:write("[tr-book] " .. msg .. "\n")
end

local function is_typst() return FORMAT == "typst" end

local function typst_str(s)
  s = tostring(s or "")
  s = s:gsub("\\", "\\\\")
  s = s:gsub('"', '\\"')
  s = s:gsub("\r?\n", " ")
  return '"' .. s .. '"'
end

local function typst_content(inlines)
  local out = pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), "typst")
  out = out:gsub("%s+$", "")
  return "[" .. out .. "]"
end

local function file_exists(path)
  local fh = io.open(path, "rb")
  if fh then fh:close() return true end
  return false
end

local function url_decode(s)
  return (s:gsub("%%(%x%x)", function(h) return string.char(tonumber(h, 16)) end))
end

-- ------------------------------------------------------------------ identifiers

local function collect_ids(doc)
  local ids = {}
  local function add(el)
    if el.identifier and el.identifier ~= "" then ids[el.identifier] = true end
  end
  doc:walk({
    Header = add, Div = add, Span = add, Figure = add, Table = add, CodeBlock = add,
    Code = add, Image = add, Link = add,
  })
  -- Raw HTML/Typst anchors written by other components (id="…" / <label>).
  doc:walk({
    RawBlock = function(raw)
      for id in raw.text:gmatch('id="([^"]+)"') do ids[id] = true end
    end,
    RawInline = function(raw)
      for id in raw.text:gmatch('id="([^"]+)"') do ids[id] = true end
    end,
  })
  return ids
end

local function fix_links(doc, ids)
  return doc:walk({
    Link = function(link)
      local t = link.target
      if t:sub(1, 1) == "#" then
        local id = url_decode(t:sub(2))
        if id == "" or not ids[id] then
          warn("dangling internal link " .. t .. " (" .. stringify(link.content) .. ") rendered as text")
          return pandoc.Span(link.content, pandoc.Attr("", { "tr-dangling" }))
        end
      end
      return nil
    end,
  })
end

-- ------------------------------------------------------------------ Typst

local function typst_heading_call(fn, h)
  local a = h.attributes
  local outlined = not h.classes:includes("unlisted")
  local args = {
    "id: " .. typst_str(h.identifier),
    "kicker: " .. typst_str(a["tr-kicker"] or ""),
    "section: " .. typst_str(a["tr-section"] or ""),
    "outlined: " .. (outlined and "true" or "false"),
    "title: " .. typst_content(h.content),
  }
  return pandoc.RawBlock("typst", "#" .. fn .. "(" .. table.concat(args, ", ") .. ")")
end

local function typst_header(h)
  if h.level == 1 and h.classes:includes("tr-part") then
    return typst_heading_call("tr-part", h)
  end
  if h.level == 1 and h.classes:includes("tr-chapter") then
    return typst_heading_call("tr-chapter", h)
  end
  return nil
end

local function typst_image(img)
  local src = img.src
  if src:match("^[%a][%w+.-]*:") and not src:match("^file:") then
    warn("remote image " .. src .. " cannot be embedded in the PDF; linked instead")
    local text = #img.caption > 0 and img.caption or pandoc.Inlines({ pandoc.Str(src) })
    return pandoc.Link(text, src)
  end
  local path = url_decode((src:gsub("^file://", "")))
  if not file_exists(path) then
    warn("image not found: " .. src .. "; replaced by its description")
    local text = #img.caption > 0 and img.caption or pandoc.Inlines({ pandoc.Str(src) })
    return pandoc.Emph(text)
  end
  return nil
end

-- Long inline code (Lean declaration names) gets break opportunities after dots/slashes.
local function typst_code(code)
  if #code.text >= 24 and code.text:match("[%./]") and not code.text:match("%s") then
    return pandoc.RawInline("typst", "#tr-code-break(" .. typst_str(code.text) .. ")")
  end
  return nil
end

local LEDGER_WIDTHS = { 0.16, 0.30, 0.36, 0.18 }

local function ledger_table(tbl)
  if #tbl.colspecs ~= #LEDGER_WIDTHS then return tbl end
  for i, spec in ipairs(tbl.colspecs) do
    tbl.colspecs[i] = { spec[1], LEDGER_WIDTHS[i] }
  end
  return tbl
end

local function media_block(div)
  local kind = "media"
  for _, c in ipairs({ "viz", "film", "slides" }) do
    if div.classes:includes("tr-" .. c) or div.classes:includes(c) then kind = c end
  end
  local out = pandoc.Blocks({ pandoc.RawBlock("typst", "#tr-media(kind: " .. typst_str(kind) .. ")[") })
  out:extend(div.content)
  out:insert(pandoc.RawBlock("typst", "]" .. (div.identifier ~= "" and (" <" .. div.identifier .. ">") or "")))
  return out
end

-- ------------------------------------------------------------------ HTML / EPUB

local function html_escape(s)
  return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
end

-- Long inline code (Lean names) gets <wbr/> after dots and slashes instead of breaking
-- anywhere, so ledger columns wrap at name boundaries.
local function html_code(code)
  if #code.text >= 24 and code.text:match("[%./]") and not code.text:match("%s")
      and code.identifier == "" and #code.classes == 0 then
    local body = html_escape(code.text):gsub("([%./])", "%1<wbr/>")
    return pandoc.RawInline("html", "<code>" .. body .. "</code>")
  end
  return nil
end

-- ------------------------------------------------------------------ filter

function Pandoc(doc)
  local ids = collect_ids(doc)
  doc = fix_links(doc, ids)

  if is_typst() then
    -- Ledger tables: top-level blocks between a `.tr-ledger` heading and the next chapter.
    local in_ledger = false
    for i, blk in ipairs(doc.blocks) do
      if blk.t == "Header" and blk.level == 1 then
        in_ledger = blk.classes:includes("tr-ledger")
      elseif in_ledger and blk.t == "Table" then
        doc.blocks[i] = ledger_table(blk)
      elseif in_ledger and blk.t == "Figure" and blk.content[1] and blk.content[1].t == "Table" then
        blk.content[1] = ledger_table(blk.content[1])
      end
    end
    doc = doc:walk({
      Image = typst_image,
      Code = typst_code,
      Div = function(div)
        if div.classes:includes("tr-media") then return media_block(div) end
        return nil
      end,
    })
    doc = doc:walk({ Header = typst_header })
  else
    doc = doc:walk({
      Code = html_code,
      Div = function(div)
        if div.classes:includes("tr-media") and not div.classes:includes("section") then
          div.classes:insert(1, "section")
          return div
        end
        return nil
      end,
    })
  end
  return doc
end
