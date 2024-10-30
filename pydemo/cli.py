import click
import requests
import configparser
import os
import curses
from Curse import view_tasks_curses
import uuid
import numpy as np
API_URL = "http://10.29.3.96:12345"
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
def view_tasks():
    """查看快递员任务"""
    # 从配置文件中读取用户名
    config = get_config()
    if 'user' not in config or 'username' not in config['user']:
        click.echo("请先登录")
        return

    username = config['user']['username']
    response = requests.post(f"{API_URL}/delivery/assign/{username}")
    if response.status_code == 200 or response.status_code == 201:
        tasks = response.json()
        curses.wrapper(view_tasks_curses, tasks)
    else:
        click.echo(f"任务获取失败: {response.json().get('error', '未知错误')}")

@click.command()
@click.option('-用户名', '--username', required=True, help='用户名')
@click.option('-密码', '--password', required=True, help='密码')
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
@click.option('-用户名', '--username', required=True, help='用户名')
@click.option('-密码', '--password', required=True, help='密码')
@click.option('-手机号', '--contact', required=False, help='联系方式')
def login(username, password, contact=''):
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
        response = requests.post(f"{API_URL}/notify/{username}")
        print(response.json().get('notification'))
    elif response.status_code == 401:
        click.echo(f"登录失败")

@click.command()
@click.option('-角色', '--role', type=click.Choice(['user', 'courier'], case_sensitive=False), required=True, help='用户身份')
def set_role(role):
    """设置用户身份"""
    # 从配置文件中读取用户名
    config = get_config()
    if 'user' not in config or 'username' not in config['user']:
        click.echo("请先登录")
        return

    username = config['user']['username']
    payload = {
        "role": role
    }
    response = requests.put(f"{API_URL}/user/{username}", json=payload)
    if response.status_code == 200:
        click.echo("身份设置成功")
    else:
        click.echo(f"身份设置失败")

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
        tasks = response.json()
        click.echo(f"任务获取成功: {tasks}")
    else:
        click.echo(f"任务获取失败")

@click.command()
@click.argument('delivery_id')
def complete_delivery(delivery_id):
    """完成配送任务"""
    response = requests.put(f"{API_URL}/delivery/{delivery_id}", json={"status": "completed"})
    if response.status_code == 200:
        click.echo("配送任务已完成")
    else:
        click.echo(f"完成配送任务失败")

@click.command()
def logout():
    """登出"""
    config = get_config()
    if 'user' in config:
        config.remove_section('user')
        save_config(config)
        click.echo("登出成功")
    else:
        click.echo("当前没有用户登录")

@click.command()
@click.option('-旧密码', '--old_password', required=True, help='旧密码')
@click.option('-新密码', '--new_password', required=True, help='新密码')
def change_password(old_password, new_password):
    """修改密码"""
    config = get_config()
    if 'user' not in config or 'username' not in config['user']:
        click.echo("请先登录")
        return

    username = config['user']['username']
    payload = {
        "username": username,
        "password": new_password
    }
    response = requests.put(f"{API_URL}/user/{username}", json=payload)
    if response.status_code == 200:
        click.echo("密码修改成功")
    else:
        click.echo(f"密码修改失败")

@click.command()
@click.argument('order_id')
def sign_order(order_id):
    """签收订单"""
    response = requests.put(f"{API_URL}/order/{order_id}", json={"status": "received"})
    if response.status_code == 200:
        click.echo("订单已完成")
    else:
        click.echo(f"完成订单失败")
@click.command()
@click.option('-发件人', '--sender_name', required=True, help='发件人姓名')
@click.option('-收件人', '--receiver_name', required=True, help='收件人姓名')
@click.option('-发件人地址', '--sender_address', required=True, help='发件人地址')
@click.option('-收件人地址', '--receiver_address', required=True, help='收件人地址')
@click.option('-优先级', '--priority', default=0, help='优先级')
def create_order(sender_name, receiver_name, sender_address, receiver_address, priority):
    """创建订单"""
    #生成订单ID
    order_id=str(uuid.uuid4())
    #根据地址生成随机坐标
    sender_address=np.random.uniform(1,100000,  2).tolist()
    receiver_address=np.random.uniform(1, 100000, 2).tolist()
    payload = {
        "order_id": order_id,
        "sender_name": sender_name,
        "receiver_name": receiver_name,
        "sender_address": sender_address,
        "receiver_address": receiver_address,
        "package_id": order_id,
        "priority": priority
    }
    print(payload)
    response = requests.post(f"{API_URL}/order", json=payload)
    if response.status_code == 201:
        click.echo("订单创建成功")
    else:
        click.echo(f"订单创建失败")

cli.add_command(view_tasks)
cli.add_command(GetTasks)
cli.add_command(register)
cli.add_command(login)
cli.add_command(set_role)
cli.add_command(complete_delivery)
cli.add_command(logout)
cli.add_command(change_password)
cli.add_command(sign_order)
cli.add_command(create_order)
if __name__ == "__main__":
    cli()