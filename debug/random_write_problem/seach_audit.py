"""
pip install auditd_tools

References:
    https://github.com/jhb/auditd_tools
    https://github.com/matheuscpalermo/ausearch_parser/blob/main/ausearch_parser.py
    https://github.com/jhb/auditd_tools/issues/3
"""
import ubelt as ub


def append_attrs(attr_parts):
    attrs = {}
    for attribute in attr_parts:
        if '=' not in attribute or 'cmd' in attribute or 'proctitle' in attribute:
            break
        else:
            kvs = attribute.split('=')
            assert len(kvs) == 2
            key, value = kvs[0:2]
            attrs[key] = value
    return attrs


def parse_raw_log_part(raw_part):
    row = {}
    lines = raw_part.split('\n')
    row['timestamp'] = lines[0].split('msg=audit(')[1].split('.')[0]
    row['id'] = lines[0].split(':')[3].split(')')[0]
    row['type'] = lines[-1].split('=')[1].split()[0]
    row['pathlines'] = []
    row['execvelines'] = []
    row['cwdlines'] = []
    for line in lines:
        line = line.strip('\' ')
        if 'type=PATH' in line:
            row['pathlines'].append(line)
            continue
        elif 'type=CWD' in line:
            row['cwdlines'].append(line)
            continue
        elif 'type=EXECVE' in line:
            row['execvelines'].append(line)
            continue
        elif 'proctitle' in line:
            row['cmd'] = line.split('proctitle=')[1].strip()
            continue
        elif 'cmd' in line:
            row['cmd'] = line.split('cmd=')[1].split(' terminal')[0]

        attr_parts = line.split(' : ')[1].split(' ')
        row.update(append_attrs(attr_parts))
    return row


def v2():
    import ubelt as ub
    out = ub.cmd('sudo ausearch -m PATH -i', shell=True)
    # ub.util_import.PythonPathContext('/usr/lib/python3/dist-packages/')
    auparse = ub.import_module_from_path('/usr/lib/python3/dist-packages/auparse.cpython-312-x86_64-linux-gnu.so')

    from auditd_tools import event_parser
    p = event_parser.AuditdEventParser()
    lines = out['out'].split('\n')
    for line in lines:
        for e in p.parseline(line):
            print(e)


def v1():
    out = ub.cmd('sudo ausearch -m PATH -i', shell=True)
    parts = out['out'].split("\n----\n")
    parts[0] = parts[0].strip('----\n')
    parts[-1] = parts[-1].rstrip('\n')

    logs = []
    pathlines = []
    for raw_part in parts:
        row = parse_raw_log_part(raw_part)
        print('---')
        pathlines.extend(row['pathlines'])
        print(raw_part)
        print(f'row = {ub.urepr(row, nl=1)}')
        logs.append(row)

    print('\n'.join(pathlines))

    for row in logs:
        if row['TYPE'] == 'PATH':
            print(f'row = {ub.urepr(row, nl=1)}')


def main():
    out1 = ub.cmd('sudo ausearch -k misc_repo_watch -i', shell=True)
    out2 = ub.cmd('sudo ausearch -k local_repo_watch -i', shell=True)
    out3 = ub.cmd('sudo ausearch -k code_repos_watch -i', shell=True)

    lines1 = out1['out'].split('\n')
    lines2 = out2['out'].split('\n')
    lines3 = out3['out'].split('\n')
    lines = lines1 + lines2 + lines3

    for line in lines:
        if line.startswith('type=PATH'):
            suf = line.split(' item=', 1)[1]
            suf = suf.split(' ', 1)[1]
            if 'inode=' in suf:
                name = suf.split('inode=')[0].strip().split('name=', 1)[1]
            elif 'nametype=' in suf:
                name = suf.split('nametype=')[0].strip().split('name=', 1)[1]
            else:
                raise AssertionError

            if name == '(null)':
                continue

            # Look for strange chars in a name
            if set(name) & set('[]{}() '):
                raise Exception


if __name__ == '__main__':
    """
    CommandLine:
        python ~/misc/debug/random_write_problem/seach_audit.py
    """
    main()
