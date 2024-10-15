import click
import requests

API_URL = "http://localhost:5000"

@click.group()
def cli():
    """配送管理命令行工具"""
    pass

@click.command()
@click.argument('username')
@click.argument('email')
def register(username, email):
    """注册新用户"""
    payload = {
        "username": username,
        "email": email
    }
    response = requests.post(f"{API_URL}/user/register", json=payload)
    if response.status_code == 201:
        click.echo("注册成功")
    else:
        click.echo(f"注册失败: {response.json().get('error', '未知错误')}")

@click.command()
@click.argument('username')
def login(username):
    """用户登录"""
    payload = {
        "username": username
    }
    response = requests.post(f"{API_URL}/user/login", json=payload)
    if response.status_code == 200:
        click.echo("登录成功")
    else:
        click.echo(f"登录失败: {response.json().get('error', '未知错误')}")

@click.command()
@click.argument('username')
@click.argument('role',type=click.Choice( ['user','courier'],case_sensitive=False ))
def set_role(username, role):
    """设置用户身份"""
    payload = {
        "role": role
    }
    response = requests.put(f"{API_URL}/user/{username}/role", json=payload)
    if response.status_code == 200:
        click.echo("用户身份设置成功")
    else:
        click.echo(f"设置用户身份失败: {response.json().get('error', '未知错误')}")

cli.add_command(register)
cli.add_command(login)
if __name__ == '__main__':
    cli()


