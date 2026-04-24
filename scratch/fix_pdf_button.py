import re

fp = r'c:\Users\BAPS\OneDrive\Desktop\company-insights-hub-main\frontend\src\components\IBBICorporateProcess.tsx'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# Use regex to find and replace the whole blob-download button block
old_pattern = (
    r"\{/\* Download \u2014 blob download for PDF, open for others \*/\}\s+"
    r"<td className=\"p-2\.5 text-center\">\s+"
    r"\{isPdf \? \(\s+"
    r"<button\s+onClick=\{\(\) => downloadPdf\(href, doc\.fileName\)\}\s+"
    r"className=\{`inline-flex items-center gap-1\.5 px-3 py-1\.5 \$\{color\} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95 hover:opacity-90`\}\s+"
    r">\s+"
    r"<Download className=\"w-3 h-3\" />\s+"
    r"\{label\}\s+"
    r"</button>\s+"
    r"\) : \(\s+"
    r"<a\s+href=\{href\}\s+target=\"_blank\"\s+rel=\"noreferrer\"\s+"
    r"className=\{`inline-flex items-center gap-1\.5 px-3 py-1\.5 \$\{color\} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95`\}\s+"
    r">\s+\{icon\}\s+\{label\}\s+</a>\s+"
    r"\)\}\s+"
    r"</td>"
)

new_block = """{/* View \u2014 open in new tab for all file types */}
                                   <td className="p-2.5 text-center">
                                     {isPdf ? (
                                       <ViewPdfButton href={href} label="View PDF" size="xs" />
                                     ) : (
                                       <a
                                         href={href}
                                         target="_blank"
                                         rel="noreferrer"
                                         className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${color} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95`}
                                       >
                                         {icon}
                                         {label}
                                       </a>
                                     )}
                                   </td>"""

result, count = re.subn(old_pattern, new_block, content, flags=re.DOTALL)

if count > 0:
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"SUCCESS: Replaced {count} occurrence(s)")
else:
    # Fallback: simple line-by-line approach
    print("Regex failed, trying line-level replacement...")
    lines = content.split('\n')
    start_line = None
    end_line = None
    for i, line in enumerate(lines):
        if 'downloadPdf(href, doc.fileName)' in line:
            # Find the opening td before this
            for j in range(i, max(i-5, 0), -1):
                if '<td className="p-2.5 text-center">' in lines[j]:
                    start_line = j - 1  # include comment line before
                    break
            # Find the closing </td> after
            for j in range(i, min(i+20, len(lines))):
                if '</td>' in lines[j] and j > i:
                    end_line = j
                    break
            break

    if start_line is not None and end_line is not None:
        new_lines = [
            '                                   {/* View \u2014 open in new tab for all file types */}',
            '                                   <td className="p-2.5 text-center">',
            '                                     {isPdf ? (',
            '                                       <ViewPdfButton href={href} label="View PDF" size="xs" />',
            '                                     ) : (',
            '                                       <a',
            '                                         href={href}',
            '                                         target="_blank"',
            '                                         rel="noreferrer"',
            '                                         className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${color} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95`}',
            '                                       >',
            '                                         {icon}',
            '                                         {label}',
            '                                       </a>',
            '                                     )}',
            '                                   </td>',
        ]
        result_lines = lines[:start_line] + new_lines + lines[end_line+1:]
        with open(fp, 'w', encoding='utf-8') as f:
            f.write('\n'.join(result_lines))
        print(f"SUCCESS via line replacement: lines {start_line}-{end_line}")
    else:
        print("ERROR: Could not locate the block to replace")
