fp = r'c:\Users\BAPS\OneDrive\Desktop\company-insights-hub-main\frontend\src\components\IBBICorporateProcess.tsx'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

checks = {
    'downloadPdf still present': 'downloadPdf' in content,
    'ViewPdfButton in docs table': 'ViewPdfButton href={href}' in content,
    'ArrowUp in non-import': 'ArrowUp className' in content or '<ArrowUp' in content,
    'Download className still used': 'Download className' in content,
    'Total ViewPdfButton count': content.count('ViewPdfButton'),
}

for k, v in checks.items():
    print(f'{k}: {v}')
