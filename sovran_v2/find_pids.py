import psutil, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        if p.info['name'] and 'python' in p.info['name'].lower():
            cmd = ' '.join(p.info['cmdline'] or [])
            print("PID", p.info['pid'], ":", cmd[:120])
    except Exception as e:
        pass
