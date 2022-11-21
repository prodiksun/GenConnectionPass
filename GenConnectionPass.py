# Возможно потребуется установить pip install paramiko scp

import platform
import subprocess
from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient
from contextlib import contextmanager


# Берем ip адрес из списка и пробуем пинговать, если пинг идет, то записываем в файл file_ipaddr_avail, если нет, то в file_ipaddr_unavail (с дописыванием на следующую строку)
@contextmanager
def ping(ipaddr):
    global ip_status
    if platform.system().lower() == 'windows':
        command = ['ping', '-n', str(1), '-w', str(1000), ipaddr]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        if b'TTL=' in result.stdout:
            ip_status = 1
            print("Хост доступен:", ipaddr)
            # with open(file_ipaddr_avail, 'w') as f:
            #     f.write(ipaddr)
        else:
            print("\033[31m{}".format("Хост недоступен:"), "\033[0m{}".format(ipaddr))
            with open(file_ipaddr_unavail, 'a') as f:
                f.write(ipaddr + '\n')
            ip_status = 0
        return result.returncode == 0 and b'TTL=' in result.stdout
    else:
        command = ['ping', '-c', str(1), '-w', str(1000), ipaddr]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if b'TTL=' in result.stdout:
            print("Хост доступен:", ipaddr)
            ip_status = 1
        else:
            print("\033[31m{}".format("Хост недоступен:"), "\033[0m{}".format(ipaddr))
            ip_status = 0        
        return result.returncode == 0
        

# Функция подключения к хостам через ssh
@contextmanager
def ssh_connection(ipaddr, sshpass, cmd_line):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(hostname=ipaddr, username=user, password=sshpass, port=port)
    stdin, stdout, stderr = ssh.exec_command(cmd_line)
    #print(stdin, stdout, stderr)
    ssh.close()


# Копирование файла по scp
@contextmanager
def scp_connection(file_rsa, rem_path):
    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(hostname=ipaddr, username=user, password=sshpass, port=port)
    scp = SCPClient(ssh.get_transport())
    scp.put(file_rsa, recursive=True, remote_path=rem_path)
    ssh.close()


# Переменные
file_ipaddr = 'ipaddresses.csv'
file_ipaddr_avail = 'ip_avail.csv'
file_ipaddr_unavail = 'ip_unavail.csv'
file_no_access = 'no_access.csv'
user = 'root'
file_secret = 'ssh_pass.txt'
port = '22'
pass_accept = False
file_rsa = 'id_rsa.pub'
rem_path = '/tmp'
cmd_line = "cat /proc/sys/kernel/hostname"


# Подключаемся к файлам со списком ip адресов устройств и паролей и считываем его построчно
inv_ip = open(file_ipaddr, 'rt')
list_sshpass = open(file_secret, 'rt')


# Подключаемся по ssh к устойствам, которые доступны по пингу
for ipaddr in inv_ip:
    ipaddr = ipaddr.translate({ord(i): None for i in '\n'})
    ping(ipaddr)
    if ip_status == 1:
        for sshpass in list_sshpass:
            sshpass = sshpass.translate({ord(i): None for i in '\n'})
            try:
                cmd_line = "cat /proc/sys/kernel/hostname"
                #print(cmd_line)
                ssh_connection(ipaddr, sshpass, cmd_line)
                pass_accept = True
                print('Пароль подошел')
                with open(file_ipaddr_avail, 'a') as f:
                    f.write(ipaddr +  ';' + user + ';' + sshpass + '\n')
                break
            except Exception:
                pass_accept = False

        if pass_accept == True:
            try:
                scp_connection(file_rsa, rem_path)
                cmd_line = 'cd /etc/dropbear/ && ls && cat /tmp/id_*.pub >> authorized_keys && chmod 0600 authorized_keys'
                ssh_connection(ipaddr, sshpass, cmd_line)
                print('RSA ключ записан и установлен')
            except Exception:
                print('Ключ не установлен')
        else:
            with open(file_no_access, 'a') as f:
                    f.write(ipaddr + '\n')
            print("Пароли не подходят.")
