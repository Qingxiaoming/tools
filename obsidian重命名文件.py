import os
import re

# 匹配：开头若干个 #，接着 YYYY/M/D，后面可有可无空格+星期
DATE_PATTERN = re.compile(r'^#+\s*(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+\w+)?\s*$')

def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()

def build_new_name(first_line: str) -> str | None:
    m = DATE_PATTERN.match(first_line.strip())
    if m:
        y, m, d = map(int, m.groups())
        return f'{y:04d}-{m:02d}-{d:02d}'
    cleaned = sanitize(first_line)
    return cleaned if cleaned else None

def main():
    for old in os.listdir('.'):
        if not os.path.isfile(old) or not re.search(r'\d', old):
            continue
        try:
            with open(old, 'r', encoding='utf-8') as f:
                first = f.readline()
        except Exception as e:
            print(f'读取失败 {old}: {e}')
            continue

        new_base = build_new_name(first)
        if new_base is None:
            print(f'跳过（无效首行）{old}')
            continue

        _, ext = os.path.splitext(old)
        new_name = new_base + ext
        counter = 1
        while os.path.exists(new_name):
            new_name = f'{new_base}_{counter}{ext}'
            counter += 1

        try:
            os.rename(old, new_name)
            print(f'{old}  ->  {new_name}')
        except Exception as e:
            print(f'重命名失败 {old}: {e}')

if __name__ == '__main__':
    main()
