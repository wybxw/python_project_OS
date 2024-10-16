import click
import requests
import configparser
import os

API_URL = "http://localhost:5000"
CONFIG_FILE = "config.ini"

def get_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

@click.group()
def cli():
    """配送管理命令行工具"""
    pass

@click.command()
@click.option('-u', '--username', required=True, help='用户名')
@click.option('-pwd', '--password', required=True, help='密码')
def register(username, password):
    """注册新用户"""
    payload = {
        "username": username,
        "password": password
    }
    response = requests.post(f"{API_URL}/user/register", json=payload)
    if response.status_code == 201:
        click.echo("注册成功")
    else:
        click.echo(f"注册失败: {response.json().get('error', '未知错误')}")

@click.command()
@click.option('-u', '--username', required=True, help='用户名')
@click.option('-pwd', '--password', required=True, help='密码')
@click.option('-c', '--contact', required=False, help='联系方式')
def login(username, password,contact=''):
    """用户登录"""
    payload = {
        "username": username,
        "password": password,
        "contact": contact
    }
    response = requests.post(f"{API_URL}/user/login", json=payload)
    if response.status_code == 200:
        click.echo("登录成功")
        # 保存用户名到配置文件
        config = get_config()
        if 'user' not in config:
            config['user'] = {}
        config['user']['username'] = username
        save_config(config)
        response=requests.post(f"{API_URL}/notify/{username}")
        print(response.json().get('notification'))
    else:
        click.echo(f"登录失败: {response.json().get('error', '未知错误')}")

@click.command()
@click.option('-r', '--role', type=click.Choice(['user', 'courier'], case_sensitive=False), required=True, help='用户身份')
def set_role(role):
    """设置用户身份"""
    # 从配置文件中读取用户名
    config = get_config()
    if 'user' not in config or 'username' not in config['user']:
        click.echo("请先登录")
        return

    username = config['user']['username']
    payload = {
        "username": username,
        "role": role
    }
    response = requests.post(f"{API_URL}/user/set_role", json=payload)
    if response.status_code == 200:
        click.echo("身份设置成功")
    else:
        click.echo(f"身份设置失败: {response.json().get('error', '未知错误')}")

@click.command()
def GetTasks():
    """获取快递员的任务"""
    # 从配置文件中读取用户名
    config = get_config()
    if 'user' not in config or 'username' not in config['user']:
        click.echo("请先登录")
        return

    username = config['user']['username']
    response = requests.post(f"{API_URL}/delivery/assign/{username}")
    if response.status_code == 200 or response.status_code == 201:
        tasks = response.json().get('tasks', [])
        click.echo(f"任务获取成功: {tasks}")
    else:
        click.echo(f"任务获取失败: {response.json().get('error', '未知错误')}")

cli.add_command(GetTasks)
cli.add_command(register)
cli.add_command(login)
cli.add_command(set_role)

if __name__ == "__main__":
    cli()