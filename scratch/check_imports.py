fp = r'c:\Users\BAPS\OneDrive\Desktop\company-insights-hub-main\frontend\src\components\IBBICorporateProcess.tsx'
with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Skip the import block (lines 2-28) and check rest of file
body = ''.join(lines[28:])

icons_to_check = [
    'Download', 'ChevronRight', 'FileText', 'FileJson', 'Globe',
    'ExternalLink', 'Loader2', 'AlertTriangle', 'RefreshCw', 'Filter',
    'CheckCircle2', 'Plus', 'UserIcon', 'Landmark', 'MapPin', 'BadgeCheck',
    'ChevronLeft', 'ArrowRight', 'BarChart2', 'TableIcon', 'Info',
    'Trash2', 'LinkIcon', 'ArrowUp', 'LayoutList',
]

for icon in icons_to_check:
    used = icon in body
    print(f'  {"OK" if used else "UNUSED"}: {icon}')
