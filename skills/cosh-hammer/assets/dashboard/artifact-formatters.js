(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ArtifactFormatters = api;
})(typeof globalThis === "undefined" ? this : globalThis, function () {
  function parseMarkdown(source) {
    const lines = source.replace(/\r\n?/g, "\n").split("\n");
    const blocks = [];
    let index = 0;
    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        index += 1;
        continue;
      }
      if (index === 0 && line.trim() === "---") {
        const body = [];
        index += 1;
        while (index < lines.length && lines[index].trim() !== "---") {
          body.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) index += 1;
        blocks.push({ type: "frontmatter", text: body.join("\n") });
        continue;
      }
      const fence = line.match(/^\s*```\s*([^\s`]*)\s*$/);
      if (fence) {
        const body = [];
        index += 1;
        while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
          body.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) index += 1;
        blocks.push({ type: "code", language: fence[1] || "", text: body.join("\n") });
        continue;
      }
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        blocks.push({ type: "heading", level: heading[1].length, text: heading[2].trim() });
        index += 1;
        continue;
      }
      if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
        blocks.push({ type: "rule" });
        index += 1;
        continue;
      }
      if (/^\s*>\s?/.test(line)) {
        const quote = [];
        while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
          quote.push(lines[index].replace(/^\s*>\s?/, "").trim());
          index += 1;
        }
        blocks.push({ type: "quote", text: quote.join("\n") });
        continue;
      }
      if (
        line.includes("|") &&
        index + 1 < lines.length &&
        /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
      ) {
        const splitRow = value => value.trim().replace(/^\||\|$/g, "").split("|").map(cell => cell.trim());
        const headers = splitRow(line);
        const rows = [];
        index += 2;
        while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
          rows.push(splitRow(lines[index]));
          index += 1;
        }
        blocks.push({ type: "table", headers, rows });
        continue;
      }
      const listItem = line.match(/^\s*(?:(\d+)[.)]|[-+*])\s+(.+)$/);
      if (listItem) {
        const ordered = Boolean(listItem[1]);
        const items = [];
        while (index < lines.length) {
          const match = lines[index].match(/^\s*(?:(\d+)[.)]|[-+*])\s+(.+)$/);
          if (!match || Boolean(match[1]) !== ordered) break;
          items.push(match[2].trim());
          index += 1;
        }
        blocks.push({ type: "list", ordered, items });
        continue;
      }
      const paragraph = [line.trim()];
      index += 1;
      while (index < lines.length && lines[index].trim()) {
        paragraph.push(lines[index].trim());
        index += 1;
      }
      blocks.push({ type: "paragraph", text: paragraph.join(" ") });
    }
    return blocks;
  }

  function present(path, content) {
    const lower = path.toLowerCase();
    if (lower.endsWith(".json")) {
      try {
        return { kind: "json", value: JSON.parse(content), raw: content };
      } catch (_error) {
        return { kind: "text", content, raw: content };
      }
    }
    if (lower.endsWith(".md") || lower.endsWith(".markdown")) {
      return { kind: "markdown", blocks: parseMarkdown(content), raw: content };
    }
    return { kind: "text", content, raw: content };
  }

  function isBackdropClick(target, currentTarget) {
    return target === currentTarget;
  }

  return { isBackdropClick, parseMarkdown, present };
});
